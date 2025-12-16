import smtplib
from email.mime.text import MIMEText
from .database import get_connection
from .config import (
    EMAIL_HOST,
    EMAIL_PORT,
    EMAIL_USER,
    EMAIL_PASS,
    EMAIL_FROM,
    EMAIL_TO,
)


def build_order_email_body(order_id: int) -> str:
    """
    Build a simple text summary of the order using data from the database.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT customer_name, phone, address, created_at, note
        FROM orders
        WHERE id = %s;
        """,
        (order_id,),
    )
    row = cur.fetchone()
    if row is None:
        cur.close()
        conn.close()
        return f"Order {order_id} not found."

    customer_name, phone, address, created_at, note = row
    created_str = created_at.strftime("%d/%m/%Y %H:%M:%S")

    cur.execute(
        """
        SELECT p.name, p.flavour, oi.quantity, oi.line_total
        FROM order_items oi
        JOIN products p ON p.id = oi.product_id
        WHERE oi.order_id = %s;
        """,
        (order_id,),
    )
    items_rows = cur.fetchall()

    cur.close()
    conn.close()

    lines = []
    lines.append(f"New order #{order_id}")
    lines.append(f"Time: {created_str}")
    lines.append(f"Customer: {customer_name}")
    lines.append(f"Phone: {phone}")
    lines.append(f"Address: {address}")
    if note:
        lines.append(f"Note: {note}")
    lines.append("")
    lines.append("Items:")

    total = 0
    for name, flavour, quantity, line_total in items_rows:
        flavour_str = f" ({flavour})" if flavour else ""
        lines.append(f"- {name}{flavour_str} x {quantity} = ₹{line_total}")
        total += line_total

    lines.append("")
    lines.append(f"Total: ₹{total}")

    return "\n".join(lines)


def send_order_email(order_id: int) -> None:
    """
    Send an email notification for the given order id.
    """
    if not (EMAIL_HOST and EMAIL_USER and EMAIL_PASS and EMAIL_FROM and EMAIL_TO):
        # Missing config; skip sending to avoid crashes.
        return

    body = build_order_email_body(order_id)
    subject = f"New order #{order_id} – Cupcakes & Crumbs Co"

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
