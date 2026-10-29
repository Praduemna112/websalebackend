import uuid
from datetime import datetime, timezone
from django.contrib.auth.models import User
from django.db import models
from django.utils.text import slugify


# ---------------------------------------------------------------------------
# 1. CATEGORY MODEL
# ---------------------------------------------------------------------------
class Category(models.Model):
    """
    Product category (e.g. Electronics, Fashion, Home & Kitchen).
    Helps organize products on the React frontend.
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    image_url = models.URLField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "categories"
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# 2. PRODUCT MODEL
# ---------------------------------------------------------------------------
class Product(models.Model):
    """
    Product entity with pricing, stock tracking, category, and image support.
    """
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=240, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Original price before discount (useful for React UI badges)",
    )
    stock = models.PositiveIntegerField(default=0, help_text="Available inventory units")
    image_url = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True, help_text="Visible for sale on store")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "products"
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            short_id = uuid.uuid4().hex[:6]
            self.slug = f"{base_slug}-{short_id}"
        super().save(*args, **kwargs)

    @property
    def is_in_stock(self) -> bool:
        return self.stock > 0

    def __str__(self):
        return f"{self.name} (${self.price})"


# ---------------------------------------------------------------------------
# 3. CUSTOMER PROFILE MODEL
# ---------------------------------------------------------------------------
class CustomerProfile(models.Model):
    """
    Extended user profile for customer delivery addresses and contact info.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, default="India")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customer_profiles"
        verbose_name = "Customer Profile"
        verbose_name_plural = "Customer Profiles"

    def __str__(self):
        return f"{self.user.username}'s Profile"


# ---------------------------------------------------------------------------
# 4. CART & CART ITEM MODELS (Add to Cart)
# ---------------------------------------------------------------------------
class Cart(models.Model):
    """
    Shopping cart for a logged-in user or a guest session from React frontend.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="carts",
    )
    session_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text="Guest user session identifier from React frontend",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "carts"
        verbose_name = "Cart"
        verbose_name_plural = "Carts"

    @property
    def total_items(self) -> int:
        return sum(item.quantity for item in self.items.all())

    @property
    def total_amount(self):
        return sum(item.subtotal for item in self.items.all())

    def __str__(self):
        identifier = self.user.username if self.user else f"Guest ({self.session_id})"
        return f"Cart #{self.id} for {identifier}"


class CartItem(models.Model):
    """
    Individual product added to a shopping cart.
    """
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="cart_items")
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cart_items"
        verbose_name = "Cart Item"
        verbose_name_plural = "Cart Items"
        unique_together = ("cart", "product")

    @property
    def subtotal(self):
        return self.product.price * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"


# ---------------------------------------------------------------------------
# 5. ORDER & ORDER ITEM MODELS (Taking Orders)
# ---------------------------------------------------------------------------
class Order(models.Model):
    """
    Customer order entity representing a confirmed checkout.
    """
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        PROCESSING = "PROCESSING", "Processing"
        SHIPPED = "SHIPPED", "Shipped"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    order_number = models.CharField(max_length=50, unique=True, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # Shipping Address Details
    shipping_name = models.CharField(max_length=150)
    shipping_email = models.EmailField()
    shipping_phone = models.CharField(max_length=20)
    shipping_address = models.TextField()
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_postal_code = models.CharField(max_length=20)
    shipping_country = models.CharField(max_length=100, default="India")
    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "orders"
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.order_number:
            date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
            unique_part = uuid.uuid4().hex[:6].upper()
            self.order_number = f"WS-{date_part}-{unique_part}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.order_number} ({self.status}) - ${self.total_amount}"


class OrderItem(models.Model):
    """
    Individual line item in an Order. Captures price snapshot at purchase time.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, related_name="order_items")
    product_name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "order_items"
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"

    def __str__(self):
        return f"{self.quantity} x {self.product_name} (${self.subtotal})"


# ---------------------------------------------------------------------------
# 6. PAYMENT MODEL (Payments Entity)
# ---------------------------------------------------------------------------
class Payment(models.Model):
    """
    Payment transaction record for an Order.
    """
    class Method(models.TextChoices):
        CREDIT_CARD = "CREDIT_CARD", "Credit Card"
        DEBIT_CARD = "DEBIT_CARD", "Debit Card"
        UPI = "UPI", "UPI"
        NET_BANKING = "NET_BANKING", "Net Banking"
        COD = "COD", "Cash On Delivery"
        WALLET = "WALLET", "Digital Wallet"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="payment")
    payment_method = models.CharField(
        max_length=30,
        choices=Method.choices,
        default=Method.UPI,
    )
    payment_status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    transaction_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payments"
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            rand_code = uuid.uuid4().hex[:10].upper()
            self.transaction_id = f"PAY-{rand_code}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Payment {self.transaction_id} ({self.payment_status}) - ${self.amount}"


# ---------------------------------------------------------------------------
# 7. DELIVERY MODEL (Delivery Entity)
# ---------------------------------------------------------------------------
class Delivery(models.Model):
    """
    Shipment and delivery tracking record for an Order.
    """
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending Dispatch"
        DISPATCHED = "DISPATCHED", "Dispatched"
        IN_TRANSIT = "IN_TRANSIT", "In Transit"
        OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY", "Out for Delivery"
        DELIVERED = "DELIVERED", "Delivered"
        RETURNED = "RETURNED", "Returned"
        CANCELLED = "CANCELLED", "Cancelled"

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="delivery")
    tracking_number = models.CharField(max_length=100, unique=True, blank=True, null=True)
    courier_partner = models.CharField(max_length=100, default="WebSale Express")
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
    )
    delivery_address = models.TextField()
    estimated_delivery_date = models.DateField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    current_location = models.CharField(max_length=255, blank=True, null=True)
    status_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "deliveries"
        verbose_name = "Delivery"
        verbose_name_plural = "Deliveries"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.tracking_number:
            date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
            rand_code = uuid.uuid4().hex[:8].upper()
            self.tracking_number = f"TRK-{date_part}-{rand_code}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Delivery {self.tracking_number} ({self.status})"
