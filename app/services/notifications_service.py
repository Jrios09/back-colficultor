from datetime import datetime

from fastapi import HTTPException, status

from app.repositories.notifications_repository import (
    count_unread_notifications_for_user,
    create_notification,
    list_notifications_for_user,
    mark_all_notifications_as_read_for_user,
    mark_notification_as_read_for_user,
)
from app.schemas.notifications import NotificationType


async def notify_new_order_to_farmers(
    *,
    order_id: str,
    buyer_id: str,
    caficultor_ids: list[str],
    total: float,
    items_count: int,
) -> None:
    if not caficultor_ids:
        return

    now = datetime.utcnow()
    for caficultor_id in caficultor_ids:
        doc = {
            "userId": caficultor_id,
            "type": NotificationType.NEW_ORDER_FOR_FARMER.value,
            "title": "Nueva orden recibida",
            "message": (
                f"Tienes una nueva orden ({order_id}) con {items_count} item(s). "
                f"Total de la orden: {round(total, 2)}."
            ),
            "meta": {
                "orderId": order_id,
                "buyerId": buyer_id,
                "itemsCount": items_count,
                "total": round(total, 2),
            },
            "isRead": False,
            "readAt": None,
            "createdAt": now,
            "updatedAt": now,
        }
        await create_notification(doc)


async def get_notifications_for_user(user_id: str, *, limit: int = 50) -> dict:
    items = await list_notifications_for_user(user_id, limit=limit)
    unread = await count_unread_notifications_for_user(user_id)
    return {
        "items": items,
        "unread": unread,
    }


async def mark_notification_read(*, notification_id: str, user_id: str) -> dict:
    updated = await mark_notification_as_read_for_user(notification_id, user_id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificación no encontrada",
        )
    return {"message": "Notificación marcada como leída"}


async def mark_all_notifications_read(user_id: str) -> dict:
    modified = await mark_all_notifications_as_read_for_user(user_id)
    return {"message": f"Se marcaron {modified} notificación(es) como leídas"}
