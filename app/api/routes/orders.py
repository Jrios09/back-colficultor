from fastapi import APIRouter, Depends

from app.api.deps import require_role
from app.schemas.orders import OrderResponse
from app.schemas.user import UserInDB, UserRole
from app.services.orders_service import create_order_from_cart

router = APIRouter(prefix="/api/ordenes", tags=["ordenes"])


@router.post("", response_model=OrderResponse)
async def create_order(
    current: UserInDB = Depends(require_role(UserRole.COMPRADOR)),
):
    return await create_order_from_cart(current.id)
