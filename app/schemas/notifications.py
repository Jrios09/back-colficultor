from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class NotificationType(str, Enum):
    NEW_ORDER_FOR_FARMER = "NEW_ORDER_FOR_FARMER"
    ORDER_CREATED_FOR_BUYER = "ORDER_CREATED_FOR_BUYER"
    ORDER_STATUS_FOR_BUYER = "ORDER_STATUS_FOR_BUYER"
    PAYMENT_STATUS_FOR_BUYER = "PAYMENT_STATUS_FOR_BUYER"
    PAYMENT_APPROVED_FOR_FARMER = "PAYMENT_APPROVED_FOR_FARMER"
    NEW_PQR_FOR_ADMIN = "NEW_PQR_FOR_ADMIN"
    PQR_STATUS_FOR_USER = "PQR_STATUS_FOR_USER"
    PQR_ANSWER_FOR_USER = "PQR_ANSWER_FOR_USER"


class NotificationResponse(BaseModel):
    id: str = Field(alias="_id")
    userId: str
    type: NotificationType
    title: str
    message: str
    meta: dict[str, Any] | None = None
    isRead: bool
    readAt: datetime | None = None
    createdAt: datetime
    updatedAt: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    unread: int


class NotificationMarkReadResponse(BaseModel):
    message: str
