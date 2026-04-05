from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO, StringIO
import csv

from fastapi import HTTPException, status

from app.repositories.reports_repository import list_orders_between, list_transactions_by_order_ids
from app.services.orders_service import list_sales

TZ_UTC_MINUS_5 = timezone(timedelta(hours=-5))
TZ_UTC = timezone.utc


def _ensure_valid_range(desde: date, hasta: date) -> None:
    if desde > hasta:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El rango de fechas es inválido: 'desde' no puede ser mayor que 'hasta'",
        )


def _to_datetime_range(desde: date, hasta: date) -> tuple[datetime, datetime]:
    # Interpretar fechas en UTC-5 (Colombia) y convertir a UTC para consultar Mongo.
    desde_local = datetime.combine(desde, time.min).replace(tzinfo=TZ_UTC_MINUS_5)
    hasta_local = datetime.combine(hasta, time.max).replace(tzinfo=TZ_UTC_MINUS_5)
    desde_utc = desde_local.astimezone(TZ_UTC).replace(tzinfo=None)
    hasta_utc = hasta_local.astimezone(TZ_UTC).replace(tzinfo=None)
    return (desde_utc, hasta_utc)


def _parse_order_created_at(raw: object) -> datetime | None:
    if isinstance(raw, datetime):
        if raw.tzinfo is not None:
            return raw.astimezone(TZ_UTC).replace(tzinfo=None)
        return raw
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return None
    return None


def _is_paid_like_status(status_value: str) -> bool:
    return status_value in {"PAGADA", "EN_PREPARACION", "ENVIADA", "ENTREGADA"}


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


async def _get_farmer_sales_in_range(
    *,
    caficultor_id: str,
    desde: date,
    hasta: date,
) -> list[dict]:
    _ensure_valid_range(desde, hasta)
    desde_dt, hasta_dt = _to_datetime_range(desde, hasta)
    sales = await list_sales(caficultor_id)

    filtered: list[dict] = []
    for order in sales:
        created_at = _parse_order_created_at(order.get("createdAt"))
        if created_at is None:
            continue
        if desde_dt <= created_at <= hasta_dt:
            filtered.append(order)
    return filtered


async def build_farmer_sales_csv(*, caficultor_id: str, desde: date, hasta: date) -> bytes:
    sales = await _get_farmer_sales_in_range(
        caficultor_id=caficultor_id,
        desde=desde,
        hasta=hasta,
    )

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "orderId",
        "estado",
        "itemsPropios",
        "subtotalPropio",
        "createdAt",
    ])

    for order in sales:
        writer.writerow([
            order.get("_id", ""),
            order.get("estado", ""),
            len(order.get("caficultor_items", [])),
            order.get("caficultor_subtotal", 0),
            order.get("createdAt", ""),
        ])

    return buffer.getvalue().encode("utf-8")


async def build_farmer_sales_pdf(*, caficultor_id: str, desde: date, hasta: date) -> bytes:
    sales = await _get_farmer_sales_in_range(
        caficultor_id=caficultor_id,
        desde=desde,
        hasta=hasta,
    )

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except Exception as ex:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo generar PDF. Instala dependencia: reportlab",
        ) from ex

    total_orders = len(sales)
    total_income = round(sum(float(o.get("caficultor_subtotal", 0)) for o in sales), 2)
    paid_orders = [o for o in sales if _is_paid_like_status(str(o.get("estado", "")))]
    paid_income = round(sum(float(o.get("caficultor_subtotal", 0)) for o in paid_orders), 2)

    out = BytesIO()
    pdf = canvas.Canvas(out, pagesize=letter)
    _, height = letter

    y = height - 50
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, y, "Colficultor - Reporte de ventas del caficultor")

    y -= 22
    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, y, f"Rango: {desde.isoformat()} a {hasta.isoformat()}")

    y -= 18
    pdf.drawString(40, y, f"Total pedidos con tus productos: {total_orders}")
    y -= 16
    pdf.drawString(40, y, f"Ingresos (subtotal propio): {total_income}")
    y -= 16
    pdf.drawString(40, y, f"Pedidos pagados/en curso/entregados: {len(paid_orders)}")
    y -= 16
    pdf.drawString(40, y, f"Ingresos pagados/en curso/entregados: {paid_income}")

    y -= 24
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(40, y, "Ultimos pedidos en rango")

    y -= 16
    pdf.setFont("Helvetica", 9)
    for order in sales[:25]:
        line = (
            f"{order.get('_id', '')[:8]}... "
            f"estado={order.get('estado', '')} "
            f"subtotal={order.get('caficultor_subtotal', 0)}"
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
