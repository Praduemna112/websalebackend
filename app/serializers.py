import base64
import binascii

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.text import slugify
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
    is_visible = serializers.BooleanField(source="is_active", required=False)

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "image_url",
            "is_active",
            "is_visible",
            "products_count",
            "created_at",
        ]

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, "copy") else dict(data)
        if "is_visible" in data and "is_active" not in data:
            data["is_active"] = data["is_visible"]
        return super().to_internal_value(data)

    def update(self, instance, validated_data):
        if "name" in validated_data and validated_data["name"] != instance.name:
            if not validated_data.get("slug"):
                validated_data["slug"] = slugify(validated_data["name"])
        return super().update(instance, validated_data)


# ---------------------------------------------------------------------------
# 2. PRODUCT SERIALIZERS
# ---------------------------------------------------------------------------
class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    category_is_active = serializers.SerializerMethodField()
    is_in_stock = serializers.BooleanField(read_only=True)
    discount_percentage = serializers.IntegerField(read_only=True)
    image_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def get_category_is_active(self, obj):
        if obj.category:
            return getattr(obj.category, "is_active", True)
        return True

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
            "category_is_active",
            "name",
            "slug",
            "description",
            "price",
            "original_price",
            "discount_percentage",
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
            "is_superuser",
            "profile",
        ]


class UserAdminSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(
        source="profile.phone",
        read_only=True,
        allow_null=True,
        default="",
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone",
            "is_active",
            "is_staff",
            "is_superuser",
            "date_joined",
            "last_login",
        ]
        read_only_fields = ["id", "date_joined", "last_login"]

    def validate(self, attrs):
        is_staff = attrs.get("is_staff", getattr(self.instance, "is_staff", False))
        is_superuser = attrs.get(
            "is_superuser", getattr(self.instance, "is_superuser", False)
        )
        if is_superuser and not is_staff:
            raise serializers.ValidationError(
                {"is_staff": "A superuser must also have staff access."}
            )
        return attrs


class AdminPasswordResetSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "The new passwords do not match."}
            )

        try:
            validate_password(attrs["new_password"], self.context["user"])
        except ValidationError as exc:
            raise serializers.ValidationError({"new_password": exc.messages}) from exc
        return attrs


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


class PasswordChangeSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        user = self.context["user"]
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "The new passwords do not match."}
            )

        try:
            validate_password(attrs["new_password"], user)
        except ValidationError as exc:
            raise serializers.ValidationError({"new_password": exc.messages}) from exc
        attrs["user"] = user
        return attrs


class PasswordRecoverySerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    recovery_code = serializers.CharField(max_length=128, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "The new passwords do not match."}
            )
        return attrs


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    new_password = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True, min_length=6, required=False)
    currect_password = serializers.CharField(write_only=True, min_length=6, required=False)

    def validate(self, attrs):
        confirm = attrs.get("confirm_password") or attrs.get("currect_password")
        if not confirm:
            raise serializers.ValidationError(
                {"confirm_password": "Confirm password is required."}
            )
        if attrs["new_password"] != confirm:
            raise serializers.ValidationError(
                {"confirm_password": "The new passwords do not match."}
            )
        attrs["confirm_password"] = confirm
        return attrs


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
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "product_name",
            "price",
            "quantity",
            "subtotal",
            "image_url",
        ]

    def get_image_url(self, obj):
        if obj.product and obj.product.image_url:
            return obj.product.image_url
        return ""


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
