from datetime import datetime, timedelta, timezone
import secrets
from decimal import Decimal

import jwt
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, BasePermission, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from app.email_notifications import (
    send_new_order_notifications,
    send_order_status_notification,
)
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
from app.serializers import (
    AddToCartSerializer,
    CartItemSerializer,
    CartSerializer,
    CategorySerializer,
    CreateOrderSerializer,
    DeliverySerializer,
    OrderSerializer,
    PaymentSerializer,
    ProcessPaymentSerializer,
    ProductSerializer,
    UpdateCartItemSerializer,
    UpdateDeliveryStatusSerializer,
    UpdateOrderStatusSerializer,
    UserAdminSerializer,
    AdminPasswordResetSerializer,
    ForgotPasswordSerializer,
    PasswordChangeSerializer,
    PasswordRecoverySerializer,
    UserLoginSerializer,
    UserRegisterSerializer,
    UserSerializer,
)

# JWT Secret & Lifetime
SECRET_KEY = settings.SECRET_KEY
TOKEN_LIFETIME = timedelta(days=7)


# ---------------------------------------------------------------------------
# JWT HELPER FUNCTIONS
# ---------------------------------------------------------------------------
def create_jwt_token(user: User) -> str:
    """Generate a JWT token for the user."""
    expires_at = datetime.now(timezone.utc) + TOKEN_LIFETIME
    payload = {
        "user_id": user.id,
        "username": user.username,
        "exp": expires_at,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def get_authenticated_user(request):
    """
    Extract user from Bearer JWT token in Authorization header,
    or fallback to Django's standard request.user if logged in.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            return User.objects.filter(id=user_id, is_active=True).first()
        except (jwt.PyJWTError, TypeError, ValueError):
            return None
    if getattr(request, "user", None) and request.user.is_authenticated:
        return request.user
    return None


class IsJWTAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return get_authenticated_user(request) is not None


class IsJWTAdminUser(BasePermission):
    def has_permission(self, request, view):
        user = get_authenticated_user(request)
        return bool(user and user.is_staff)


class IsJWTSuperuser(BasePermission):
    def has_permission(self, request, view):
        user = get_authenticated_user(request)
        return bool(user and user.is_superuser)


class PasswordRecoveryRateThrottle(AnonRateThrottle):
    rate = "5/hour"


class ReadOnlyOrJWTAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or IsJWTAdminUser().has_permission(request, view)


def merge_guest_cart(user, session_id):
    if not session_id:
        return

    guest_cart = Cart.objects.filter(user__isnull=True, session_id=session_id).first()
    if not guest_cart:
        return

    user_cart = Cart.objects.filter(user=user).first()
    if not user_cart:
        guest_cart.user = user
        guest_cart.session_id = None
        guest_cart.save(update_fields=["user", "session_id", "updated_at"])
        return

    with transaction.atomic():
        for guest_item in guest_cart.items.select_related("product"):
            user_item = CartItem.objects.filter(cart=user_cart, product=guest_item.product).first()
            if user_item:
                user_item.quantity = min(
                    guest_item.product.stock,
                    user_item.quantity + guest_item.quantity,
                )
                user_item.save(update_fields=["quantity", "updated_at"])
                guest_item.delete()
            else:
                guest_item.cart = user_cart
                guest_item.quantity = min(guest_item.quantity, guest_item.product.stock)
                if guest_item.quantity:
                    guest_item.save(update_fields=["cart", "quantity", "updated_at"])
                else:
                    guest_item.delete()

        guest_cart.delete()


def get_or_create_cart(request, session_id_hint: str = None) -> Cart:
    """
    Retrieve existing cart or create a new cart.
    Supports logged-in users and guest sessions from React frontend.
    """
    user = get_authenticated_user(request)
    if user:
        cart, _ = Cart.objects.get_or_create(user=user)
        return cart

    # Determine session ID from hint, header, query params, or cookies
    request_data = getattr(request, "data", {})
    session_id = (
        session_id_hint
        or request.headers.get("X-Session-ID")
        or request.query_params.get("session_id")
        or (request_data.get("session_id") if isinstance(request_data, dict) else None)
    )

    if not session_id:
        session_id = f"guest-{secrets.token_hex(12)}"

    cart, _ = Cart.objects.get_or_create(session_id=session_id, user=None)
    return cart


# ---------------------------------------------------------------------------
# API ROOT & HEALTH CHECK
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([AllowAny])
def api_root(request):
    """
    Overview of all available API endpoints for easy testing and React integration.
    """
    return Response({
        "status": "online",
        "service": "WebSale E-Commerce Backend API",
        "version": "1.0.0",
        "database": "MySQL (websale)",
        "endpoints": {
            "auth": {
                "register": "/api/auth/register/",
                "login": "/api/auth/login/",
                "profile": "/api/auth/profile/",
                "forgot_password": "/api/auth/forgot-password/",
                "change_password": "/api/auth/change-password/",
                "recovery_code": "/api/auth/recovery-code/",
                "recover_password": "/api/auth/recover-password/",
                "users": "/api/auth/users/",
                "reset_user_password": "/api/auth/users/<id>/password/",
            },
            "products": {
                "categories": "/api/categories/",
                "products": "/api/products/",
                "featured": "/api/products/featured/",
            },
            "cart": {
                "view": "/api/cart/",
                "add": "/api/cart/add/",
                "update_item": "/api/cart/items/<id>/",
                "remove_item": "/api/cart/items/<id>/",
                "clear": "/api/cart/clear/",
            },
            "orders": {
                "create": "/api/orders/create/",
                "list": "/api/orders/",
                "detail": "/api/orders/<id_or_number>/",
                "cancel": "/api/orders/<id_or_number>/cancel/",
            },
            "payments": {
                "list": "/api/payments/",
                "process": "/api/payments/process/",
                "by_order": "/api/payments/order/<id_or_number>/",
            },
            "deliveries": {
                "list": "/api/deliveries/",
                "track": "/api/deliveries/track/<tracking_number>/",
                "by_order": "/api/deliveries/order/<id_or_number>/",
                "update_status": "/api/deliveries/<id>/update-status/",
            },
        },
    })


# ---------------------------------------------------------------------------
# 1. USER AUTHENTICATION & PROFILE VIEWS
# ---------------------------------------------------------------------------
@api_view(["POST"])
@permission_classes([AllowAny])
def register_user(request):
    """
    Register a new customer account.
    Returns user details along with JWT token for auto-login on React frontend.
    """
    serializer = UserRegisterSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    username = serializer.validated_data["username"]
    password = serializer.validated_data["password"]
    email = serializer.validated_data.get("email", "")

    if User.objects.filter(username=username).exists():
        return Response({"detail": "Username already exists"}, status=status.HTTP_409_CONFLICT)

    if email and User.objects.filter(email=email).exists():
        return Response({"detail": "Email already registered"}, status=status.HTTP_409_CONFLICT)

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=serializer.validated_data.get("first_name", ""),
        last_name=serializer.validated_data.get("last_name", ""),
    )

    # Create associated customer profile
    CustomerProfile.objects.create(
        user=user,
        phone=serializer.validated_data.get("phone", ""),
        address=serializer.validated_data.get("address", ""),
        city=serializer.validated_data.get("city", ""),
        state=serializer.validated_data.get("state", ""),
        postal_code=serializer.validated_data.get("postal_code", ""),
    )
    merge_guest_cart(user, request.data.get("session_id"))

    token = create_jwt_token(user)
    return Response(
        {
            "message": "User registered successfully",
            "token": token,
            "user": UserSerializer(user).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def login_user(request):
    """
    Login with username and password. Returns JWT token and user info.
    """
    serializer = UserLoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    username = serializer.validated_data["username"]
    password = serializer.validated_data["password"]

    user = authenticate(username=username, password=password)
    if user is None:
        return Response(
            {"detail": "Invalid username or password"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        return Response(
            {"detail": "User account is disabled"},
            status=status.HTTP_403_FORBIDDEN,
        )

    CustomerProfile.objects.get_or_create(user=user)
    merge_guest_cart(user, request.data.get("session_id"))
    token = create_jwt_token(user)
    return Response({
        "message": "Login successful",
        "token": token,
        "token_type": "Bearer",
        "user": UserSerializer(user).data,
    })


@api_view(["POST"])
@permission_classes([IsJWTAuthenticated])
def change_password(request):
    user = get_authenticated_user(request)
    if not user:
        return Response({"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

    serializer = PasswordChangeSerializer(
        data=request.data,
        context={"user": user},
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(serializer.validated_data["new_password"])
    user.save(update_fields=["password"])
    return Response({"detail": "Your password has been changed successfully."})


@api_view(["POST"])
@permission_classes([IsJWTAuthenticated])
def generate_recovery_code(request):
    user = get_authenticated_user(request)
    if not user:
        return Response({"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

    profile, _ = CustomerProfile.objects.get_or_create(user=user)
    recovery_code = secrets.token_urlsafe(32)
    profile.recovery_code_hash = make_password(recovery_code)
    profile.save(update_fields=["recovery_code_hash", "updated_at"])
    return Response({
        "recovery_code": recovery_code,
        "detail": "Save this recovery code now. It will not be shown again.",
    })


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PasswordRecoveryRateThrottle])
def recover_password(request):
    serializer = PasswordRecoverySerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        user = User.objects.select_for_update().filter(
            username__iexact=serializer.validated_data["username"]
        ).first()
        profile = (
            CustomerProfile.objects.select_for_update().filter(user=user).first()
            if user
            else None
        )
        recovery_code = serializer.validated_data["recovery_code"]
        if not profile or not profile.recovery_code_hash or not check_password(
            recovery_code, profile.recovery_code_hash
        ):
            return Response(
                {"detail": "Username or recovery code is invalid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        password_serializer = PasswordChangeSerializer(
            data={
                "new_password": serializer.validated_data["new_password"],
                "confirm_password": serializer.validated_data["confirm_password"],
            },
            context={"user": user},
        )
        if not password_serializer.is_valid():
            return Response(
                password_serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(password_serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        profile.recovery_code_hash = ""
        profile.save(update_fields=["recovery_code_hash", "updated_at"])

    return Response({"detail": "Password reset successfully. You can now sign in."})


@api_view(["POST"])
@permission_classes([AllowAny])
def forgot_password(request):
    """
    Direct password reset by verifying email, new password, and confirmation password.
    """
    serializer = ForgotPasswordSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data["email"].strip()
    new_password = serializer.validated_data["new_password"]

    users = User.objects.filter(email__iexact=email, is_active=True)
    if not users.exists():
        if User.objects.filter(email__iexact=email).exists():
            return Response(
                {"detail": "This user account is disabled."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(
            {"detail": "No account found with this email address."},
            status=status.HTTP_404_NOT_FOUND,
        )

    user = users.first()
    try:
        validate_password(new_password, user)
    except ValidationError as exc:
        return Response(
            {"detail": " ".join(exc.messages), "errors": exc.messages},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        for u in users:
            u.set_password(new_password)
            u.save(update_fields=["password"])

    return Response(
        {
            "message": "Password reset successfully. You can now sign in with your new password.",
            "detail": "Password reset successfully.",
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET", "PUT"])
@permission_classes([IsJWTAuthenticated])
def user_profile(request):
    """
    Get or update authenticated user profile and shipping details.
    """
    user = get_authenticated_user(request)
    if not user:
        return Response({"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

    profile, _ = CustomerProfile.objects.get_or_create(user=user)

    if request.method == "GET":
        return Response(UserSerializer(user).data)

    if request.method == "PUT":
        data = request.data
        if "first_name" in data:
            user.first_name = data["first_name"]
        if "last_name" in data:
            user.last_name = data["last_name"]
        if "email" in data:
            user.email = data["email"]
        user.save()

        # Update profile fields
        for field in ["phone", "address", "city", "state", "postal_code", "country"]:
            if field in data:
                setattr(profile, field, data[field])
        profile.save()

        return Response({
            "message": "Profile updated successfully",
            "user": UserSerializer(user).data,
        })


@api_view(["GET"])
@permission_classes([IsJWTSuperuser])
def admin_user_list(request):
    users = User.objects.select_related("profile").order_by("id")
    return Response(UserAdminSerializer(users, many=True).data)


@api_view(["PATCH"])
@permission_classes([IsJWTSuperuser])
def admin_user_detail(request, user_id):
    actor = get_authenticated_user(request)
    user = get_object_or_404(User, pk=user_id)
    serializer = UserAdminSerializer(user, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    changed_fields = serializer.validated_data
    if user.pk == actor.pk and any(
        changed_fields.get(field, getattr(user, field)) != getattr(user, field)
        for field in ("is_active", "is_staff", "is_superuser")
    ):
        return Response(
            {"detail": "You cannot change your own account access."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    removes_active_superuser = (
        user.is_active
        and user.is_superuser
        and (
            changed_fields.get("is_active", True) is False
            or changed_fields.get("is_superuser", True) is False
        )
    )
    if removes_active_superuser and not User.objects.filter(
        is_active=True, is_superuser=True
    ).exclude(pk=user.pk).exists():
        return Response(
            {"detail": "At least one active superuser must remain."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer.save()
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsJWTSuperuser])
def admin_user_password_reset(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    serializer = AdminPasswordResetSerializer(
        data=request.data,
        context={"user": user},
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(serializer.validated_data["new_password"])
    user.save(update_fields=["password"])
    return Response({"detail": f"Password updated for {user.username}."})


# ---------------------------------------------------------------------------
# 2. CATEGORY & PRODUCT VIEWSETS
# ---------------------------------------------------------------------------
def category_has_is_active_column() -> bool:
    """Check if 'is_active' column exists in categories table to prevent OperationalError 1054."""
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'categories' AND COLUMN_NAME = 'is_active'"
            )
            row = cursor.fetchone()
            return bool(row and row[0] > 0)
    except Exception:
        return True


class CategoryViewSet(viewsets.ModelViewSet):
    """
    API for managing Product Categories.
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [ReadOnlyOrJWTAdmin]
    lookup_field = "id"

    def get_queryset(self):
        qs = super().get_queryset()
        user = get_authenticated_user(self.request)
        if category_has_is_active_column():
            if not (user and user.is_staff):
                qs = qs.filter(is_active=True)
            else:
                is_active_param = self.request.query_params.get("is_active")
                if is_active_param is not None:
                    if is_active_param.lower() in ("true", "1"):
                        qs = qs.filter(is_active=True)
                    elif is_active_param.lower() in ("false", "0"):
                        qs = qs.filter(is_active=False)
        return qs


class ProductViewSet(viewsets.ModelViewSet):
    """
    API for Products. Supports filtering, search, and stock checking.
    Query params:
      - search: filter by name or description
      - category: filter by category ID
      - category_slug: filter by category slug
      - min_price / max_price: filter by price range
      - in_stock: true/false
    """
    queryset = Product.objects.all().select_related("category")
    serializer_class = ProductSerializer
    permission_classes = [ReadOnlyOrJWTAdmin]
    lookup_field = "id"

    def get_queryset(self):
        qs = super().get_queryset()
        user = get_authenticated_user(self.request)
        if not (user and user.is_staff):
            qs = qs.filter(is_active=True)
            if category_has_is_active_column():
                qs = qs.filter(
                    Q(category__isnull=True) | Q(category__is_active=True)
                )
        params = self.request.query_params

        search = params.get("search")
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))

        category_id = params.get("category")
        if category_id:
            qs = qs.filter(category_id=category_id)

        category_slug = params.get("category_slug")
        if category_slug:
            qs = qs.filter(category__slug=category_slug)

        min_price = params.get("min_price")
        if min_price:
            try:
                qs = qs.filter(price__gte=Decimal(min_price))
            except Exception:
                pass

        max_price = params.get("max_price")
        if max_price:
            try:
                qs = qs.filter(price__lte=Decimal(max_price))
            except Exception:
                pass

        in_stock = params.get("in_stock")
        if in_stock is not None:
            if in_stock.lower() in ("true", "1"):
                qs = qs.filter(stock__gt=0)
            elif in_stock.lower() in ("false", "0"):
                qs = qs.filter(stock=0)

        return qs

    @action(detail=False, methods=["GET"])
    def featured(self, request):
        """Return top featured products for React homepage."""
        featured_products = self.get_queryset()[:8]
        serializer = self.get_serializer(featured_products, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# 3. CART APIS (Add to Cart, Update, Remove, Clear)
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([AllowAny])
def view_cart(request):
    """
    Get current cart details with all items, subtotals, and total amount.
    Supports authenticated user or guest session_id.
    """
    cart = get_or_create_cart(request)
    serializer = CartSerializer(cart)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([AllowAny])
def add_to_cart(request):
    """
    Add a product to cart.
    Request body:
      - product_id: int (required)
      - quantity: int (default 1)
      - session_id: str (optional, for guest users)
    """
    serializer = AddToCartSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    product_id = serializer.validated_data["product_id"]
    quantity = serializer.validated_data["quantity"]
    session_id = serializer.validated_data.get("session_id")

    try:
        product = Product.objects.select_related("category").get(id=product_id, is_active=True)
        if category_has_is_active_column() and product.category and not getattr(product.category, "is_active", True):
            raise Product.DoesNotExist
    except Product.DoesNotExist:
        return Response({"detail": "Product not found or inactive"}, status=status.HTTP_404_NOT_FOUND)

    cart = get_or_create_cart(request, session_id_hint=session_id)

    # Check stock
    cart_item = CartItem.objects.filter(cart=cart, product=product).first()
    current_qty = cart_item.quantity if cart_item else 0
    new_qty = current_qty + quantity

    if product.stock < new_qty:
        return Response(
            {
                "detail": f"Only {product.stock} units available in stock. You already have {current_qty} in cart."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if cart_item:
        cart_item.quantity = new_qty
        cart_item.save()
    else:
        cart_item = CartItem.objects.create(cart=cart, product=product, quantity=quantity)

    return Response({
        "message": f"Added {quantity} x '{product.name}' to cart successfully",
        "cart": CartSerializer(cart).data,
    }, status=status.HTTP_200_OK)


@api_view(["PUT", "DELETE"])
@permission_classes([AllowAny])
def cart_item_detail(request, item_id):
    """
    PUT: Update quantity of a cart item.
    DELETE: Remove a specific item from cart.
    """
    cart = get_or_create_cart(request)
    try:
        cart_item = CartItem.objects.get(id=item_id, cart=cart)
    except CartItem.DoesNotExist:
        return Response({"detail": "Cart item not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "PUT":
        serializer = UpdateCartItemSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        qty = serializer.validated_data["quantity"]
        if cart_item.product.stock < qty:
            return Response(
                {"detail": f"Only {cart_item.product.stock} units available in stock"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cart_item.quantity = qty
        cart_item.save()
        return Response({
            "message": "Cart item updated successfully",
            "cart": CartSerializer(cart).data,
        })

    if request.method == "DELETE":
        product_name = cart_item.product.name
        cart_item.delete()
        return Response({
            "message": f"Removed '{product_name}' from cart",
            "cart": CartSerializer(cart).data,
        })


@api_view(["POST"])
@permission_classes([AllowAny])
def clear_cart(request):
    """
    Remove all items from current cart.
    """
    cart = get_or_create_cart(request)
    cart.items.all().delete()
    return Response({
        "message": "Cart cleared successfully",
        "cart": CartSerializer(cart).data,
    })


# ---------------------------------------------------------------------------
# 4. ORDER APIS (Taking Orders)
# ---------------------------------------------------------------------------
@api_view(["POST"])
@permission_classes([AllowAny])
def create_order(request):
    """
    Place an order from the user's cart.
    Automatically:
      1. Validates stock for all items
      2. Creates Order and OrderItems (captures price snapshots)
      3. Decrements product inventory
      4. Creates Payment record in PENDING status
      5. Creates Delivery record in PENDING status
      6. Clears the cart
    """
    serializer = CreateOrderSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    session_id = data.get("session_id")
    cart = get_or_create_cart(request, session_id_hint=session_id)

    cart_items = list(cart.items.select_related("product").all())
    if not cart_items:
        return Response(
            {"detail": "Your cart is empty. Please add products to cart first."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = get_authenticated_user(request)

    with transaction.atomic():
        # Step 1: Validate stock
        for item in cart_items:
            if item.product.stock < item.quantity:
                return Response(
                    {"detail": f"Product '{item.product.name}' has insufficient stock (available: {item.product.stock})"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Step 2: Calculate total amount
        total_amount = sum(item.subtotal for item in cart_items)

        # Step 3: Create Order
        order = Order.objects.create(
            user=user,
            total_amount=total_amount,
            status=Order.Status.PENDING,
            shipping_name=data["shipping_name"],
            shipping_email=data["shipping_email"],
            shipping_phone=data["shipping_phone"],
            shipping_address=data["shipping_address"],
            shipping_city=data["shipping_city"],
            shipping_state=data["shipping_state"],
            shipping_postal_code=data["shipping_postal_code"],
            shipping_country=data.get("shipping_country", "India"),
            notes=data.get("notes", ""),
        )

        # Step 4: Create Order Items and decrement stock
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                product_name=item.product.name,
                price=item.product.price,
                quantity=item.quantity,
                subtotal=item.subtotal,
            )
            item.product.stock -= item.quantity
            item.product.save(update_fields=["stock"])

        # Step 5: Create Payment Record
        payment_method = data.get("payment_method", Payment.Method.UPI)
        Payment.objects.create(
            order=order,
            payment_method=payment_method,
            payment_status=Payment.Status.PENDING,
            amount=total_amount,
        )

        # Step 6: Create Delivery Record
        full_shipping_address = f"{data['shipping_address']}, {data['shipping_city']}, {data['shipping_state']} - {data['shipping_postal_code']}, {data.get('shipping_country', 'India')}"
        estimated_date = (datetime.now(timezone.utc) + timedelta(days=4)).date()
        Delivery.objects.create(
            order=order,
            delivery_address=full_shipping_address,
            estimated_delivery_date=estimated_date,
            status=Delivery.Status.PENDING,
        )

        # Step 7: Clear user cart
        cart.items.all().delete()

    email_notification = send_new_order_notifications(order)

    return Response(
        {
            "message": "Order placed successfully!",
            "order": OrderSerializer(order).data,
            "email_notification": email_notification,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsJWTAuthenticated])
def list_orders(request):
    """
    List orders. Logged-in users see their orders; admin sees all.
    """
    user = get_authenticated_user(request)
    if not user:
        return Response({"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
    if not user.is_staff:
        orders = Order.objects.filter(user=user).select_related("payment", "delivery").prefetch_related("items__product")
    else:
        orders = Order.objects.all().select_related("payment", "delivery").prefetch_related("items__product")

    serializer = OrderSerializer(orders, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsJWTAuthenticated])
def order_detail(request, order_identifier):
    """
    Get order details by order ID or order number (e.g. 'WS-20261028-XXXX').
    """
    base_qs = Order.objects.select_related("payment", "delivery").prefetch_related("items__product")
    if order_identifier.isdigit():
        order = base_qs.filter(id=int(order_identifier)).first()
    else:
        order = base_qs.filter(order_number=order_identifier).first()

    if not order:
        return Response({"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

    user = get_authenticated_user(request)
    if not user.is_staff and order.user_id != user.id:
        return Response({"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

    return Response(OrderSerializer(order).data)


@api_view(["POST"])
@permission_classes([IsJWTAuthenticated])
def cancel_order(request, order_identifier):
    """
    Cancel an order. If order was pending, restores product stock.
    """
    if order_identifier.isdigit():
        order = Order.objects.filter(id=int(order_identifier)).first()
    else:
        order = Order.objects.filter(order_number=order_identifier).first()

    if not order:
        return Response({"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

    user = get_authenticated_user(request)
    if not user.is_staff and order.user_id != user.id:
        return Response({"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

    if order.status in [Order.Status.SHIPPED, Order.Status.DELIVERED]:
        return Response(
            {"detail": f"Cannot cancel order that is already {order.status}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    previous_status = order.status
    with transaction.atomic():
        # Restore stock if order was not yet cancelled
        if order.status != Order.Status.CANCELLED:
            for item in order.items.all():
                if item.product:
                    item.product.stock += item.quantity
                    item.product.save(update_fields=["stock"])

        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status"])

        if hasattr(order, "delivery"):
            order.delivery.status = Delivery.Status.CANCELLED
            order.delivery.save(update_fields=["status"])

    email_notification = send_order_status_notification(order, previous_status)
    return Response({
        "message": f"Order {order.order_number} cancelled successfully",
        "order": OrderSerializer(order).data,
        "email_notification": email_notification,
    })


@api_view(["PATCH"])
@permission_classes([IsJWTAdminUser])
def update_order_status(request, order_identifier):
    if order_identifier.isdigit():
        order = Order.objects.filter(id=int(order_identifier)).first()
    else:
        order = Order.objects.filter(order_number=order_identifier).first()

    if not order:
        return Response({"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = UpdateOrderStatusSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    new_status = serializer.validated_data["status"]
    previous_status = order.status
    with transaction.atomic():
        if new_status == Order.Status.CANCELLED and order.status != Order.Status.CANCELLED:
            if order.status in [Order.Status.SHIPPED, Order.Status.DELIVERED]:
                return Response(
                    {"detail": f"Cannot cancel an order that is already {order.status}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            for item in order.items.select_related("product"):
                if item.product:
                    item.product.stock += item.quantity
                    item.product.save(update_fields=["stock"])
            if hasattr(order, "delivery"):
                order.delivery.status = Delivery.Status.CANCELLED
                order.delivery.save(update_fields=["status"])

        order.status = new_status
        order.save(update_fields=["status", "updated_at"])

    email_notification = send_order_status_notification(order, previous_status)
    return Response({
        "order": OrderSerializer(order).data,
        "email_notification": email_notification,
    })


@api_view(["POST"])
@permission_classes([IsJWTAdminUser])
def resend_order_status_email(request, order_identifier):
    if order_identifier.isdigit():
        order = Order.objects.filter(id=int(order_identifier)).first()
    else:
        order = Order.objects.filter(order_number=order_identifier).first()

    if not order:
        return Response({"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

    email_notification = send_order_status_notification(order, force=True)
    return Response({
        "message": f"Status email requested for order {order.order_number}",
        "email_notification": email_notification,
    })


# ---------------------------------------------------------------------------
# 5. PAYMENT APIS (Payments Entity)
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([IsJWTAuthenticated])
def list_payments(request):
    """
    List all payment records.
    """
    user = get_authenticated_user(request)
    payments = Payment.objects.all().select_related("order")
    if not user.is_staff:
        payments = payments.filter(order__user=user)
    serializer = PaymentSerializer(payments, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsJWTAuthenticated])
def get_payment_by_order(request, order_identifier):
    """
    Get payment status and details for an order.
    """
    if order_identifier.isdigit():
        order = Order.objects.filter(id=int(order_identifier)).first()
    else:
        order = Order.objects.filter(order_number=order_identifier).first()

    if not order or not hasattr(order, "payment"):
        return Response({"detail": "Payment record not found for this order"}, status=status.HTTP_404_NOT_FOUND)

    user = get_authenticated_user(request)
    if not user.is_staff and order.user_id != user.id:
        return Response({"detail": "Payment record not found for this order"}, status=status.HTTP_404_NOT_FOUND)

    return Response(PaymentSerializer(order.payment).data)


@api_view(["POST"])
@permission_classes([IsJWTAdminUser])
def process_payment(request):
    """
    Process/confirm payment for an order.
    Request body:
      - order_id: int or str (Order ID or Order Number)
      - payment_status: 'COMPLETED' | 'FAILED' | 'REFUNDED'
      - transaction_id: str (optional, auto-generated if omitted)
    """
    order_id = request.data.get("order_id") or request.data.get("order_number")
    if not order_id:
        return Response({"detail": "order_id or order_number is required"}, status=status.HTTP_400_BAD_REQUEST)

    if str(order_id).isdigit():
        order = Order.objects.filter(id=int(order_id)).first()
    else:
        order = Order.objects.filter(order_number=str(order_id)).first()

    if not order or not hasattr(order, "payment"):
        return Response({"detail": "Order or payment record not found"}, status=status.HTTP_404_NOT_FOUND)

    payment = order.payment
    new_status = request.data.get("payment_status", Payment.Status.COMPLETED)
    transaction_id = request.data.get("transaction_id")

    previous_order_status = order.status
    with transaction.atomic():
        payment.payment_status = new_status
        if transaction_id:
            payment.transaction_id = transaction_id
        if new_status == Payment.Status.COMPLETED:
            payment.paid_at = datetime.now(timezone.utc)
            order.status = Order.Status.CONFIRMED
            order.save(update_fields=["status"])
        elif new_status == Payment.Status.FAILED:
            order.status = Order.Status.PENDING
            order.save(update_fields=["status"])
        payment.save()

    email_notification = send_order_status_notification(order, previous_order_status)
    return Response({
        "message": f"Payment status updated to '{new_status}'",
        "payment": PaymentSerializer(payment).data,
        "order_status": order.status,
        "email_notification": email_notification,
    })


# ---------------------------------------------------------------------------
# 6. DELIVERY APIS (Delivery Entity)
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([IsJWTAuthenticated])
def list_deliveries(request):
    """
    List all deliveries.
    """
    user = get_authenticated_user(request)
    deliveries = Delivery.objects.all().select_related("order")
    if not user.is_staff:
        deliveries = deliveries.filter(order__user=user)
    serializer = DeliverySerializer(deliveries, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def track_delivery(request, tracking_number):
    """
    Track shipment and delivery status by tracking number (e.g. 'TRK-20261028-XXXXXX').
    Used directly by React tracking page!
    """
    delivery = Delivery.objects.filter(tracking_number=tracking_number).select_related("order").first()
    if not delivery:
        return Response({"detail": "Delivery not found with this tracking number"}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        "tracking_number": delivery.tracking_number,
        "order_number": delivery.order.order_number,
        "courier_partner": delivery.courier_partner,
        "status": delivery.status,
        "delivery_address": delivery.delivery_address,
        "estimated_delivery_date": delivery.estimated_delivery_date,
        "delivered_at": delivery.delivered_at,
        "current_location": delivery.current_location,
        "status_notes": delivery.status_notes,
        "updated_at": delivery.updated_at,
    })


@api_view(["GET"])
@permission_classes([IsJWTAuthenticated])
def get_delivery_by_order(request, order_identifier):
    """
    Get delivery information for an order.
    """
    if order_identifier.isdigit():
        order = Order.objects.filter(id=int(order_identifier)).first()
    else:
        order = Order.objects.filter(order_number=order_identifier).first()

    if not order or not hasattr(order, "delivery"):
        return Response({"detail": "Delivery record not found for this order"}, status=status.HTTP_404_NOT_FOUND)

    user = get_authenticated_user(request)
    if not user.is_staff and order.user_id != user.id:
        return Response({"detail": "Delivery record not found for this order"}, status=status.HTTP_404_NOT_FOUND)

    return Response(DeliverySerializer(order.delivery).data)


@api_view(["PATCH", "POST"])
@permission_classes([IsJWTAdminUser])
def update_delivery_status(request, delivery_id):
    """
    Update delivery status and tracking location.
    Request body:
      - status: PENDING | DISPATCHED | IN_TRANSIT | OUT_FOR_DELIVERY | DELIVERED | RETURNED | CANCELLED
      - current_location: str (optional)
      - status_notes: str (optional)
    """
    delivery = Delivery.objects.filter(id=delivery_id).select_related("order").first()
    if not delivery:
        return Response({"detail": "Delivery record not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = UpdateDeliveryStatusSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    new_status = serializer.validated_data["status"]
    location = serializer.validated_data.get("current_location")
    notes = serializer.validated_data.get("status_notes")

    previous_order_status = delivery.order.status
    with transaction.atomic():
        delivery.status = new_status
        if location:
            delivery.current_location = location
        if notes:
            delivery.status_notes = notes

        # If delivered, mark delivered_at and order status as DELIVERED
        if new_status == Delivery.Status.DELIVERED:
            delivery.delivered_at = datetime.now(timezone.utc)
            delivery.order.status = Order.Status.DELIVERED
            delivery.order.save(update_fields=["status"])
        elif new_status in [Delivery.Status.DISPATCHED, Delivery.Status.IN_TRANSIT, Delivery.Status.OUT_FOR_DELIVERY]:
            delivery.order.status = Order.Status.SHIPPED
            delivery.order.save(update_fields=["status"])

        delivery.save()

    email_notification = send_order_status_notification(
        delivery.order,
        previous_order_status,
    )
    return Response({
        "message": f"Delivery updated to '{new_status}'",
        "delivery": DeliverySerializer(delivery).data,
        "email_notification": email_notification,
    })
