from django.contrib import admin

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


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "created_at")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "category",
        "price",
        "original_price",
        "stock",
        "is_active",
        "created_at",
    )
    list_filter = ("category", "is_active", "created_at")
    search_fields = ("name", "description")
    list_editable = ("price", "stock", "is_active")


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "phone", "city", "state", "country")
    search_fields = ("user__username", "user__email", "phone", "city")


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session_id", "total_items", "total_amount", "updated_at")
    search_fields = ("user__username", "session_id")
    inlines = [CartItemInline]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product_name", "price", "quantity", "subtotal")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "user",
        "shipping_name",
        "status",
        "total_amount",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("order_number", "shipping_name", "shipping_email", "shipping_phone")
    inlines = [OrderItemInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_id",
        "order",
        "payment_method",
        "payment_status",
        "amount",
        "paid_at",
    )
    list_filter = ("payment_method", "payment_status", "created_at")
    search_fields = ("transaction_id", "order__order_number")


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "tracking_number",
        "order",
        "courier_partner",
        "status",
        "estimated_delivery_date",
        "delivered_at",
    )
    list_filter = ("status", "courier_partner", "created_at")
    search_fields = ("tracking_number", "order__order_number", "current_location")
