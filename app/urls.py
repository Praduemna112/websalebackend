from django.urls import include, path
from rest_framework.routers import DefaultRouter

from app.views import (
    CategoryViewSet,
    ProductViewSet,
    add_to_cart,
    api_root,
    cancel_order,
    cart_item_detail,
    clear_cart,
    create_order,
    get_delivery_by_order,
    get_payment_by_order,
    list_deliveries,
    list_orders,
    list_payments,
    login_user,
    order_detail,
    process_payment,
    register_user,
    track_delivery,
    update_order_status,
    update_delivery_status,
    user_profile,
    view_cart,
)

# Router for ViewSets (Categories & Products)
router = DefaultRouter()
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"products", ProductViewSet, basename="product")

base_api_patterns = [
    # API Overview & Health Check
    path("", api_root, name="api_root"),
    path("health/", api_root, name="health_check"),
    # User Authentication & Profile
    path("auth/register/", register_user, name="auth_register"),
    path("auth/login/", login_user, name="auth_login"),
    path("auth/profile/", user_profile, name="auth_profile"),
    # Categories & Products (REST ViewSets)
    path("", include(router.urls)),
    # Shopping Cart (Add to Cart)
    path("cart/", view_cart, name="view_cart"),
    path("cart/add/", add_to_cart, name="add_to_cart"),
    path("cart/items/<int:item_id>/", cart_item_detail, name="cart_item_detail"),
    path("cart/clear/", clear_cart, name="clear_cart"),
    # Orders (Taking Orders)
    path("orders/", list_orders, name="list_orders"),
    path("orders/create/", create_order, name="create_order"),
    path("orders/<str:order_identifier>/", order_detail, name="order_detail"),
    path("orders/<str:order_identifier>/cancel/", cancel_order, name="cancel_order"),
    path("orders/<str:order_identifier>/status/", update_order_status, name="update_order_status"),
    # Payments
    path("payments/", list_payments, name="list_payments"),
    path("payments/process/", process_payment, name="process_payment"),
    path("payments/order/<str:order_identifier>/", get_payment_by_order, name="get_payment_by_order"),
    # Deliveries (Shipment Tracking)
    path("deliveries/", list_deliveries, name="list_deliveries"),
    path("deliveries/track/<str:tracking_number>/", track_delivery, name="track_delivery"),
    path("deliveries/order/<str:order_identifier>/", get_delivery_by_order, name="get_delivery_by_order"),
    path("deliveries/<int:delivery_id>/update-status/", update_delivery_status, name="update_delivery_status"),
]

urlpatterns = [
    # Support both direct (/products/) and prefixed (/api/products/)
    path("", include(base_api_patterns)),
    path("api/", include(base_api_patterns)),
]
