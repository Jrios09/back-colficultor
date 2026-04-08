from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user, require_role
from app.schemas.pqr import (
    PqrCreateRequest,
    PqrEstadoUpdateRequest,
    PqrMensajeCreateRequest,
    PqrRespuestaRequest,
    PqrTicketResponse,
)
from app.schemas.user import UserInDB, UserRole
from app.services.pqr_service import (
    add_ticket_message,
    answer_ticket,
    change_ticket_status,
    create_ticket_for_user,
    get_ticket_for_view,
    list_all_tickets_for_admin,
    list_my_tickets,
)

router = APIRouter(prefix="/api/pqr", tags=["pqr"])


@router.post("", response_model=PqrTicketResponse, status_code=status.HTTP_201_CREATED)
async def create_pqr_ticket(
    payload: PqrCreateRequest,
    current: UserInDB = Depends(get_current_user),
):
    return await create_ticket_for_user(user_id=current.id, user_role=current.role, payload=payload)


@router.get("/mis", response_model=list[PqrTicketResponse])
async def list_my_pqr_tickets(current: UserInDB = Depends(get_current_user)):
    return await list_my_tickets(current.id)


@router.get("", response_model=list[PqrTicketResponse])
async def list_all_pqr_tickets(
    current: UserInDB = Depends(require_role(UserRole.ADMIN)),
):
    return await list_all_tickets_for_admin(current.role)


@router.get("/{ticket_id}", response_model=PqrTicketResponse)
async def get_pqr_ticket(
    ticket_id: str,
    current: UserInDB = Depends(get_current_user),
):
    return await get_ticket_for_view(
        ticket_id=ticket_id,
        viewer_id=current.id,
        viewer_role=current.role,
    )


@router.put("/{ticket_id}/estado", response_model=PqrTicketResponse)
async def update_pqr_status(
    ticket_id: str,
    payload: PqrEstadoUpdateRequest,
    current: UserInDB = Depends(require_role(UserRole.ADMIN)),
):
    return await change_ticket_status(
        ticket_id=ticket_id,
        estado=payload.estado,
        actor_role=current.role,
    )


@router.post("/{ticket_id}/respuesta", response_model=PqrTicketResponse)
async def respond_pqr_ticket(
    ticket_id: str,
    payload: PqrRespuestaRequest,
    current: UserInDB = Depends(require_role(UserRole.ADMIN)),
):
    return await answer_ticket(
        ticket_id=ticket_id,
        payload=payload,
        actor_role=current.role,
    )


@router.post("/{ticket_id}/mensajes", response_model=PqrTicketResponse)
async def send_pqr_message(
    ticket_id: str,
    payload: PqrMensajeCreateRequest,
    current: UserInDB = Depends(get_current_user),
):
    return await add_ticket_message(
        ticket_id=ticket_id,
        sender_id=current.id,
        sender_role=current.role,
        payload=payload,
    )
