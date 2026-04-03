from datetime import datetime

from pydantic import BaseModel, Field


class CartItemMutation(BaseModel):
    productId: str = Field(..., min_length=1)
    cantidad: int = Field(..., ge=1, le=100000)


class CartItemQuantityUpdate(BaseModel):
    cantidad: int = Field(..., ge=1, le=100000)


class CartItemResponse(BaseModel):
    productId: str
    nombre: str
    cantidad: int
    precioSnapshot: float
    subtotal: float


class CartResponse(BaseModel):
    userId: str
    items: list[CartItemResponse]
    total: float
    updatedAt: datetime
