from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, require_role
from app.schemas.orders import OrderResponse, OrderStatusUpdateRequest
from app.schemas.user import UserInDB, UserRole
from app.services.orders_service import (
    change_order_status,
    create_order_from_cart,
    get_order_for_view,
    list_my_orders,
)

router = APIRouter(prefix="/api/ordenes", tags=["ordenes"])


@router.post("", response_model=OrderResponse)
async def create_order(
    current: UserInDB = Depends(require_role(UserRole.COMPRADOR)),
):
    return await create_order_from_cart(current.id)


@router.get("/mias", response_model=list[OrderResponse])
async def get_my_orders(
    current: UserInDB = Depends(require_role(UserRole.COMPRADOR)),
):
    return await list_my_orders(current.id)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order_detail(
    order_id: str,
    current: UserInDB = Depends(get_current_user),
):
    return await get_order_for_view(
        order_id=order_id,
        viewer_id=current.id,
        viewer_role=current.role,
    )


@router.put("/{order_id}/estado", response_model=OrderResponse)
async def update_order_status(
    order_id: str,
    payload: OrderStatusUpdateRequest,
    current: UserInDB = Depends(require_role(UserRole.CAFICULTOR, UserRole.ADMIN)),
):
    return await change_order_status(
        order_id=order_id,
        new_status=payload.estado,
        actor_id=current.id,
        actor_role=current.role,
    )
