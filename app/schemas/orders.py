from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    PENDIENTE_PAGO = "PENDIENTE_PAGO"
    PAGADA = "PAGADA"
    PAGO_FALLIDO = "PAGO_FALLIDO"
    EN_PREPARACION = "EN_PREPARACION"
    ENVIADA = "ENVIADA"
    ENTREGADA = "ENTREGADA"
    CANCELADA = "CANCELADA"


class OrderItemResponse(BaseModel):
    productId: str
    nombreSnapshot: str
    precioSnapshot: float
    cantidad: int
    subtotal: float


class OrderStatusHistoryItem(BaseModel):
    fromStatus: OrderStatus | None = None
    toStatus: OrderStatus
    changedByUserId: str | None = None
    reason: str | None = None
    createdAt: datetime


class OrderResponse(BaseModel):
    id: str = Field(alias="_id")
    userId: str
    caficultorIds: list[str] = Field(default_factory=list)
    items: list[OrderItemResponse]
    total: float
    estado: OrderStatus
    statusHistory: list[OrderStatusHistoryItem] = Field(default_factory=list)
    createdAt: datetime
    updatedAt: datetime


class OrderStatusUpdateRequest(BaseModel):
    estado: OrderStatus
