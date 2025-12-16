import os
import resend
from .database import get_connection
from .config import EMAIL_FROM, EMAIL_TO  # keep if you already define them in config.py

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
resend.api_key = RESEND_API_KEY


def build_order_email_body(order_id: int) -> str:
    # keep your existing implementation exactly as it is
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
    New version: same signature as your old code (takes order_id),
    but sends via Resend using the text body built above.
    """
    if not RESEND_API_KEY or not EMAIL_FROM or not EMAIL_TO:
        return  # avoid crashing if not configured

    body = build_order_email_body(order_id)
    subject = f"New order #{order_id}"

    resend.Emails.send({
        "from": EMAIL_FROM,
        "to": [EMAIL_TO],
        "subject": subject,
        "text": body,  # plain text is fine here
    })
