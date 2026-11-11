import logging
import smtplib

from django.conf import settings
from django.core.mail import send_mail

from app.models import Order

logger = logging.getLogger(__name__)

NOTIFIABLE_ORDER_STATUSES = {
    Order.Status.CONFIRMED,
    Order.Status.PROCESSING,
    Order.Status.SHIPPED,
    Order.Status.DELIVERED,
    Order.Status.CANCELLED,
}


def send_order_status_notification(order, previous_status=None, force=False):
    if order.status not in NOTIFIABLE_ORDER_STATUSES:
        return "not_needed"
    if not force and order.status == previous_status:
        return "not_needed"

    if settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
        logger.warning(
            "Order status email for %s was logged to the console, not delivered to %s",
            order.order_number,
            order.shipping_email,
        )
        return "logged"

    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        logger.error(
            "Order status email for %s was not sent: SMTP credentials are not configured",
            order.order_number,
        )
        return "not_configured"

    subject = f"Order {order.order_number}: {order.get_status_display()}"
    message = (
        f"Hello {order.shipping_name},\n\n"
        f"The status of your WebSale order {order.order_number} is now "
        f"{order.get_status_display()}.\n\n"
        f"Order total: ₹{order.total_amount}\n"
        "Thank you for shopping with us."
    )
    try:
        sent_count = send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [order.shipping_email],
            fail_silently=False,
        )
    except (OSError, smtplib.SMTPException):
        logger.exception(
            "Could not send status email for order %s to %s",
            order.order_number,
            order.shipping_email,
        )
        return "failed"

    if sent_count != 1:
        logger.error(
            "Status email was not sent for order %s to %s",
            order.order_number,
            order.shipping_email,
        )
        return "failed"

    return "sent"
