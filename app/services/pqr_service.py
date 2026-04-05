from datetime import datetime

from fastapi import HTTPException, status

from app.repositories.pqr_repository import (
    append_ticket_message,
    create_ticket,
    get_ticket_by_id,
    list_all_tickets,
    list_tickets_by_user,
    update_ticket_estado,
)
from app.services.notifications_service import (
    notify_new_pqr_to_admins,
    notify_pqr_answer_to_user,
    notify_pqr_status_to_user,
)
from app.schemas.pqr import (
    PqrCreateRequest,
    PqrEstado,
    PqrMensajeCreateRequest,
    PqrRespuestaRequest,
)
from app.schemas.user import UserRole


def _is_admin(role: str | UserRole) -> bool:
    raw_role = role.value if isinstance(role, UserRole) else str(role)
    return raw_role == UserRole.ADMIN.value


async def create_ticket_for_user(*, user_id: str, payload: PqrCreateRequest) -> dict:
    now = datetime.utcnow()
    ticket_doc = {
        "userId": user_id,
        "tipo": payload.tipo.value,
        "asunto": payload.asunto.strip(),
        "descripcion": payload.descripcion.strip(),
        "estado": PqrEstado.ABIERTO.value,
        "respuesta": None,
        "mensajes": [
            {
                "autorId": user_id,
                "autorRole": "USUARIO",
                "mensaje": payload.descripcion.strip(),
                "createdAt": now,
            }
        ],
        "createdAt": now,
        "updatedAt": now,
    }
    created = await create_ticket(ticket_doc)
    try:
        await notify_new_pqr_to_admins(
            ticket_id=str(created.get("_id", "")),
            user_id=user_id,
            tipo=payload.tipo,
            asunto=payload.asunto.strip(),
        )
    except Exception:
        pass
    return created


async def list_my_tickets(user_id: str) -> list[dict]:
    return await list_tickets_by_user(user_id)


async def list_all_tickets_for_admin(actor_role: str | UserRole) -> list[dict]:
    if not _is_admin(actor_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para consultar todos los tickets",
        )
    return await list_all_tickets()


async def get_ticket_for_view(*, ticket_id: str, viewer_id: str, viewer_role: str | UserRole) -> dict:
    ticket = await get_ticket_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")

    if _is_admin(viewer_role):
        return ticket

    if ticket.get("userId") != viewer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver este ticket",
        )

    return ticket


async def change_ticket_status(*, ticket_id: str, estado: PqrEstado, actor_role: str | UserRole) -> dict:
    if not _is_admin(actor_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para cambiar el estado de tickets",
        )

    updated = await update_ticket_estado(ticket_id=ticket_id, estado=estado.value)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")
    try:
        await notify_pqr_status_to_user(
            ticket_id=ticket_id,
            user_id=str(updated.get("userId", "")),
            estado=estado,
        )
    except Exception:
        pass
    return updated


async def answer_ticket(*, ticket_id: str, payload: PqrRespuestaRequest, actor_role: str | UserRole) -> dict:
    if not _is_admin(actor_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para responder tickets",
        )

    message_text = payload.respuesta.strip()
    updated = await append_ticket_message(
        ticket_id=ticket_id,
        message_doc={
            "autorId": "admin",
            "autorRole": UserRole.ADMIN.value,
            "mensaje": message_text,
            "createdAt": datetime.utcnow(),
        },
        set_respuesta=message_text,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")
    try:
        await notify_pqr_answer_to_user(
            ticket_id=ticket_id,
            user_id=str(updated.get("userId", "")),
        )
    except Exception:
        pass
    return updated


async def add_ticket_message(
    *,
    ticket_id: str,
    sender_id: str,
    sender_role: str | UserRole,
    payload: PqrMensajeCreateRequest,
) -> dict:
    ticket = await get_ticket_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")

    raw_role = sender_role.value if isinstance(sender_role, UserRole) else str(sender_role)
    is_admin = raw_role == UserRole.ADMIN.value
    if not is_admin and ticket.get("userId") != sender_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para enviar mensajes en este ticket",
        )

    text = payload.mensaje.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El mensaje no puede estar vacío",
        )

    updated = await append_ticket_message(
        ticket_id=ticket_id,
        message_doc={
            "autorId": sender_id,
            "autorRole": raw_role,
            "mensaje": text,
            "createdAt": datetime.utcnow(),
        },
        set_respuesta=text if is_admin else None,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")

    try:
        if is_admin:
            await notify_pqr_answer_to_user(
                ticket_id=ticket_id,
                user_id=str(updated.get("userId", "")),
            )
        else:
            await notify_new_pqr_to_admins(
                ticket_id=ticket_id,
                user_id=sender_id,
                tipo=str(updated.get("tipo", "PQR")),
                asunto=f"Nuevo mensaje en ticket: {updated.get('asunto', '')}",
            )
    except Exception:
        pass

    return updated
