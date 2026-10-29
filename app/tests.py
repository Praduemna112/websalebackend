from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from app.models import (
    Cart,
    CartItem,
    Category,
    Delivery,
    Order,
    OrderItem,
    Payment,
    Product,
)
from app.views import create_jwt_token


class WebSaleAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create Category
        self.category = Category.objects.create(
            name="Electronics",
            slug="electronics",
            description="Electronic gadgets",
        )

        # Create Product
        self.product = Product.objects.create(
            category=self.category,
            name="Test Headphones",
            slug="test-headphones",
            description="High quality sound",
            price=Decimal("99.99"),
            original_price=Decimal("129.99"),
            stock=10,
            is_active=True,
        )

    def test_01_api_root(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "online")
        self.assertIn("endpoints", response.data)

    def test_02_product_list_and_filter(self):
        # List products
        response = self.client.get("/api/products/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", response.data)
        self.assertGreaterEqual(len(results), 1)

        # Search products
        search_res = self.client.get("/api/products/?search=Headphones")
        search_results = search_res.data.get("results", search_res.data)
        self.assertEqual(len(search_results), 1)

    def test_staff_can_save_product_image_url_or_base64(self):
        admin = User.objects.create_user(username="image-manager", password="AdminPassword123!", is_staff=True)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {create_jwt_token(admin)}")
        product_data = {
            "name": "Image Upload Product",
            "category": self.category.id,
            "price": "12.00",
            "stock": 2,
            "image_url": "data:image/png;base64,aGVsbG8=",
        }

        response = self.client.post("/api/products/", product_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["image_url"], product_data["image_url"])
        self.assertEqual(
            Product.objects.get(id=response.data["id"]).image_url,
            product_data["image_url"],
        )

        response = self.client.patch(
            f"/api/products/{response.data['id']}/",
            {"image_url": "https://example.com/product.png"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["image_url"], "https://example.com/product.png")

    def test_product_image_rejects_invalid_base64(self):
        admin = User.objects.create_user(username="invalid-image-manager", password="AdminPassword123!", is_staff=True)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {create_jwt_token(admin)}")

        response = self.client.post(
            "/api/products/",
            {
                "name": "Invalid Image Product",
                "price": "12.00",
                "stock": 2,
                "image_url": "data:image/png;base64,not-valid-base64!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("image_url", response.data)

    def test_03_user_register_and_login(self):
        # Register
        reg_data = {
            "username": "johndoe",
            "password": "Password123!",
            "email": "john@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "phone": "9998887776",
            "address": "123 Main St",
            "city": "Mumbai",
            "state": "Maharashtra",
            "postal_code": "400001",
        }
        reg_res = self.client.post("/api/auth/register/", reg_data, format="json")
        self.assertEqual(reg_res.status_code, status.HTTP_201_CREATED)
        self.assertIn("token", reg_res.data)
        self.assertFalse(reg_res.data["user"]["is_staff"])

        # Login
        login_res = self.client.post(
            "/api/auth/login/",
            {"username": "johndoe", "password": "Password123!"},
            format="json",
        )
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        token = login_res.data["token"]

        # Profile with JWT
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        profile_res = self.client.get("/api/auth/profile/")
        self.assertEqual(profile_res.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_res.data["username"], "johndoe")

    def test_04_add_to_cart_and_view_cart(self):
        session_id = "test-session-cart-1"

        # Add to cart
        add_res = self.client.post(
            "/api/cart/add/",
            {"product_id": self.product.id, "quantity": 2, "session_id": session_id},
            format="json",
        )
        self.assertEqual(add_res.status_code, status.HTTP_200_OK)
        cart_data = add_res.data["cart"]
        self.assertEqual(cart_data["total_items"], 2)

        register_res = self.client.post(
            "/api/auth/register/",
            {
                "username": "cart-customer",
                "password": "Password123!",
                "email": "cart@example.com",
                "session_id": session_id,
            },
            format="json",
        )
        self.assertEqual(register_res.status_code, status.HTTP_201_CREATED)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {register_res.data['token']}",
        )

        # View cart
        view_res = self.client.get(f"/api/cart/?session_id={session_id}")
        self.assertEqual(view_res.status_code, status.HTTP_200_OK)
        self.assertEqual(view_res.data["total_items"], 2)
        self.assertEqual(Decimal(str(view_res.data["total_amount"])), Decimal("199.98"))

    def test_05_taking_order_workflow(self):
        session_id = "test-session-order-1"

        # 1. Add to cart
        self.client.post(
            "/api/cart/add/",
            {"product_id": self.product.id, "quantity": 2, "session_id": session_id},
            format="json",
        )

        initial_stock = self.product.stock

        # 2. Place Order
        order_payload = {
            "session_id": session_id,
            "shipping_name": "Jane Doe",
            "shipping_email": "jane@example.com",
            "shipping_phone": "+91 9123456789",
            "shipping_address": "Flat 402, Sunshine Apts, Ring Road",
            "shipping_city": "Bengaluru",
            "shipping_state": "Karnataka",
            "shipping_postal_code": "560034",
            "shipping_country": "India",
            "payment_method": "COD",
        }
        order_res = self.client.post("/api/orders/create/", order_payload, format="json")
        self.assertEqual(order_res.status_code, status.HTTP_201_CREATED)
        order_data = order_res.data["order"]

        order_number = order_data["order_number"]
        self.assertTrue(order_number.startswith("WS-"))
        self.assertEqual(order_data["status"], "PENDING")

        # Verify stock decremented
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, initial_stock - 2)

        # Verify Payment and Delivery entities automatically created
        self.assertIsNotNone(order_data.get("payment"))
        self.assertEqual(order_data["payment"]["payment_status"], "PENDING")

        self.assertIsNotNone(order_data.get("delivery"))
        self.assertEqual(order_data["delivery"]["status"], "PENDING")
        tracking_number = order_data["delivery"]["tracking_number"]
        self.assertTrue(tracking_number.startswith("TRK-"))

        # A staff member records payment collected for the COD order.
        admin = User.objects.create_user(
            username="store-admin",
            password="AdminPassword123!",
            is_staff=True,
        )
        login_res = self.client.post(
            "/api/auth/login/",
            {"username": "store-admin", "password": "AdminPassword123!"},
            format="json",
        )
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        self.assertTrue(login_res.data["user"]["is_staff"])
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_res.data['token']}")

        # 3. Record payment
        pay_res = self.client.post(
            "/api/payments/process/",
            {
                "order_number": order_number,
                "payment_status": "COMPLETED",
                "transaction_id": "UPI-TXN-123456",
            },
            format="json",
        )
        self.assertEqual(pay_res.status_code, status.HTTP_200_OK)
        self.assertEqual(pay_res.data["payment"]["payment_status"], "COMPLETED")
        self.assertEqual(pay_res.data["order_status"], "CONFIRMED")

        # 4. Delivery Tracking
        track_res = self.client.get(f"/api/deliveries/track/{tracking_number}/")
        self.assertEqual(track_res.status_code, status.HTTP_200_OK)
        self.assertEqual(track_res.data["tracking_number"], tracking_number)
        self.assertEqual(track_res.data["order_number"], order_number)

        # 5. Update Delivery Status
        delivery_id = order_data["delivery"]["id"]
        update_del_res = self.client.patch(
            f"/api/deliveries/{delivery_id}/update-status/",
            {
                "status": "DELIVERED",
                "current_location": "Customer Doorstep, Bengaluru",
                "status_notes": "Delivered and signed by customer",
            },
            format="json",
        )
        self.assertEqual(update_del_res.status_code, status.HTTP_200_OK)
        self.assertEqual(update_del_res.data["delivery"]["status"], "DELIVERED")

        # Verify order is now marked DELIVERED
        order = Order.objects.get(order_number=order_number)
        self.assertEqual(order.status, "DELIVERED")

    def test_staff_permissions_and_customer_order_isolation(self):
        response = self.client.get("/api/orders/")
        self.assertNotEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(
            "/api/payments/process/",
            {"order_number": "unknown", "payment_status": "COMPLETED"},
            format="json",
        )
        self.assertNotEqual(response.status_code, status.HTTP_200_OK)

        customer = User.objects.create_user(username="customer", password="Password123!")
        other_customer = User.objects.create_user(username="other", password="Password123!")
        order = Order.objects.create(
            user=customer,
            total_amount=Decimal("10.00"),
            shipping_name="Customer",
            shipping_email="customer@example.com",
            shipping_phone="9999999999",
            shipping_address="1 Main Street",
            shipping_city="Mumbai",
            shipping_state="Maharashtra",
            shipping_postal_code="400001",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {create_jwt_token(other_customer)}")
        response = self.client.get(f"/api/orders/{order.order_number}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        response = self.client.post("/api/categories/", {"name": "Forbidden"}, format="json")
        self.assertNotEqual(response.status_code, status.HTTP_201_CREATED)

        admin = User.objects.create_user(username="manager", password="Password123!", is_staff=True)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {create_jwt_token(admin)}")
        response = self.client.patch(
            f"/api/orders/{order.order_number}/status/",
            {"status": "PROCESSING"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["order"]["status"], "PROCESSING")

        response = self.client.post("/api/categories/", {"name": "Staff category"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
