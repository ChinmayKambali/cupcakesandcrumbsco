from fastapi import FastAPI, Header, HTTPException, Path, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
from typing import List, Dict, Any, Optional
from datetime import date
from .database import get_connection
from .email_utils import send_order_email
from .config import ADMIN_KEY, RAZORPAY_KEY_ID
from .payment_utils import create_razorpay_order


class OrderItemIn(BaseModel):
    product_id: int
    quantity: int


class OrderIn(BaseModel):
    customer_name: str
    phone: str
    address: str
    note: Optional[str] = None
    items: List[OrderItemIn]

    @validator("customer_name")
    def validate_customer_name(cls, v: str) -> str:
        name = v.strip()
        if len(name) < 2:
            raise ValueError("Name must be at least 2 characters")
        if not all(ch.isalpha() or ch.isspace() for ch in name):
            raise ValueError("Name can only contain letters and spaces")
        return name

    @validator("address")
    def validate_address(cls, v: str) -> str:
        addr = v.strip()
        if not addr:
            raise ValueError("Address cannot be empty")
        return addr


class PaymentOrderIn(BaseModel):
    customer_name: str
    phone: str
    address: str
    note: Optional[str] = None
    items: List[OrderItemIn]


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/menu")
def get_menu():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, flavour, pack_size, price
        FROM products
        WHERE is_active = TRUE
        ORDER BY id;
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    items: List[Dict[str, Any]] = []
    for pid, name, flavour, pack_size, price in rows:
        items.append(
            {
                "id": pid,
                "name": name,
                "flavour": flavour,
                "pack_size": pack_size,
                "price": price,
            }
        )

    return {"items": items}


@app.post("/api/payment/order")
def create_payment_order(payload: PaymentOrderIn):
    if not payload.items:
        return {"error": "Cart is empty"}

    cleaned_phone = payload.phone.strip()
    if not (len(cleaned_phone) == 10 and cleaned_phone.isdigit()):
        return {"error": "Phone number must be exactly 10 digits"}

    # Reuse name/address validation
    _ = OrderIn(
        customer_name=payload.customer_name,
        phone=payload.phone,
        address=payload.address,
        note=payload.note,
        items=payload.items,
    )

    conn = get_connection()
    cur = conn.cursor()

    total_amount = 0
    try:
        for item in payload.items:
            cur.execute(
                "SELECT price FROM products WHERE id = %s",
                (item.product_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"Invalid product_id {item.product_id}")
            (price,) = row
            total_amount += price * item.quantity
    except Exception as e:
        cur.close()
        conn.close()
        return {"error": str(e)}
    else:
        cur.close()
        conn.close()

    if total_amount <= 0:
        return {"error": "Total amount must be greater than zero"}

    receipt_id = f"order_cart_{cleaned_phone}"
    try:
        rp_order = create_razorpay_order(total_amount, receipt_id)
    except Exception as e:
        return {"error": f"Failed to create Razorpay order: {e}"}

    return {
        "razorpay_key_id": RAZORPAY_KEY_ID,
        "razorpay_order_id": rp_order.get("id"),
        "amount": total_amount,
        "currency": "INR",
        "customer": {
            "name": payload.customer_name,
            "phone": cleaned_phone,
            "address": payload.address,
            "note": payload.note,
        },
    }


@app.post("/api/orders")
def create_order(order: OrderIn, background_tasks: BackgroundTasks):
    if not order.items:
        return {"error": "Cart is empty"}

    cleaned_phone = order.phone.strip()
    if not (len(cleaned_phone) == 10 and cleaned_phone.isdigit()):
        return {"error": "Phone number must be exactly 10 digits"}

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO orders (customer_name, phone, address, note)
            VALUES (%s, %s, %s, %s)
            RETURNING id;
            """,
            (order.customer_name, cleaned_phone, order.address, order.note),
        )
        (order_id,) = cur.fetchone()

        for item in order.items:
            cur.execute(
                "SELECT price FROM products WHERE id = %s",
                (item.product_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"Invalid product_id {item.product_id}")
            (price,) = row
            line_total = price * item.quantity

            cur.execute(
                """
                INSERT INTO order_items (order_id, product_id, quantity, line_total)
                VALUES (%s, %s, %s, %s);
                """,
                (order_id, item.product_id, item.quantity, line_total),
            )

        conn.commit()
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return {"error": str(e)}
    else:
        cur.close()
        conn.close()
        background_tasks.add_task(send_order_email, order_id)
        return {"order_id": order_id, "message": "Order placed"}


@app.get("/api/admin/orders")
def get_admin_orders(x_admin_key: Optional[str] = Header(None)):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            o.id AS order_id,
            o.customer_name,
            o.phone,
            o.address,
            o.created_at,
            o.note,
            p.name AS product_name,
            p.flavour,
            oi.quantity,
            oi.line_total
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.id
        JOIN products p ON p.id = oi.product_id
        WHERE o.status = 'pending'
        ORDER BY o.created_at DESC, o.id, oi.id;
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    orders: Dict[int, Dict[str, Any]] = {}
    for (
        order_id,
        customer_name,
        phone,
        address,
        created_at,
        note,
        product_name,
        flavour,
        quantity,
        line_total,
    ) in rows:
        if order_id not in orders:
            orders[order_id] = {
                "order_id": order_id,
                "customer_name": customer_name,
                "phone": phone,
                "address": address,
                "created_at": created_at.strftime("%d/%m/%Y %H:%M:%S"),
                "note": note,
                "items": [],
            }
        orders[order_id]["items"].append(
            {
                "product_name": product_name,
                "flavour": flavour,
                "quantity": quantity,
                "line_total": line_total,
            }
        )

    return {"orders": list(orders.values())}


@app.post("/api/admin/orders/{order_id}/complete")
def complete_order(
    order_id: int = Path(...),
    x_admin_key: Optional[str] = Header(None),
):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE orders
            SET status = 'completed'
            WHERE id = %s;
            """,
            (order_id,),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    return {"message": f"Order {order_id} marked as completed"}


@app.get("/api/admin/analytics")
def get_admin_analytics(
    x_admin_key: Optional[str] = Header(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    conn = get_connection()
    cur = conn.cursor()

    where_clauses = []
    params_summary: List[Any] = []
    params_weeks: List[Any] = []
    params_products: List[Any] = []

    if from_date is not None:
        where_clauses.append("o.created_at::date >= %s")
        params_summary.append(from_date)
        params_weeks.append(from_date)
        params_products.append(from_date)

    if to_date is not None:
        where_clauses.append("o.created_at::date <= %s")
        params_summary.append(to_date)
        params_weeks.append(to_date)
        params_products.append(to_date)

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    cur.execute(
        f"""
        SELECT
            COUNT(DISTINCT o.id) AS total_orders,
            COALESCE(SUM(oi.line_total), 0) AS total_revenue
        FROM orders o
        LEFT JOIN order_items oi ON oi.order_id = o.id
        {where_sql};
        """,
        params_summary,
    )
    total_orders, total_revenue = cur.fetchone()

    cur.execute(
        f"""
        SELECT
            date_trunc('week', o.created_at)::date AS week_start,
            COUNT(DISTINCT o.id) AS order_count,
            COALESCE(SUM(oi.line_total), 0) AS revenue
        FROM orders o
        LEFT JOIN order_items oi ON oi.order_id = o.id
        {where_sql}
        GROUP BY week_start
        ORDER BY week_start DESC
        LIMIT 8;
        """,
        params_weeks,
    )
    week_rows = cur.fetchall()

    cur.execute(
        f"""
        SELECT
            p.name AS product_name,
            p.flavour,
            SUM(oi.quantity) AS total_quantity,
            SUM(oi.line_total) AS total_revenue
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        JOIN products p ON p.id = oi.product_id
        {where_sql}
        GROUP BY product_name, p.flavour
        ORDER BY total_quantity DESC
        LIMIT 10;
        """,
        params_products,
    )
    product_rows = cur.fetchall()

    cur.close()
    conn.close()

    orders_per_week = []
    for week_start, order_count, revenue in week_rows:
        orders_per_week.append(
            {
                "week_start": week_start.strftime("%d/%m/%Y"),
                "order_count": order_count,
                "revenue": revenue,
            }
        )

    top_products = []
    for product_name, flavour, total_quantity, prod_revenue in product_rows:
        top_products.append(
            {
                "product_name": product_name,
                "flavour": flavour,
                "total_quantity": total_quantity,
                "total_revenue": prod_revenue,
            }
        )

    return {
        "summary": {
            "total_orders": total_orders,
            "total_revenue": total_revenue,
        },
        "orders_per_week": orders_per_week,
        "top_products": top_products,
    }
