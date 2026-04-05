from datetime import datetime

from fastapi import HTTPException, status

from app.models.user import list_active_user_ids_by_role
from app.repositories.notifications_repository import (
    count_unread_notifications_for_user,
    create_notification,
    list_notifications_for_user,
    mark_all_notifications_as_read_for_user,
    mark_notification_as_read_for_user,
)
from app.schemas.notifications import NotificationType
from app.schemas.pqr import PqrEstado, PqrTipo
from app.schemas.user import UserRole


async def _notify_user(
    *,
    user_id: str,
    notification_type: NotificationType,
    title: str,
    message: str,
    meta: dict | None = None,
) -> None:
    now = datetime.utcnow()
    await create_notification(
        {
            "userId": user_id,
            "type": notification_type.value,
            "title": title,
            "message": message,
            "meta": meta,
            "isRead": False,
            "readAt": None,
            "createdAt": now,
            "updatedAt": now,
        }
    )


async def _notify_many_users(
    *,
    user_ids: list[str],
    notification_type: NotificationType,
    title: str,
    message: str,
    meta: dict | None = None,
) -> None:
    for user_id in user_ids:
        await _notify_user(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            meta=meta,
        )


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

    await _notify_many_users(
        user_ids=caficultor_ids,
        notification_type=NotificationType.NEW_ORDER_FOR_FARMER,
        title="Nueva orden recibida",
        message=(
            f"Tienes una nueva orden ({order_id}) con {items_count} item(s). "
            f"Total de la orden: {round(total, 2)}."
        ),
        meta={
            "orderId": order_id,
            "buyerId": buyer_id,
            "itemsCount": items_count,
            "total": round(total, 2),
        },
    )


async def notify_order_created_to_buyer(
    *,
    order_id: str,
    buyer_id: str,
    total: float,
    items_count: int,
) -> None:
    await _notify_user(
        user_id=buyer_id,
        notification_type=NotificationType.ORDER_CREATED_FOR_BUYER,
        title="Orden creada",
        message=(
            f"Tu orden ({order_id}) fue creada con {items_count} item(s). "
            f"Total: {round(total, 2)}."
        ),
        meta={
            "orderId": order_id,
            "itemsCount": items_count,
            "total": round(total, 2),
        },
    )


async def notify_order_status_changed_to_buyer(
    *,
    order_id: str,
    buyer_id: str,
    from_status: str,
    to_status: str,
) -> None:
    await _notify_user(
        user_id=buyer_id,
        notification_type=NotificationType.ORDER_STATUS_FOR_BUYER,
        title="Estado de pedido actualizado",
        message=f"Tu pedido ({order_id}) cambió de {from_status} a {to_status}.",
        meta={
            "orderId": order_id,
            "fromStatus": from_status,
            "toStatus": to_status,
        },
    )


async def notify_payment_result_to_buyer(
    *,
    order_id: str,
    buyer_id: str,
    payment_status: str,
    provider_ref: str,
    amount: float,
    currency: str,
) -> None:
    await _notify_user(
        user_id=buyer_id,
        notification_type=NotificationType.PAYMENT_STATUS_FOR_BUYER,
        title="Resultado del pago",
        message=(
            f"El pago de tu orden ({order_id}) quedó en estado {payment_status}. "
            f"Referencia: {provider_ref}."
        ),
        meta={
            "orderId": order_id,
            "paymentStatus": payment_status,
            "providerRef": provider_ref,
            "amount": round(amount, 2),
            "currency": currency.upper(),
        },
    )


async def notify_payment_approved_to_farmers(
    *,
    order_id: str,
    caficultor_ids: list[str],
    amount: float,
    currency: str,
) -> None:
    if not caficultor_ids:
        return
    await _notify_many_users(
        user_ids=caficultor_ids,
        notification_type=NotificationType.PAYMENT_APPROVED_FOR_FARMER,
        title="Pago confirmado",
        message=f"La orden ({order_id}) fue pagada. Monto: {round(amount, 2)} {currency.upper()}.",
        meta={
            "orderId": order_id,
            "amount": round(amount, 2),
            "currency": currency.upper(),
        },
    )


async def notify_new_pqr_to_admins(
    *,
    ticket_id: str,
    user_id: str,
    tipo: PqrTipo | str,
    asunto: str,
) -> None:
    admin_ids = await list_active_user_ids_by_role(UserRole.ADMIN)
    if not admin_ids:
        return
    tipo_value = tipo.value if hasattr(tipo, "value") else str(tipo)
    await _notify_many_users(
        user_ids=admin_ids,
        notification_type=NotificationType.NEW_PQR_FOR_ADMIN,
        title="Nuevo ticket PQR",
        message=f"Se creó un ticket {tipo_value} ({ticket_id}) con asunto: {asunto}.",
        meta={
            "ticketId": ticket_id,
            "userId": user_id,
            "tipo": tipo_value,
            "asunto": asunto,
        },
    )


async def notify_pqr_status_to_user(
    *,
    ticket_id: str,
    user_id: str,
    estado: PqrEstado | str,
) -> None:
    estado_value = estado.value if hasattr(estado, "value") else str(estado)
    await _notify_user(
        user_id=user_id,
        notification_type=NotificationType.PQR_STATUS_FOR_USER,
        title="Actualización de PQR",
        message=f"Tu ticket ({ticket_id}) cambió al estado {estado_value}.",
        meta={
            "ticketId": ticket_id,
            "estado": estado_value,
        },
    )


async def notify_pqr_answer_to_user(
    *,
    ticket_id: str,
    user_id: str,
) -> None:
    await _notify_user(
        user_id=user_id,
        notification_type=NotificationType.PQR_ANSWER_FOR_USER,
        title="Respuesta a tu PQR",
        message=f"Tu ticket ({ticket_id}) recibió una respuesta del equipo de soporte.",
        meta={"ticketId": ticket_id},
    )


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
