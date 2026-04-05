from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.schemas.notifications import (
    NotificationListResponse,
    NotificationMarkReadResponse,
)
from app.schemas.user import UserInDB
from app.services.notifications_service import (
    get_notifications_for_user,
    mark_all_notifications_read,
    mark_notification_read,
)

router = APIRouter(prefix="/api/notificaciones", tags=["notificaciones"])


@router.get("", response_model=NotificationListResponse)
async def list_my_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    current: UserInDB = Depends(get_current_user),
):
    return await get_notifications_for_user(current.id, limit=limit)


@router.put("/{notification_id}/leer", response_model=NotificationMarkReadResponse)
async def mark_one_notification_as_read(
    notification_id: str,
    current: UserInDB = Depends(get_current_user),
):
    return await mark_notification_read(notification_id=notification_id, user_id=current.id)


@router.put("/leer-todas", response_model=NotificationMarkReadResponse)
async def mark_all_as_read(
    current: UserInDB = Depends(get_current_user),
):
    return await mark_all_notifications_read(current.id)
