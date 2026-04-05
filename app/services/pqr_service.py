from datetime import datetime

from fastapi import HTTPException, status

from app.repositories.pqr_repository import (
    create_ticket,
    get_ticket_by_id,
    list_all_tickets,
    list_tickets_by_user,
    update_ticket_estado,
    update_ticket_respuesta,
)
from app.services.notifications_service import (
    notify_new_pqr_to_admins,
    notify_pqr_answer_to_user,
    notify_pqr_status_to_user,
)
from app.schemas.pqr import PqrCreateRequest, PqrEstado, PqrRespuestaRequest
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

    updated = await update_ticket_respuesta(
        ticket_id=ticket_id,
        respuesta=payload.respuesta.strip(),
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
