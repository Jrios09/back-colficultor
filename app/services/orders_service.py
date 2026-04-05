import asyncio
import logging
from datetime import datetime

from fastapi import HTTPException, status

from app.repositories.cart_repository import clear_cart, get_or_create_cart
from app.repositories.orders_repository import (
    create_order,
    get_order_by_id,
    get_product_ids_of_caficultor,
    list_orders_by_caficultor,
    list_orders_by_user,
    order_has_caficultor,
    soft_delete_pending_order_by_buyer,
    update_order_status_with_history,
)
from app.repositories.products_repository import (
    decrement_stock_if_available,
    get_active_products_by_ids,
    increment_stock,
)
from app.services.notifications_service import notify_new_order_to_farmers
from app.schemas.orders import OrderStatus
from app.schemas.user import UserRole

logger = logging.getLogger(__name__)

ROLE_VALUE_MAP = {
    UserRole.COMPRADOR.value: UserRole.COMPRADOR.value,
    UserRole.CAFICULTOR.value: UserRole.CAFICULTOR.value,
    UserRole.ADMIN.value: UserRole.ADMIN.value,
}


ORDER_TRANSITIONS_BY_ROLE: dict[str, set[tuple[OrderStatus, OrderStatus]]] = {
    UserRole.CAFICULTOR.value: {
        (OrderStatus.PAGADA, OrderStatus.EN_PREPARACION),
        (OrderStatus.EN_PREPARACION, OrderStatus.ENVIADA),
        (OrderStatus.ENVIADA, OrderStatus.ENTREGADA),
        (OrderStatus.PAGADA, OrderStatus.CANCELADA),
        (OrderStatus.EN_PREPARACION, OrderStatus.CANCELADA),
    },
    UserRole.ADMIN.value: {
        (OrderStatus.PAGADA, OrderStatus.EN_PREPARACION),
        (OrderStatus.EN_PREPARACION, OrderStatus.ENVIADA),
        (OrderStatus.ENVIADA, OrderStatus.ENTREGADA),
        (OrderStatus.PAGADA, OrderStatus.CANCELADA),
        (OrderStatus.EN_PREPARACION, OrderStatus.CANCELADA),
        (OrderStatus.ENVIADA, OrderStatus.CANCELADA),
    },
}


def _normalize_role(role: str | UserRole) -> str:
    raw = role.value if isinstance(role, UserRole) else str(role)
    return ROLE_VALUE_MAP.get(raw, raw)


def _to_order_status(value: str | OrderStatus) -> OrderStatus:
    try:
        return value if isinstance(value, OrderStatus) else OrderStatus(value)
    except Exception as ex:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Estado actual de orden no soportado: {value}",
        ) from ex


def _assert_allowed_transition(*, role: str, current: OrderStatus, target: OrderStatus) -> None:
    if current == OrderStatus.PENDIENTE_PAGO and target == OrderStatus.PAGADA:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La transición PENDIENTE_PAGO -> PAGADA solo se permite por confirmación de pago",
        )

    allowed = ORDER_TRANSITIONS_BY_ROLE.get(role, set())
    if (current, target) in allowed:
        return

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Transición inválida: {current.value} -> {target.value}",
    )


async def create_order_from_cart(user_id: str) -> dict:
    cart = await get_or_create_cart(user_id)
    cart_items = cart.get("items", [])

    if not cart_items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El carrito está vacío",
        )

    product_ids = [item["productId"] for item in cart_items]
    products_map = await get_active_products_by_ids(product_ids)

    missing_products = [pid for pid in product_ids if pid not in products_map]
    if missing_products:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto no encontrado o inactivo: {missing_products[0]}",
        )

    for item in cart_items:
        product = products_map[item["productId"]]
        if int(product["stock"]) < int(item["cantidad"]):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stock insuficiente para '{product['nombre']}'. Disponible: {product['stock']}",
            )

    decremented: list[tuple[str, int]] = []
    try:
        for item in cart_items:
            ok = await decrement_stock_if_available(item["productId"], int(item["cantidad"]))
            if not ok:
                product = products_map[item["productId"]]
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Stock insuficiente para '{product['nombre']}'. Intenta nuevamente.",
                )
            decremented.append((item["productId"], int(item["cantidad"])))
    except Exception:
        for product_id, cantidad in decremented:
            await increment_stock(product_id, cantidad)
        raise

    order_items = []
    caficultor_ids: set[str] = set()
    total = 0.0
    for item in cart_items:
        product = products_map[item["productId"]]
        precio = float(product["precio"])
        cantidad = int(item["cantidad"])
        subtotal = precio * cantidad
        total += subtotal

        order_items.append(
            {
                "productId": item["productId"],
                "nombreSnapshot": product["nombre"],
                "precioSnapshot": precio,
                "cantidad": cantidad,
                "subtotal": subtotal,
            }
        )
        caficultor_id = product.get("caficultor_id")
        if caficultor_id:
            caficultor_ids.add(str(caficultor_id))

    now = datetime.utcnow()
    order_doc = {
        "userId": user_id,
        "caficultorIds": sorted(caficultor_ids),
        "items": order_items,
        "total": total,
        "estado": OrderStatus.PENDIENTE_PAGO.value,
        "statusHistory": [
            {
                "fromStatus": None,
                "toStatus": OrderStatus.PENDIENTE_PAGO.value,
                "changedByUserId": user_id,
                "reason": "order_created",
                "createdAt": now,
            }
        ],
        "createdAt": now,
        "updatedAt": now,
    }

    order = await create_order(order_doc)
    await clear_cart(user_id)

    # No bloquear el flujo de compra por fallos o latencia en notificaciones.
    try:
        await asyncio.wait_for(
            notify_new_order_to_farmers(
                order_id=order["_id"],
                buyer_id=user_id,
                caficultor_ids=sorted(caficultor_ids),
                total=total,
                items_count=len(order_items),
            ),
            timeout=2.0,
        )
    except asyncio.TimeoutError:
        logger.warning("Timeout enviando notificaciones de nueva orden order_id=%s", order.get("_id"))
    except Exception:
        logger.exception("Error enviando notificaciones de nueva orden order_id=%s", order.get("_id"))

    return order


async def list_my_orders(user_id: str) -> list[dict]:
    return await list_orders_by_user(user_id)


async def list_sales(caficultor_id: str) -> list[dict]:
    orders = await list_orders_by_caficultor(caficultor_id)

    # Recolectar todos los product_ids en un solo pass
    all_product_ids: set[str] = {
        item["productId"]
        for order in orders
        for item in order.get("items", [])
    }

    # Un solo query a MongoDB para saber cuáles productos son de este caficultor
    my_product_ids = await get_product_ids_of_caficultor(all_product_ids, caficultor_id)

    # Anotar cada orden con la vista del caficultor
    for order in orders:
        my_items = [i for i in order.get("items", []) if i["productId"] in my_product_ids]
        order["caficultor_items"]    = my_items
        order["caficultor_subtotal"] = round(sum(i["subtotal"] for i in my_items), 2)

    return orders


async def get_order_for_view(*, order_id: str, viewer_id: str, viewer_role: str | UserRole) -> dict:
    order = await get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden no encontrada")

    role = _normalize_role(viewer_role)
    if role == UserRole.ADMIN.value:
        return order

    if role == UserRole.COMPRADOR.value:
        if order.get("userId") != viewer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para ver esta orden",
            )
        return order

    if role == UserRole.CAFICULTOR.value:
        if await order_has_caficultor(order, viewer_id):
            return order
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver esta orden",
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Rol no permitido para consultar órdenes",
    )


async def change_order_status(
    *,
    order_id: str,
    new_status: OrderStatus,
    actor_id: str,
    actor_role: str | UserRole,
) -> dict:
    role = _normalize_role(actor_role)
    if role not in {UserRole.CAFICULTOR.value, UserRole.ADMIN.value}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para cambiar estado de órdenes",
        )

    order = await get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden no encontrada")

    if role == UserRole.CAFICULTOR.value and not await order_has_caficultor(order, actor_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para cambiar estado de esta orden",
        )

    current_status = _to_order_status(order.get("estado"))
    _assert_allowed_transition(role=role, current=current_status, target=new_status)

    updated = await update_order_status_with_history(
        order_id=order_id,
        new_status=new_status.value,
        changed_by_user_id=actor_id,
        reason=f"manual_update_by_{role}",
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden no encontrada")
    return updated


async def delete_pending_order_for_buyer(*, order_id: str, buyer_id: str) -> dict:
    order = await get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden no encontrada")

    if order.get("userId") != buyer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para eliminar esta orden",
        )

    if order.get("deletedByBuyer") is True:
        return {
            "message": "La orden ya fue eliminada de tu historial.",
            "orderId": order_id,
        }

    if order.get("estado") != OrderStatus.PENDIENTE_PAGO.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo puedes eliminar órdenes en estado PENDIENTE_PAGO",
        )

    for item in order.get("items", []):
        await increment_stock(item.get("productId", ""), int(item.get("cantidad", 0)))

    updated = await soft_delete_pending_order_by_buyer(order_id=order_id, buyer_id=buyer_id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se pudo eliminar la orden",
        )

    return {
        "message": "Orden pendiente eliminada correctamente.",
        "orderId": order_id,
    }
