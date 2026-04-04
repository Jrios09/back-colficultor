from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.api.deps import require_role
from app.core.config import settings
from app.schemas.payments import (
    CreatePaymentIntentRequest,
    CreatePaymentIntentResponse,
    MockEmitPaymentEventRequest,
    PaymentWebhookPayload,
    PaymentWebhookResponse,
)
from app.schemas.user import UserInDB, UserRole
from app.services.payments_service import (
    create_payment_intent,
    process_payment_webhook_payload,
    process_payu_confirmation,
)

router = APIRouter(prefix="/api/pagos", tags=["pagos"])


@router.post("/crear-intento", response_model=CreatePaymentIntentResponse)
async def create_intent(
    payload: CreatePaymentIntentRequest,
    current: UserInDB = Depends(require_role(UserRole.COMPRADOR)),
):
    return await create_payment_intent(order_id=payload.orderId, user_id=current.id)


@router.post("/webhook", response_model=PaymentWebhookResponse)
async def payments_webhook(
    request: Request,
    x_webhook_token: str | None = Header(default=None),
):
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        return await process_payu_confirmation(dict(form))

    payload_dict = await request.json()
    if "state_pol" in payload_dict or "reference_sale" in payload_dict:
        return await process_payu_confirmation(payload_dict)

    payload = PaymentWebhookPayload.model_validate(payload_dict)
    return await process_payment_webhook_payload(payload=payload, webhook_token=x_webhook_token)


@router.post("/mock/emit-event", response_model=PaymentWebhookResponse)
async def emit_mock_event(
    payload: MockEmitPaymentEventRequest,
    x_mock_webhook_token: str | None = Header(default=None),
):
    if settings.APP_ENV.lower() not in {"dev", "development", "local"}:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Endpoint disponible solo en entorno de desarrollo",
        )

    webhook_payload = PaymentWebhookPayload(
        provider="mock",
        providerRef=payload.providerRef,
        orderId=payload.orderId,
        userId=None,
        status=payload.status,
        amount=payload.amount,
        currency=payload.currency,
        raw=payload.raw,
    )
    return await process_payment_webhook_payload(
        payload=webhook_payload,
        webhook_token=x_mock_webhook_token,
    )
