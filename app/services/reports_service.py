from datetime import date, datetime, time
from io import BytesIO, StringIO
import csv

from fastapi import HTTPException, status

from app.repositories.reports_repository import list_orders_between, list_transactions_by_order_ids


def _ensure_valid_range(desde: date, hasta: date) -> None:
    if desde > hasta:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El rango de fechas es inválido: 'desde' no puede ser mayor que 'hasta'",
        )


def _to_datetime_range(desde: date, hasta: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(desde, time.min),
        datetime.combine(hasta, time.max),
    )


async def build_orders_csv(*, desde: date, hasta: date) -> bytes:
    _ensure_valid_range(desde, hasta)
    desde_dt, hasta_dt = _to_datetime_range(desde, hasta)

    orders = await list_orders_between(desde_dt=desde_dt, hasta_dt=hasta_dt)
    tx_map = await list_transactions_by_order_ids([order["_id"] for order in orders])

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "orderId",
        "userId",
        "estado",
        "total",
        "cantidadItems",
        "createdAt",
        "updatedAt",
        "provider",
        "paymentStatus",
        "providerRef",
    ])

    for order in orders:
        tx = tx_map.get(order["_id"], {})
        writer.writerow([
            order.get("_id", ""),
            order.get("userId", ""),
            order.get("estado", ""),
            order.get("total", 0),
            len(order.get("items", [])),
            order.get("createdAt", ""),
            order.get("updatedAt", ""),
            tx.get("provider", ""),
            tx.get("status", ""),
            tx.get("providerRef", ""),
        ])

    return buffer.getvalue().encode("utf-8")


async def build_sales_pdf(*, desde: date, hasta: date) -> bytes:
    _ensure_valid_range(desde, hasta)

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except Exception as ex:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo generar PDF. Instala dependencia: reportlab",
        ) from ex

    desde_dt, hasta_dt = _to_datetime_range(desde, hasta)
    orders = await list_orders_between(desde_dt=desde_dt, hasta_dt=hasta_dt)

    total_orders = len(orders)
    total_amount = round(sum(float(o.get("total", 0)) for o in orders), 2)
    paid_orders = [o for o in orders if o.get("estado") == "PAGADA"]
    paid_amount = round(sum(float(o.get("total", 0)) for o in paid_orders), 2)

    out = BytesIO()
    pdf = canvas.Canvas(out, pagesize=letter)
    width, height = letter

    y = height - 50
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, y, "Colficultor - Reporte de ventas")

    y -= 22
    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, y, f"Rango: {desde.isoformat()} a {hasta.isoformat()}")

    y -= 18
    pdf.drawString(40, y, f"Total ordenes: {total_orders}")
    y -= 16
    pdf.drawString(40, y, f"Total vendido (todas): {total_amount}")
    y -= 16
    pdf.drawString(40, y, f"Ordenes pagadas: {len(paid_orders)}")
    y -= 16
    pdf.drawString(40, y, f"Total pagado: {paid_amount}")

    y -= 24
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(40, y, "Ultimas ordenes en rango")

    y -= 16
    pdf.setFont("Helvetica", 9)
    for order in orders[:25]:
        line = (
            f"{order.get('_id', '')[:8]}... "
            f"estado={order.get('estado', '')} "
            f"total={order.get('total', 0)}"
        )
        pdf.drawString(40, y, line)
        y -= 13
        if y <= 40:
            pdf.showPage()
            y = height - 40
            pdf.setFont("Helvetica", 9)

    pdf.save()
    out.seek(0)
    return out.read()
