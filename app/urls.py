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

urlpatterns = [
    # API Overview & Health Check
    path("", api_root, name="api_root"),
    path("health/", api_root, name="health_check"),
    # User Authentication & Profile
    path("api/auth/register/", register_user, name="auth_register"),
    path("api/auth/login/", login_user, name="auth_login"),
    path("api/auth/profile/", user_profile, name="auth_profile"),
    # Categories & Products (REST ViewSets)
    path("api/", include(router.urls)),
    # Shopping Cart (Add to Cart)
    path("api/cart/", view_cart, name="view_cart"),
    path("api/cart/add/", add_to_cart, name="add_to_cart"),
    path("api/cart/items/<int:item_id>/", cart_item_detail, name="cart_item_detail"),
    path("api/cart/clear/", clear_cart, name="clear_cart"),
    # Orders (Taking Orders)
    path("api/orders/", list_orders, name="list_orders"),
    path("api/orders/create/", create_order, name="create_order"),
    path("api/orders/<str:order_identifier>/", order_detail, name="order_detail"),
    path("api/orders/<str:order_identifier>/cancel/", cancel_order, name="cancel_order"),
    path("api/orders/<str:order_identifier>/status/", update_order_status, name="update_order_status"),
    # Payments
    path("api/payments/", list_payments, name="list_payments"),
    path("api/payments/process/", process_payment, name="process_payment"),
    path("api/payments/order/<str:order_identifier>/", get_payment_by_order, name="get_payment_by_order"),
    # Deliveries (Shipment Tracking)
    path("api/deliveries/", list_deliveries, name="list_deliveries"),
    path("api/deliveries/track/<str:tracking_number>/", track_delivery, name="track_delivery"),
    path("api/deliveries/order/<str:order_identifier>/", get_delivery_by_order, name="get_delivery_by_order"),
    path("api/deliveries/<int:delivery_id>/update-status/", update_delivery_status, name="update_delivery_status"),
]
