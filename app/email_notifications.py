import logging
import smtplib

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from app.models import Order

logger = logging.getLogger(__name__)

NOTIFIABLE_ORDER_STATUSES = {
    Order.Status.CONFIRMED,
    Order.Status.PROCESSING,
    Order.Status.SHIPPED,
    Order.Status.DELIVERED,
    Order.Status.CANCELLED,
}


def _send_email_with_html(subject, text_body, html_body, recipient):
    """
    Sends an email with both plain text and rich HTML alternatives.
    """
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    if html_body:
        msg.attach_alternative(html_body, "text/html")
    return msg.send(fail_silently=False)


def format_order_items_text(order):
    items = list(order.items.all())
    if not items:
        return "  (No item details recorded)"
    lines = []
    for idx, item in enumerate(items, start=1):
        price = f"₹{item.price}" if item.price is not None else "—"
        subtotal = f"₹{item.subtotal}" if item.subtotal is not None else "—"
        lines.append(f"  {idx}. {item.product_name} | Qty: {item.quantity} | Price: {price} | Subtotal: {subtotal}")
    return "\n".join(lines)


def format_order_items_html(order):
    items = list(order.items.all())
    if not items:
        return "<p style='color: #64748b; font-style: italic;'>No item details recorded.</p>"
    rows = []
    for idx, item in enumerate(items, start=1):
        price = f"₹{item.price}" if item.price is not None else "—"
        subtotal = f"₹{item.subtotal}" if item.subtotal is not None else "—"
        img_html = ""
        if hasattr(item, "product") and item.product and getattr(item.product, "image_url", None):
            url = item.product.image_url
            if url.startswith("http") or url.startswith("data:image"):
                img_html = f"<img src='{url}' alt='' style='width: 36px; height: 36px; object-fit: cover; border-radius: 4px; vertical-align: middle; margin-right: 8px;' />"
        rows.append(f"""
          <tr style='border-bottom: 1px solid #e2e8f0;'>
            <td style='padding: 10px 12px; font-size: 14px; color: #1e293b;'>
              {img_html}<strong>{item.product_name}</strong>
            </td>
            <td style='padding: 10px 12px; font-size: 14px; text-align: center; color: #1e293b;'>
              <strong>{item.quantity}</strong>
            </td>
            <td style='padding: 10px 12px; font-size: 14px; text-align: right; color: #475569;'>
              {price}
            </td>
            <td style='padding: 10px 12px; font-size: 14px; text-align: right; color: #0f172a;'>
              <strong>{subtotal}</strong>
            </td>
          </tr>
        """)
    return f"""
    <table style='width: 100%; border-collapse: collapse; margin: 12px 0; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; overflow: hidden;'>
      <thead>
        <tr style='background-color: #f1f5f9; text-align: left;'>
          <th style='padding: 10px 12px; font-size: 13px; color: #334155; border-bottom: 2px solid #cbd5e1;'>Item</th>
          <th style='padding: 10px 12px; font-size: 13px; color: #334155; text-align: center; border-bottom: 2px solid #cbd5e1;'>Qty</th>
          <th style='padding: 10px 12px; font-size: 13px; color: #334155; text-align: right; border-bottom: 2px solid #cbd5e1;'>Unit Price</th>
          <th style='padding: 10px 12px; font-size: 13px; color: #334155; text-align: right; border-bottom: 2px solid #cbd5e1;'>Subtotal</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
    """


def format_payment_details_text(order):
    payment = getattr(order, "payment", None)
    payment_method = "Unknown"
    payment_status = "Pending"
    if payment:
        payment_method = getattr(payment, "get_payment_method_display", lambda: payment.payment_method)()
        payment_status = getattr(payment, "get_payment_status_display", lambda: payment.payment_status)()

    lines = [
        f"  Total Amount   : ₹{order.total_amount}",
        f"  Payment Method : {payment_method}",
        f"  Payment Status : {payment_status}",
    ]
    if payment and payment.transaction_id:
        lines.append(f"  Transaction ID : {payment.transaction_id}")
    return "\n".join(lines)


def format_payment_details_html(order):
    payment = getattr(order, "payment", None)
    payment_method = "Unknown"
    payment_status = "Pending"
    txn_row = ""
    paid_row = ""
    if payment:
        payment_method = getattr(payment, "get_payment_method_display", lambda: payment.payment_method)()
        payment_status = getattr(payment, "get_payment_status_display", lambda: payment.payment_status)()
        if payment.transaction_id:
            txn_row = f"<tr><td style='padding: 4px 0; color: #475569;'>Transaction ID:</td><td style='padding: 4px 0; text-align: right; color: #0f172a;'><strong>{payment.transaction_id}</strong></td></tr>"
        if payment.paid_at:
            paid_row = f"<tr><td style='padding: 4px 0; color: #475569;'>Paid At:</td><td style='padding: 4px 0; text-align: right; color: #0f172a;'><strong>{payment.paid_at.strftime('%d %b %Y, %I:%M %p UTC')}</strong></td></tr>"

    return f"""
    <div style='background-color: #f8fafc; border: 1px solid #cbd5e1; border-left: 5px solid #2563eb; padding: 14px 18px; border-radius: 6px; margin: 12px 0;'>
      <table style='width: 100%; border-collapse: collapse; font-size: 14px;'>
        <tr>
          <td style='padding: 4px 0; color: #334155; font-size: 15px;'><strong>Total Payment Amount:</strong></td>
          <td style='padding: 4px 0; text-align: right; font-size: 18px; color: #0f172a;'><strong>₹{order.total_amount}</strong></td>
        </tr>
        <tr>
          <td style='padding: 4px 0; color: #475569;'>Payment Method:</td>
          <td style='padding: 4px 0; text-align: right; color: #0f172a;'><strong>{payment_method}</strong></td>
        </tr>
        <tr>
          <td style='padding: 4px 0; color: #475569;'>Payment Status:</td>
          <td style='padding: 4px 0; text-align: right; color: #0f172a;'><strong>{payment_status}</strong></td>
        </tr>
        {txn_row}
        {paid_row}
      </table>
    </div>
    """


def format_shipping_details_text(order):
    return (
        f"  Name    : {order.shipping_name}\n"
        f"  Email   : {order.shipping_email}\n"
        f"  Phone   : {order.shipping_phone}\n"
        f"  Address : {order.shipping_address}, {order.shipping_city}, "
        f"{order.shipping_state} - {order.shipping_postal_code}, {order.shipping_country}"
    )


def format_shipping_details_html(order):
    notes_html = f"<div style='margin-top: 6px; color: #334155;'><strong>Notes:</strong> {order.notes}</div>" if order.notes else ""
    return f"""
    <div style='background-color: #ffffff; border: 1px solid #cbd5e1; padding: 14px 18px; border-radius: 6px; margin: 12px 0; font-size: 14px; line-height: 1.6;'>
      <div style='margin-bottom: 6px;'><strong style='font-size: 16px; color: #0f172a;'>{order.shipping_name}</strong></div>
      <div style='color: #334155;'><strong>Email:</strong> <a href='mailto:{order.shipping_email}' style='color: #2563eb; text-decoration: none;'><strong>{order.shipping_email}</strong></a></div>
      <div style='color: #334155;'><strong>Phone:</strong> <a href='tel:{order.shipping_phone}' style='color: #2563eb; text-decoration: none;'><strong>{order.shipping_phone}</strong></a></div>
      <div style='color: #334155; margin-top: 6px;'>
        <strong>Delivery Address:</strong><br />
        {order.shipping_address}<br />
        {order.shipping_city}, {order.shipping_state} - {order.shipping_postal_code}<br />
        {order.shipping_country}
      </div>
      {notes_html}
    </div>
    """


def format_delivery_details_html(order):
    if not hasattr(order, "delivery") or not order.delivery:
        return ""
    d = order.delivery
    est_row = f"<tr><td style='padding: 4px 0; color: #475569;'>Estimated Delivery:</td><td style='padding: 4px 0; text-align: right; color: #0f172a;'><strong>{d.estimated_delivery_date}</strong></td></tr>" if d.estimated_delivery_date else ""
    loc_row = f"<tr><td style='padding: 4px 0; color: #475569;'>Current Location:</td><td style='padding: 4px 0; text-align: right; color: #0f172a;'><strong>{d.current_location}</strong></td></tr>" if d.current_location else ""
    notes_row = f"<tr><td style='padding: 4px 0; color: #475569;'>Status Notes:</td><td style='padding: 4px 0; text-align: right; color: #0f172a;'><strong>{d.status_notes}</strong></td></tr>" if d.status_notes else ""
    delivered_row = f"<tr><td style='padding: 4px 0; color: #475569;'>Delivered At:</td><td style='padding: 4px 0; text-align: right; color: #0f172a;'><strong>{d.delivered_at.strftime('%d %b %Y, %I:%M %p UTC')}</strong></td></tr>" if d.delivered_at else ""

    return f"""
    <div style='background-color: #faf5ff; border: 1px solid #e9d5ff; border-left: 5px solid #9333ea; padding: 14px 18px; border-radius: 6px; margin: 12px 0;'>
      <h4 style='margin: 0 0 8px 0; color: #581c87; font-size: 15px;'><strong>Delivery & Tracking Details</strong></h4>
      <table style='width: 100%; border-collapse: collapse; font-size: 14px;'>
        <tr>
          <td style='padding: 4px 0; color: #475569;'>Courier Partner:</td>
          <td style='padding: 4px 0; text-align: right; color: #0f172a;'><strong>{d.courier_partner}</strong></td>
        </tr>
        <tr>
          <td style='padding: 4px 0; color: #475569;'>Tracking Number:</td>
          <td style='padding: 4px 0; text-align: right; color: #0f172a;'><strong>{d.tracking_number or 'Pending'}</strong></td>
        </tr>
        <tr>
          <td style='padding: 4px 0; color: #475569;'>Delivery Status:</td>
          <td style='padding: 4px 0; text-align: right; color: #0f172a;'><strong>{d.get_status_display()}</strong></td>
        </tr>
        {est_row}
        {loc_row}
        {notes_row}
        {delivered_row}
      </table>
    </div>
    """


def send_new_order_notifications(order):
    """
    Sent when a customer places an order.
    Notifies Admin with complete item list, payment amount, and customer details.
    Sends confirmation to Customer with complete item list and order summary in bold formatting.
    """
    if settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
        logger.warning(
            "New order email for %s was logged to the console, not delivered",
            order.order_number,
        )
        return "logged"

    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        logger.error(
            "New order email for %s was not sent: SMTP credentials are not configured",
            order.order_number,
        )
        return "not_configured"

    admin_email = getattr(settings, "ADMIN_EMAIL", settings.DEFAULT_FROM_EMAIL)
    items_text = format_order_items_text(order)
    payment_text = format_payment_details_text(order)
    shipping_text = format_shipping_details_text(order)

    items_html = format_order_items_html(order)
    payment_html = format_payment_details_html(order)
    shipping_html = format_shipping_details_html(order)
    delivery_html = format_delivery_details_html(order)

    # 1. ADMIN EMAIL (Complete detail format)
    admin_subject = f"[Admin Alert] New Order #{order.order_number} Received - Total: ₹{order.total_amount}"
    admin_text = (
        f"Hello Admin,\n\n"
        f"A new order has been placed on WebSale!\n\n"
        f"==================================================\n"
        f"ORDER SUMMARY\n"
        f"==================================================\n"
        f"Order Number : {order.order_number}\n"
        f"Order Status : {order.get_status_display()}\n\n"
        f"==================================================\n"
        f"ORDERED ITEMS LIST\n"
        f"==================================================\n"
        f"{items_text}\n\n"
        f"==================================================\n"
        f"PAYMENT DETAILS\n"
        f"==================================================\n"
        f"{payment_text}\n\n"
        f"==================================================\n"
        f"CUSTOMER & SHIPPING DETAILS\n"
        f"==================================================\n"
        f"{shipping_text}\n"
        f"  Notes   : {order.notes or 'None'}\n\n"
        f"Log in to the WebSale Admin Panel to process this order.\n"
    )

    admin_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8" /></head>
    <body style="font-family: Arial, Helvetica, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #1e293b;">
      <div style="max-width: 650px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #cbd5e1; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
        <div style="background-color: #0f172a; color: #ffffff; padding: 20px 24px;">
          <h2 style="margin: 0; font-size: 20px;">[Admin Alert] New Order Received</h2>
          <p style="margin: 6px 0 0 0; font-size: 14px; color: #94a3b8;">Order <strong>#{order.order_number}</strong> &bull; Total: <strong>₹{order.total_amount}</strong></p>
        </div>
        <div style="padding: 24px;">
          <p style="font-size: 15px; margin-top: 0;">Hello <strong>Admin</strong>, a new order has been placed on WebSale.</p>

          <h3 style="font-size: 16px; color: #0f172a; margin: 20px 0 8px 0; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">Customer & Shipping Details</h3>
          {shipping_html}

          <h3 style="font-size: 16px; color: #0f172a; margin: 24px 0 8px 0; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">Ordered Items List</h3>
          {items_html}

          <h3 style="font-size: 16px; color: #0f172a; margin: 24px 0 8px 0; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">Payment Details</h3>
          {payment_html}

          {delivery_html}

          <div style="margin-top: 28px; text-align: center;">
            <p style="font-size: 13px; color: #64748b; margin-bottom: 0;">WebSale E-Commerce Admin Notification</p>
          </div>
        </div>
      </div>
    </body>
    </html>
    """

    # 2. CUSTOMER EMAIL (Bold Name, Items, Payment, and Confirmation)
    customer_subject = f"Order Confirmation - #{order.order_number} | WebSale"
    customer_text = (
        f"Hello {order.shipping_name},\n\n"
        f"Thank you for shopping with WebSale! We have received your order #{order.order_number}.\n\n"
        f"Order Confirmation Status: CONFIRMED\n\n"
        f"==================================================\n"
        f"ITEMS IN YOUR ORDER\n"
        f"==================================================\n"
        f"{items_text}\n\n"
        f"==================================================\n"
        f"PAYMENT SUMMARY\n"
        f"==================================================\n"
        f"{payment_text}\n\n"
        f"We will notify you via email as your order is confirmed, processed, and shipped.\n\n"
        f"Thank you for choosing WebSale!\n"
    )

    customer_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8" /></head>
    <body style="font-family: Arial, Helvetica, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #1e293b;">
      <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #cbd5e1; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
        <div style="background-color: #2563eb; color: #ffffff; padding: 24px; text-align: center;">
          <h1 style="margin: 0; font-size: 22px; font-weight: bold;">Order Confirmation</h1>
          <p style="margin: 8px 0 0 0; font-size: 15px;">Order <strong>#{order.order_number}</strong> is <strong>CONFIRMED</strong></p>
        </div>
        <div style="padding: 24px;">
          <p style="font-size: 16px; margin-top: 0;">
            Hello <strong>{order.shipping_name}</strong>,
          </p>
          <p style="font-size: 14px; color: #334155; line-height: 1.5;">
            Thank you for shopping with WebSale! Your order confirmation for <strong>#{order.order_number}</strong> is <strong>CONFIRMED</strong>.
          </p>

          <h3 style="font-size: 16px; color: #0f172a; margin: 24px 0 8px 0; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">
            <strong>Items in Your Order</strong>
          </h3>
          {items_html}

          <h3 style="font-size: 16px; color: #0f172a; margin: 24px 0 8px 0; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">
            <strong>Payment Summary</strong>
          </h3>
          {payment_html}

          <div style="margin-top: 24px; padding: 14px; background-color: #f8fafc; border-radius: 6px; text-align: center; font-size: 13px; color: #64748b;">
            We will email you once your order is processed and shipped.<br />
            Thank you for shopping with <strong>WebSale</strong>!
          </div>
        </div>
      </div>
    </body>
    </html>
    """

    try:
        sent_admin = _send_email_with_html(admin_subject, admin_text, admin_html, admin_email)
        sent_customer = _send_email_with_html(customer_subject, customer_text, customer_html, order.shipping_email)
        return "sent" if (sent_admin or sent_customer) else "failed"
    except (OSError, smtplib.SMTPException):
        logger.exception(
            "Could not send new order notification for order %s",
            order.order_number,
        )
        return "failed"


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

    items_text = format_order_items_text(order)
    payment_text = format_payment_details_text(order)
    shipping_text = format_shipping_details_text(order)

    items_html = format_order_items_html(order)
    payment_html = format_payment_details_html(order)
    shipping_html = format_shipping_details_html(order)
    delivery_html = format_delivery_details_html(order)

    delivery_info = ""
    if hasattr(order, "delivery") and order.delivery:
        d = order.delivery
        delivery_lines = [
            f"  Courier Partner : {d.courier_partner}",
            f"  Tracking Number : {d.tracking_number or 'Pending'}",
            f"  Delivery Status : {d.get_status_display()}",
        ]
        if d.estimated_delivery_date:
            delivery_lines.append(f"  Estimated Date  : {d.estimated_delivery_date}")
        if d.current_location:
            delivery_lines.append(f"  Current Location: {d.current_location}")
        delivery_info = "==================================================\nDELIVERY & TRACKING\n==================================================\n" + "\n".join(delivery_lines) + "\n\n"

    # 1. CUSTOMER STATUS EMAIL (Customer name, items, payment, and status in bold)
    customer_subject = f"Order {order.order_number}: {order.get_status_display()}"
    customer_text = (
        f"Hello {order.shipping_name},\n\n"
        f"The status of your WebSale order {order.order_number} is now "
        f"{order.get_status_display()}.\n\n"
        f"Order Confirmation Status: {order.get_status_display()}\n\n"
        f"==================================================\n"
        f"ITEMS ORDERED\n"
        f"==================================================\n"
        f"{items_text}\n\n"
        f"==================================================\n"
        f"PAYMENT SUMMARY\n"
        f"==================================================\n"
        f"{payment_text}\n\n"
        f"{delivery_info}"
        f"Thank you for shopping with WebSale."
    )

    customer_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8" /></head>
    <body style="font-family: Arial, Helvetica, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #1e293b;">
      <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #cbd5e1; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
        <div style="background-color: #2563eb; color: #ffffff; padding: 24px; text-align: center;">
          <h1 style="margin: 0; font-size: 22px; font-weight: bold;">Order Status Update</h1>
          <p style="margin: 8px 0 0 0; font-size: 16px;">Order <strong>#{order.order_number}</strong> is <strong>{order.get_status_display().upper()}</strong></p>
        </div>
        <div style="padding: 24px;">
          <p style="font-size: 16px; margin-top: 0;">
            Hello <strong>{order.shipping_name}</strong>,
          </p>
          <p style="font-size: 14px; color: #334155; line-height: 1.5;">
            The confirmation status of your WebSale order <strong>#{order.order_number}</strong> is now <strong>{order.get_status_display()}</strong>.
          </p>

          <h3 style="font-size: 16px; color: #0f172a; margin: 24px 0 8px 0; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">
            <strong>Items in Your Order</strong>
          </h3>
          {items_html}

          <h3 style="font-size: 16px; color: #0f172a; margin: 24px 0 8px 0; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">
            <strong>Payment Summary</strong>
          </h3>
          {payment_html}

          {delivery_html}

          <div style="margin-top: 24px; padding: 14px; background-color: #f8fafc; border-radius: 6px; text-align: center; font-size: 13px; color: #64748b;">
            Thank you for shopping with <strong>WebSale</strong>!
          </div>
        </div>
      </div>
    </body>
    </html>
    """

    try:
        sent_count = _send_email_with_html(
            customer_subject,
            customer_text,
            customer_html,
            order.shipping_email,
        )

        # Also send detailed alert to Admin so admin knows all updated details
        admin_email = getattr(settings, "ADMIN_EMAIL", settings.DEFAULT_FROM_EMAIL)
        if admin_email and admin_email.lower() != order.shipping_email.lower():
            admin_subject = f"[Admin Alert] Order #{order.order_number} Status: {order.get_status_display()}"
            admin_text = (
                f"Hello Admin,\n\n"
                f"WebSale Order #{order.order_number} status has been updated to: {order.get_status_display()}.\n\n"
                f"==================================================\n"
                f"CUSTOMER & SHIPPING DETAILS\n"
                f"==================================================\n"
                f"{shipping_text}\n\n"
                f"==================================================\n"
                f"ORDERED ITEMS LIST\n"
                f"==================================================\n"
                f"{items_text}\n\n"
                f"==================================================\n"
                f"PAYMENT DETAILS\n"
                f"==================================================\n"
                f"{payment_text}\n\n"
                f"{delivery_info}"
                f"Log in to the WebSale Admin Panel to view and manage this order.\n"
            )

            admin_html = f"""
            <!DOCTYPE html>
            <html>
            <head><meta charset="utf-8" /></head>
            <body style="font-family: Arial, Helvetica, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #1e293b;">
              <div style="max-width: 650px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #cbd5e1; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
                <div style="background-color: #0f172a; color: #ffffff; padding: 20px 24px;">
                  <h2 style="margin: 0; font-size: 20px;">[Admin Alert] Order Status Updated</h2>
                  <p style="margin: 6px 0 0 0; font-size: 14px; color: #94a3b8;">Order <strong>#{order.order_number}</strong> is now <strong>{order.get_status_display().upper()}</strong></p>
                </div>
                <div style="padding: 24px;">
                  <p style="font-size: 15px; margin-top: 0;">Hello <strong>Admin</strong>, Order <strong>#{order.order_number}</strong> has been updated to <strong>{order.get_status_display()}</strong>.</p>

                  <h3 style="font-size: 16px; color: #0f172a; margin: 20px 0 8px 0; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">Customer & Shipping Details</h3>
                  {shipping_html}

                  <h3 style="font-size: 16px; color: #0f172a; margin: 24px 0 8px 0; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">Ordered Items List</h3>
                  {items_html}

                  <h3 style="font-size: 16px; color: #0f172a; margin: 24px 0 8px 0; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">Payment Details</h3>
                  {payment_html}

                  {delivery_html}

                  <div style="margin-top: 28px; text-align: center;">
                    <p style="font-size: 13px; color: #64748b; margin-bottom: 0;">WebSale E-Commerce Admin Notification</p>
                  </div>
                </div>
              </div>
            </body>
            </html>
            """
            try:
                _send_email_with_html(
                    admin_subject,
                    admin_text,
                    admin_html,
                    admin_email,
                )
            except Exception:
                logger.exception("Could not send status copy to admin %s", admin_email)
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
