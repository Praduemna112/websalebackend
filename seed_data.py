import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from decimal import Decimal
from django.contrib.auth.models import User
from app.models import (
    Category,
    Product,
    CustomerProfile,
    Cart,
    CartItem,
    Order,
    OrderItem,
    Payment,
    Delivery,
)

def populate():
    print("--- 1. Creating Super Admin User 'PD Admin' ---")
    admin_user, created = User.objects.get_or_create(
        username="PD",
        defaults={
            "email": "admin@jiovendor.com",
            "first_name": "PD",
            "last_name": "Admin",
            "is_staff": True,
            "is_superuser": True,
        }
    )
    admin_user.set_password("Admin@123")
    admin_user.is_staff = True
    admin_user.is_superuser = True
    admin_user.save()
    print(f" Super Admin ready: Username='{admin_user.username}', Password='Admin@123'")

    admin_profile, _ = CustomerProfile.objects.get_or_create(
        user=admin_user,
        defaults={
            "phone": "+91 9876543210",
            "address": "WebSale HQ, Sector 5",
            "city": "Mumbai",
            "state": "Maharashtra",
            "postal_code": "400001",
            "country": "India",
        }
    )

    print("--- 2. Creating Customer User ---")
    customer_user, _ = User.objects.get_or_create(
        username="rahul_kumar",
        defaults={
            "email": "rahul@example.com",
            "first_name": "Rahul",
            "last_name": "Kumar",
        }
    )
    customer_user.set_password("Rahul@12345")
    customer_user.save()

    CustomerProfile.objects.get_or_create(
        user=customer_user,
        defaults={
            "phone": "+91 9123456789",
            "address": "42 MG Road, Indiranagar",
            "city": "Bengaluru",
            "state": "Karnataka",
            "postal_code": "560038",
            "country": "India",
        }
    )

    print("--- 3. Creating Product Categories ---")
    categories_data = [
        {
            "name": "Electronics",
            "description": "Smartphones, Audio, Laptops and everyday tech accessories.",
            "image_url": "https://images.unsplash.com/photo-1498049794561-7780e7231661?w=600&auto=format&fit=crop",
        },
        {
            "name": "Fashion & Apparel",
            "description": "Modern urban wear, timeless classics, and everyday essentials.",
            "image_url": "https://images.unsplash.com/photo-1445205170230-053b83016050?w=600&auto=format&fit=crop",
        },
        {
            "name": "Home & Living",
            "description": "Minimalist interior pieces, ceramic cookware, and cosy accents.",
            "image_url": "https://images.unsplash.com/photo-1513694203232-719a280e022f?w=600&auto=format&fit=crop",
        },
        {
            "name": "Wellness & Grooming",
            "description": "Organic botanicals, skin rituals, and daily calm essentials.",
            "image_url": "https://images.unsplash.com/photo-1522335789203-aabd1fc54bc9?w=600&auto=format&fit=crop",
        },
    ]

    cat_map = {}
    for c in categories_data:
        cat_obj, _ = Category.objects.get_or_create(
            name=c["name"],
            defaults={"description": c["description"], "image_url": c["image_url"]}
        )
        cat_map[c["name"]] = cat_obj

    print("--- 4. Creating Products with Card Images ---")
    products_data = [
        # Electronics
        {
            "category": cat_map["Electronics"],
            "name": "Studio ANC Wireless Headphones",
            "description": "Pure sound acoustic tuning with active noise cancellation, 40-hour battery life, and plush memory-foam ear cushions.",
            "price": Decimal("2499.00"),
            "original_price": Decimal("3499.00"),
            "stock": 25,
            "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=700&auto=format&fit=crop",
        },
        {
            "category": cat_map["Electronics"],
            "name": "Minimalist Mechanical Keyboard",
            "description": "Hot-swappable tactile switches with wireless Bluetooth 5.2 and matte PBT keycaps.",
            "price": Decimal("3999.00"),
            "original_price": Decimal("4999.00"),
            "stock": 18,
            "image_url": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=700&auto=format&fit=crop",
        },
        {
            "category": cat_map["Electronics"],
            "name": "Smart Fitness Pulse Tracker",
            "description": "All-day heart rate tracking, AMOLED touch display, GPS run tracking, and water resistant up to 50m.",
            "price": Decimal("1899.00"),
            "original_price": Decimal("2499.00"),
            "stock": 40,
            "image_url": "https://images.unsplash.com/photo-1575311373937-040b8e1fd5b6?w=700&auto=format&fit=crop",
        },
        # Fashion
        {
            "category": cat_map["Fashion & Apparel"],
            "name": "Classic Raw Denim Overshirt",
            "description": "Crafted from 100% organic cotton twill with reinforced stitching and custom matte metal hardware.",
            "price": Decimal("1599.00"),
            "original_price": Decimal("2199.00"),
            "stock": 30,
            "image_url": "https://images.unsplash.com/photo-1618354691373-d851c5c3a990?w=700&auto=format&fit=crop",
        },
        {
            "category": cat_map["Fashion & Apparel"],
            "name": "Urban Canvas Daily Tote",
            "description": "Heavyweight waterproof waxed canvas tote with vegetable-tanned leather straps and padded laptop compartment.",
            "price": Decimal("899.00"),
            "original_price": Decimal("1299.00"),
            "stock": 50,
            "image_url": "https://images.unsplash.com/photo-1544816155-12df9643f363?w=700&auto=format&fit=crop",
        },
        {
            "category": cat_map["Fashion & Apparel"],
            "name": "Everyday Minimalist Chrono Watch",
            "description": "Sapphire crystal glass with Japanese quartz movement and quick-release genuine leather band.",
            "price": Decimal("2799.00"),
            "original_price": Decimal("3599.00"),
            "stock": 15,
            "image_url": "https://images.unsplash.com/photo-1524805444758-089113d48a6d?w=700&auto=format&fit=crop",
        },
        # Home & Living
        {
            "category": cat_map["Home & Living"],
            "name": "Handcrafted Ceramic Pour-Over Dripper",
            "description": "Hand-thrown stoneware coffee dripper with ribbed interior spiral for a clean, nuanced brew.",
            "price": Decimal("649.00"),
            "original_price": Decimal("899.00"),
            "stock": 35,
            "image_url": "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=700&auto=format&fit=crop",
        },
        {
            "category": cat_map["Home & Living"],
            "name": "Amber Glass Soy Wax Candle",
            "description": "Hand-poured 100% natural soy wax infused with cedarwood, dried amber, and hints of crushed vanilla bean.",
            "price": Decimal("499.00"),
            "original_price": Decimal("699.00"),
            "stock": 60,
            "image_url": "https://images.unsplash.com/photo-1603006905003-be475563bc59?w=700&auto=format&fit=crop",
        },
        # Wellness
        {
            "category": cat_map["Wellness & Grooming"],
            "name": "Botanical Revitalizing Face Serum",
            "description": "Cold-pressed rosehip seed oil with vitamin C & squalane to balance skin tone and lock in deep hydration.",
            "price": Decimal("799.00"),
            "original_price": Decimal("1099.00"),
            "stock": 45,
            "image_url": "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?w=700&auto=format&fit=crop",
        },
    ]

    created_products = []
    for p in products_data:
        prod, _ = Product.objects.get_or_create(
            name=p["name"],
            defaults={
                "category": p["category"],
                "description": p["description"],
                "price": p["price"],
                "original_price": p["original_price"],
                "stock": p["stock"],
                "image_url": p["image_url"],
                "is_active": True,
            }
        )
        created_products.append(prod)

    print(f" Created {len(created_products)} Products with images.")

    print("--- 5. Creating Carts & Cart Items ---")
    cart, _ = Cart.objects.get_or_create(user=customer_user)
    if created_products:
        CartItem.objects.get_or_create(
            cart=cart,
            product=created_products[0],
            defaults={"quantity": 1}
        )
        CartItem.objects.get_or_create(
            cart=cart,
            product=created_products[3],
            defaults={"quantity": 2}
        )

    print("--- 6. Creating Orders, Payments & Deliveries ---")
    if len(created_products) >= 2:
        # Order 1 (Delivered)
        p1 = created_products[0]
        p2 = created_products[4]
        order1, created = Order.objects.get_or_create(
            order_number="WS-20261030-DEMO01",
            defaults={
                "user": customer_user,
                "status": Order.Status.DELIVERED,
                "total_amount": p1.price + (p2.price * 2),
                "shipping_name": "Rahul Kumar",
                "shipping_email": "rahul@example.com",
                "shipping_phone": "+91 9123456789",
                "shipping_address": "42 MG Road, Indiranagar",
                "shipping_city": "Bengaluru",
                "shipping_state": "Karnataka",
                "shipping_postal_code": "560038",
                "shipping_country": "India",
                "notes": "Please deliver between 10am and 4pm.",
            }
        )
        if created:
            OrderItem.objects.create(
                order=order1, product=p1, product_name=p1.name, price=p1.price, quantity=1, subtotal=p1.price
            )
            OrderItem.objects.create(
                order=order1, product=p2, product_name=p2.name, price=p2.price, quantity=2, subtotal=p2.price * 2
            )
            Payment.objects.create(
                order=order1,
                payment_method=Payment.Method.UPI,
                payment_status=Payment.Status.COMPLETED,
                amount=order1.total_amount,
                transaction_id="PAY-DEMO-UPI-9921",
            )
            Delivery.objects.create(
                order=order1,
                tracking_number="TRK-DEL-2026-901",
                carrier="BlueDart Express",
                delivery_status=Delivery.Status.DELIVERED,
                estimated_delivery="2026-10-31",
                current_location="Delivered to recipient - Bengaluru Hub",
            )

        # Order 2 (Processing / In-transit)
        p3 = created_products[1]
        order2, created2 = Order.objects.get_or_create(
            order_number="WS-20261030-DEMO02",
            defaults={
                "user": admin_user,
                "status": Order.Status.PROCESSING,
                "total_amount": p3.price,
                "shipping_name": "PD Admin",
                "shipping_email": "admin@jiovendor.com",
                "shipping_phone": "+91 9876543210",
                "shipping_address": "WebSale HQ, Sector 5",
                "shipping_city": "Mumbai",
                "shipping_state": "Maharashtra",
                "shipping_postal_code": "400001",
                "shipping_country": "India",
            }
        )
        if created2:
            OrderItem.objects.create(
                order=order2, product=p3, product_name=p3.name, price=p3.price, quantity=1, subtotal=p3.price
            )
            Payment.objects.create(
                order=order2,
                payment_method=Payment.Method.CREDIT_CARD,
                payment_status=Payment.Status.COMPLETED,
                amount=order2.total_amount,
                transaction_id="PAY-DEMO-CC-4432",
            )
            Delivery.objects.create(
                order=order2,
                tracking_number="TRK-DEL-2026-902",
                carrier="Delhivery Logistics",
                delivery_status=Delivery.Status.IN_TRANSIT,
                estimated_delivery="2026-11-02",
                current_location="In transit - Mumbai Sort Facility",
            )

    print("\n All dummy data successfully inserted!")

if __name__ == "__main__":
    populate()
