import base64
import binascii

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.contrib.auth.models import User
from rest_framework import serializers

from app.models import (
    Cart,
    CartItem,
    Category,
    CustomerProfile,
    Delivery,
    Order,
    OrderItem,
    Payment,
    Product,
)


# ---------------------------------------------------------------------------
# 1. CATEGORY SERIALIZER
# ---------------------------------------------------------------------------
class CategorySerializer(serializers.ModelSerializer):
    products_count = serializers.IntegerField(source="products.count", read_only=True)

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "image_url",
            "products_count",
            "created_at",
        ]


# ---------------------------------------------------------------------------
# 2. PRODUCT SERIALIZERS
# ---------------------------------------------------------------------------
class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)
    image_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_image_url(self, value):
        if value is None or value == "":
            return value

        if value.startswith("data:"):
            try:
                header, encoded_image = value.split(",", 1)
            except ValueError as exc:
                raise serializers.ValidationError("Provide a valid Base64 image.") from exc

            if header not in {
                "data:image/jpeg;base64",
                "data:image/png;base64",
                "data:image/webp;base64",
                "data:image/gif;base64",
            }:
                raise serializers.ValidationError(
                    "Use a JPEG, PNG, WebP, or GIF image encoded as Base64."
                )

            if len(encoded_image) > 4 * ((5 * 1024 * 1024 + 2) // 3):
                raise serializers.ValidationError("Product images must be 5 MB or smaller.")
            try:
                image_data = base64.b64decode(encoded_image, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise serializers.ValidationError("Provide a valid Base64 image.") from exc

            if not image_data:
                raise serializers.ValidationError("The uploaded image is empty.")
            if len(image_data) > 5 * 1024 * 1024:
                raise serializers.ValidationError("Product images must be 5 MB or smaller.")
            return value

        try:
            URLValidator(schemes=["http", "https"])(value)
        except ValidationError as exc:
            raise serializers.ValidationError(
                "Enter a valid HTTP(S) image URL or upload an image."
            ) from exc
        return value

    class Meta:
        model = Product
        fields = [
            "id",
            "category",
            "category_name",
            "name",
            "slug",
            "description",
            "price",
            "original_price",
            "stock",
            "image_url",
            "is_active",
            "is_in_stock",
            "created_at",
            "updated_at",
        ]


# ---------------------------------------------------------------------------
# 3. USER & PROFILE SERIALIZERS
# ---------------------------------------------------------------------------
class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerProfile
        fields = [
            "phone",
            "address",
            "city",
            "state",
            "postal_code",
            "country",
        ]


class UserSerializer(serializers.ModelSerializer):
    profile = CustomerProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_staff",
            "profile",
        ]


class UserRegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, default="")
    password = serializers.CharField(write_only=True, min_length=6)
    first_name = serializers.CharField(max_length=150, required=False, default="")
    last_name = serializers.CharField(max_length=150, required=False, default="")
    phone = serializers.CharField(max_length=20, required=False, default="")
    address = serializers.CharField(required=False, default="")
    city = serializers.CharField(max_length=100, required=False, default="")
    state = serializers.CharField(max_length=100, required=False, default="")
    postal_code = serializers.CharField(max_length=20, required=False, default="")


class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)


# ---------------------------------------------------------------------------
# 4. CART & CART ITEM SERIALIZERS (Add to Cart)
# ---------------------------------------------------------------------------
class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source="product", write_only=True
    )
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = [
            "id",
            "product",
            "product_id",
            "quantity",
            "subtotal",
            "created_at",
            "updated_at",
        ]


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Cart
        fields = [
            "id",
            "user",
            "session_id",
            "total_items",
            "total_amount",
            "items",
            "created_at",
            "updated_at",
        ]


class AddToCartSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    session_id = serializers.CharField(max_length=100, required=False, allow_blank=True)


class UpdateCartItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)


# ---------------------------------------------------------------------------
# 5. PAYMENT & DELIVERY SERIALIZERS
# ---------------------------------------------------------------------------
class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id",
            "payment_method",
            "payment_status",
            "transaction_id",
            "amount",
            "paid_at",
            "created_at",
            "updated_at",
        ]


class DeliverySerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.order_number", read_only=True)

    class Meta:
        model = Delivery
        fields = [
            "id",
            "order",
            "order_number",
            "tracking_number",
            "courier_partner",
            "status",
            "delivery_address",
            "estimated_delivery_date",
            "delivered_at",
            "current_location",
            "status_notes",
            "created_at",
            "updated_at",
        ]


# ---------------------------------------------------------------------------
# 6. ORDER & ORDER ITEM SERIALIZERS (Taking Orders)
# ---------------------------------------------------------------------------
class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "product_name",
            "price",
            "quantity",
            "subtotal",
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    payment = PaymentSerializer(read_only=True)
    delivery = DeliverySerializer(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "user",
            "status",
            "total_amount",
            "shipping_name",
            "shipping_email",
            "shipping_phone",
            "shipping_address",
            "shipping_city",
            "shipping_state",
            "shipping_postal_code",
            "shipping_country",
            "notes",
            "items",
            "payment",
            "delivery",
            "created_at",
            "updated_at",
        ]


class CreateOrderSerializer(serializers.Serializer):
    """
    Checkout request payload: converts cart to order or creates order directly.
    """
    session_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    shipping_name = serializers.CharField(max_length=150)
    shipping_email = serializers.EmailField()
    shipping_phone = serializers.CharField(max_length=20)
    shipping_address = serializers.CharField()
    shipping_city = serializers.CharField(max_length=100)
    shipping_state = serializers.CharField(max_length=100)
    shipping_postal_code = serializers.CharField(max_length=20)
    shipping_country = serializers.CharField(max_length=100, default="India")
    notes = serializers.CharField(required=False, allow_blank=True)
    payment_method = serializers.ChoiceField(
        choices=Payment.Method.choices,
        default=Payment.Method.UPI,
    )


class ProcessPaymentSerializer(serializers.Serializer):
    """
    Simulate/record payment gateway confirmation.
    """
    payment_status = serializers.ChoiceField(
        choices=Payment.Status.choices,
        default=Payment.Status.COMPLETED,
    )
    transaction_id = serializers.CharField(max_length=100, required=False)


class UpdateDeliveryStatusSerializer(serializers.Serializer):
    """
    Update delivery tracking progress.
    """
    status = serializers.ChoiceField(choices=Delivery.Status.choices)
    current_location = serializers.CharField(max_length=255, required=False, allow_blank=True)
    status_notes = serializers.CharField(required=False, allow_blank=True)


class UpdateOrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)
