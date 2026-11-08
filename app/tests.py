from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from django.core import mail
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
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
        self.assertFalse(reg_res.data["user"]["is_superuser"])

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

    def test_superuser_can_manage_users_but_staff_cannot(self):
        customer = User.objects.create_user(username="managed-customer", password="Password123!")
        staff = User.objects.create_user(
            username="regular-staff", password="Password123!", is_staff=True
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {create_jwt_token(customer)}")
        self.assertEqual(self.client.get("/api/auth/users/").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.patch(
                f"/api/auth/users/{customer.id}/",
                {"is_staff": True},
                format="json",
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {create_jwt_token(staff)}")
        self.assertEqual(self.client.get("/api/auth/users/").status_code, status.HTTP_403_FORBIDDEN)

        superuser = User.objects.create_superuser(
            username="user-admin", email="admin@example.com", password="Password123!"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {create_jwt_token(superuser)}")
        response = self.client.get("/api/auth/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), User.objects.count())
        self.assertNotIn("password", response.data[0])

        response = self.client.patch(
            f"/api/auth/users/{customer.id}/",
            {"is_staff": True, "is_superuser": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        customer.refresh_from_db()
        self.assertTrue(customer.is_staff)
        self.assertTrue(customer.is_superuser)

        response = self.client.patch(
            f"/api/auth/users/{superuser.id}/",
            {"is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        FRONTEND_URL="http://localhost:3000",
    )
    def test_password_reset_request_and_confirmation(self):
        user = User.objects.create_user(
            username="reset-customer",
            email="reset@example.com",
            password="OriginalPassword123!",
        )

        unknown_response = self.client.post(
            "/api/auth/password-reset/",
            {"email": "unknown@example.com"},
            format="json",
        )
        response = self.client.post(
            "/api/auth/password-reset/",
            {"email": "RESET@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, unknown_response.data)
        self.assertEqual(len(mail.outbox), 1)

        reset_link = next(
            line for line in mail.outbox[0].body.splitlines() if line.startswith("http")
        )
        reset_url = urlparse(reset_link)
        reset_params = parse_qs(reset_url.query)
        self.assertEqual(reset_url.path, "/reset-password")
        confirm_response = self.client.post(
            "/api/auth/password-reset/confirm/",
            {
                "uid": reset_params["uid"][0],
                "token": reset_params["token"][0],
                "new_password": "NewUniquePassword847!",
            },
            format="json",
        )
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewUniquePassword847!"))

        expired_response = self.client.post(
            "/api/auth/password-reset/confirm/",
            {
                "uid": reset_params["uid"][0],
                "token": reset_params["token"][0],
                "new_password": "AnotherUniquePassword847!",
            },
            format="json",
        )
        self.assertEqual(expired_response.status_code, status.HTTP_400_BAD_REQUEST)

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

    def test_forgot_password(self):
        user = User.objects.create_user(
            username="forgot-user",
            email="forgotuser@example.com",
            password="InitialPassword123!",
        )

        # 1. Non-existent email -> 404
        res = self.client.post(
            "/api/auth/forgot-password/",
            {
                "email": "nonexistent@example.com",
                "new_password": "NewSecretPassword123!",
                "confirm_password": "NewSecretPassword123!",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        # 2. Mismatched passwords -> 400
        res = self.client.post(
            "/api/auth/forgot-password/",
            {
                "email": "forgotuser@example.com",
                "new_password": "NewSecretPassword123!",
                "confirm_password": "DifferentPassword123!",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # 3. Successful reset with confirm_password -> 200
        res = self.client.post(
            "/api/auth/forgot-password/",
            {
                "email": "forgotuser@example.com",
                "new_password": "NewSecretPassword123!",
                "confirm_password": "NewSecretPassword123!",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewSecretPassword123!"))

        # 4. Successful login with new password
        login_res = self.client.post(
            "/api/auth/login/",
            {"username": "forgot-user", "password": "NewSecretPassword123!"},
            format="json",
        )
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)

        # 5. Successful reset with currect_password alias -> 200
        res = self.client.post(
            "/api/auth/forgot-password/",
            {
                "email": "forgotuser@example.com",
                "new_password": "AnotherSecret123!",
                "currect_password": "AnotherSecret123!",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.check_password("AnotherSecret123!"))



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

    def test_category_crud_and_visibility_filtering(self):
        # Admin creates category
        admin = User.objects.create_user(username="category_admin", password="AdminPassword123!", is_staff=True)
        admin_token = create_jwt_token(admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_token}")

        # 1. Create category
        create_res = self.client.post("/api/categories/", {
            "name": "Books & Stationery",
            "description": "Best books",
            "is_active": True,
        }, format="json")
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        cat_id = create_res.data["id"]
        self.assertTrue(create_res.data["is_active"])

        # Create a product under this category
        book_prod = Product.objects.create(
            category_id=cat_id,
            name="Django Guide",
            slug="django-guide",
            price=Decimal("49.99"),
            stock=5,
            is_active=True,
        )

        # 2. Edit category name and description
        edit_res = self.client.patch(f"/api/categories/{cat_id}/", {
            "name": "Books, Comics & Stationery",
            "description": "Books and comics",
        }, format="json")
        self.assertEqual(edit_res.status_code, status.HTTP_200_OK)
        self.assertEqual(edit_res.data["name"], "Books, Comics & Stationery")
        self.assertEqual(edit_res.data["description"], "Books and comics")

        # Public customer sees the category and product
        self.client.credentials()  # Clear auth (public user)
        public_cats = self.client.get("/api/categories/")
        cat_ids = [c["id"] for c in public_cats.data.get("results", public_cats.data)]
        self.assertIn(cat_id, cat_ids)

        public_prods = self.client.get("/api/products/")
        prod_ids = [p["id"] for p in public_prods.data.get("results", public_prods.data)]
        self.assertIn(book_prod.id, prod_ids)

        # 3. Set category is_active=False (hide category)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_token}")
        hide_res = self.client.patch(f"/api/categories/{cat_id}/", {
            "is_active": False,
        }, format="json")
        self.assertEqual(hide_res.status_code, status.HTTP_200_OK)
        self.assertFalse(hide_res.data["is_active"])

        # 4. Verify public customer no longer sees the category or its products
        self.client.credentials()  # Clear auth (public user)
        public_cats = self.client.get("/api/categories/")
        cat_ids = [c["id"] for c in public_cats.data.get("results", public_cats.data)]
        self.assertNotIn(cat_id, cat_ids)

        public_prods = self.client.get("/api/products/")
        prod_ids = [p["id"] for p in public_prods.data.get("results", public_prods.data)]
        self.assertNotIn(book_prod.id, prod_ids)

        # Direct product detail for inactive category returns 404 to public
        detail_res = self.client.get(f"/api/products/{book_prod.id}/")
        self.assertEqual(detail_res.status_code, status.HTTP_404_NOT_FOUND)

        # Public cannot add product of inactive category to cart
        cart_res = self.client.post("/api/cart/add/", {
            "product_id": book_prod.id,
            "quantity": 1,
        }, format="json")
        self.assertEqual(cart_res.status_code, status.HTTP_404_NOT_FOUND)

        # Admin can still see inactive category and product
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_token}")
        admin_cats = self.client.get("/api/categories/")
        admin_cat_ids = [c["id"] for c in admin_cats.data.get("results", admin_cats.data)]
        self.assertIn(cat_id, admin_cat_ids)

        admin_prods = self.client.get("/api/products/")
        admin_prod_ids = [p["id"] for p in admin_prods.data.get("results", admin_prods.data)]
        self.assertIn(book_prod.id, admin_prod_ids)

        # 5. Delete category
        del_res = self.client.delete(f"/api/categories/{cat_id}/")
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Category.objects.filter(id=cat_id).exists())

        # Product still exists as uncategorized (on_delete=SET_NULL)
        book_prod.refresh_from_db()
        self.assertIsNone(book_prod.category)

