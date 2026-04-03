from fastapi import APIRouter, Depends

from app.api.deps import require_role
from app.schemas.cart import CartItemMutation, CartItemQuantityUpdate, CartResponse
from app.schemas.user import UserInDB, UserRole
from app.services.cart_service import (
    add_item_to_cart,
    get_cart_for_user,
    remove_item_from_cart,
    update_cart_item_quantity,
)

router = APIRouter(prefix="/api/carrito", tags=["carrito"])


@router.get("", response_model=CartResponse)
async def get_cart(
    current: UserInDB = Depends(require_role(UserRole.COMPRADOR)),
):
    return await get_cart_for_user(current.id)


@router.post("/items", response_model=CartResponse)
async def add_cart_item(
    payload: CartItemMutation,
    current: UserInDB = Depends(require_role(UserRole.COMPRADOR)),
):
    return await add_item_to_cart(
        user_id=current.id,
        product_id=payload.productId,
        cantidad=payload.cantidad,
    )


@router.put("/items/{product_id}", response_model=CartResponse)
async def update_cart_item(
    product_id: str,
    payload: CartItemQuantityUpdate,
    current: UserInDB = Depends(require_role(UserRole.COMPRADOR)),
):
    return await update_cart_item_quantity(
        user_id=current.id,
        product_id=product_id,
        cantidad=payload.cantidad,
    )


@router.delete("/items/{product_id}", response_model=CartResponse)
async def delete_cart_item(
    product_id: str,
    current: UserInDB = Depends(require_role(UserRole.COMPRADOR)),
):
    return await remove_item_from_cart(
        user_id=current.id,
        product_id=product_id,
    )
