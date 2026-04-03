from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    PENDIENTE_PAGO = "PENDIENTE_PAGO"


class OrderItemResponse(BaseModel):
    productId: str
    nombreSnapshot: str
    precioSnapshot: float
    cantidad: int
    subtotal: float


class OrderResponse(BaseModel):
    id: str = Field(alias="_id")
    userId: str
    items: list[OrderItemResponse]
    total: float
    estado: OrderStatus
    createdAt: datetime
    updatedAt: datetime
