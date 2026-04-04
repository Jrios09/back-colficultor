from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PaymentStatus(str, Enum):
    INITIATED = "INITIATED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class CreatePaymentIntentRequest(BaseModel):
    orderId: str = Field(..., min_length=1)


class CreatePaymentIntentResponse(BaseModel):
    orderId: str
    provider: str
    providerRef: str
    status: PaymentStatus
    paymentUrl: str | None = None
    redirectMethod: str | None = None
    formFields: dict[str, str] | None = None
    instructions: str | None = None


class PaymentWebhookPayload(BaseModel):
    provider: str
    providerRef: str = Field(..., min_length=1)
    orderId: str = Field(..., min_length=1)
    userId: str | None = None
    status: PaymentStatus
    amount: float = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    raw: dict[str, Any] | None = None


class PaymentWebhookResponse(BaseModel):
    accepted: bool
    idempotent: bool
    providerRef: str
    orderId: str
    status: PaymentStatus


class MockEmitPaymentEventRequest(BaseModel):
    orderId: str = Field(..., min_length=1)
    providerRef: str = Field(..., min_length=1)
    status: PaymentStatus
    amount: float = Field(..., gt=0)
    currency: str = Field(default="COP", min_length=3, max_length=3)
    raw: dict[str, Any] | None = None


class PaymentTransactionResponse(BaseModel):
    id: str = Field(alias="_id")
    orderId: str
    userId: str
    provider: str
    providerRef: str
    status: PaymentStatus
    amount: float
    currency: str
    raw: dict[str, Any] | None = None
    createdAt: datetime
    updatedAt: datetime
