import razorpay
from .config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET

if not (RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET):
    client = None
else:
    client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


def create_razorpay_order(amount_in_rupees: int, receipt_id: str) -> dict:
    """
    Create a Razorpay order in TEST mode.
    amount_in_rupees: integer rupees (e.g. 360)
    """
    if client is None:
        raise RuntimeError("Razorpay keys not configured")

    amount_paise = amount_in_rupees * 100  # Razorpay uses paise

    order = client.order.create(
        dict(
            amount=amount_paise,
            currency="INR",
            receipt=receipt_id,
            payment_capture=1,
        )
    )
    return order
