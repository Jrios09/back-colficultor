from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import hmac
from uuid import uuid4

from fastapi import HTTPException, status

from app.core.config import settings
from app.models.user import get_user_by_id
from app.repositories.payments_repository import (
    create_transaction,
    get_order_by_id,
    get_transaction_by_provider_ref,
    set_order_status_with_history,
    update_transaction_status,
)
from app.services.notifications_service import (
    notify_payment_approved_to_farmers,
    notify_payment_result_to_buyer,
)
from app.schemas.orders import OrderStatus
from app.schemas.payments import (
    CreatePaymentIntentResponse,
    PaymentStatus,
    PaymentWebhookPayload,
    PaymentWebhookResponse,
)


PAYU_SANDBOX_CHECKOUT_URL = "https://sandbox.checkout.payulatam.com/ppp-web-gateway-payu/"
PAYU_PRODUCTION_CHECKOUT_URL = "https://checkout.payulatam.com/ppp-web-gateway-payu/"


def _ensure_webhook_secret_configured() -> str:
    secret = settings.WEBHOOK_SECRET.strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WEBHOOK_SECRET no está configurado",
        )
    return secret


def _assert_mock_webhook_token(token: str | None) -> None:
    expected = _ensure_webhook_secret_configured()
    if not token or token.strip() != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook token inválido",
        )


def _sanitize_raw_payload(raw: dict | None) -> dict | None:
    if not raw:
        return None

    blocked_fragments = ("card", "cvv", "cvc", "pan", "number")
    sanitized: dict = {}
    for key, value in raw.items():
        key_lower = key.lower()
        if any(fragment in key_lower for fragment in blocked_fragments):
            continue
        sanitized[key] = value
    return sanitized


def _target_order_status(payment_status: PaymentStatus) -> OrderStatus | None:
    if payment_status == PaymentStatus.APPROVED:
        return OrderStatus.PAGADA
    if payment_status in {PaymentStatus.REJECTED, PaymentStatus.FAILED}:
        return OrderStatus.PAGO_FALLIDO
    return None


def _build_mock_payment_url(order_id: str, provider_ref: str) -> str:
    return (
        f"{settings.FRONTEND_URL}/index.html"
        f"#resultado-pago?orderId={order_id}&providerRef={provider_ref}"
    )


def _payu_algorithm() -> str:
    return settings.PAYU_SIGNATURE_ALGORITHM.strip().upper() or "MD5"


def _payu_sign(message: str, *, algorithm: str) -> str:
    data = message.encode("utf-8")
    normalized = algorithm.upper()
    if normalized == "MD5":
        return hashlib.md5(data).hexdigest()
    if normalized == "SHA":
        return hashlib.sha1(data).hexdigest()
    if normalized in {"SHA256", "SHA-256"}:
        return hashlib.sha256(data).hexdigest()
    if normalized in {"HMAC_SHA256", "HMAC-SHA256"}:
        secret = (settings.PAYMENT_SECRET or settings.PAYU_API_KEY).encode("utf-8")
        return hmac.new(secret, data, hashlib.sha256).hexdigest()
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Algoritmo de firma PayU no soportado: {algorithm}",
    )


def _format_money_2(value: float | int | Decimal) -> str:
    decimal_value = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{decimal_value:.2f}"


def _format_payu_confirmation_value(raw_value: str) -> str:
    try:
        decimal_value = Decimal(str(raw_value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation as ex:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Valor PayU inválido") from ex

    rendered = f"{decimal_value:.2f}"
    integer_part, decimal_part = rendered.split(".")
    if decimal_part[1] == "0":
        return f"{integer_part}.{decimal_part[0]}"
    return rendered


def _validate_payu_config() -> None:
    required = {
        "PAYU_MERCHANT_ID": settings.PAYU_MERCHANT_ID,
        "PAYU_API_KEY": settings.PAYU_API_KEY,
        "PAYU_ACCOUNT_ID": settings.PAYU_ACCOUNT_ID,
    }
    missing = [key for key, value in required.items() if not str(value).strip()]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Faltan variables PayU: {', '.join(missing)}",
        )


def _build_payu_checkout(order: dict, *, provider_ref: str, buyer_email: str | None, buyer_name: str | None) -> tuple[str, dict[str, str]]:
    _validate_payu_config()
    amount = _format_money_2(order.get("total", 0))
    currency = settings.PAYU_CURRENCY.upper()
    algorithm = _payu_algorithm()
    signature_raw = f"{settings.PAYU_API_KEY}~{settings.PAYU_MERCHANT_ID}~{provider_ref}~{amount}~{currency}"
    signature = _payu_sign(signature_raw, algorithm=algorithm)

    checkout_url = PAYU_SANDBOX_CHECKOUT_URL if settings.PAYU_SANDBOX else PAYU_PRODUCTION_CHECKOUT_URL
    form_fields = {
        "merchantId": settings.PAYU_MERCHANT_ID,
        "accountId": settings.PAYU_ACCOUNT_ID,
        "description": f"Orden Colficultor {order['_id']}",
        "referenceCode": provider_ref,
        "amount": amount,
        "tax": "0",
        "taxReturnBase": "0",
        "currency": currency,
        "signature": signature,
        "algorithmSignature": algorithm,
        "test": "1" if settings.PAYU_SANDBOX else "0",
        "buyerEmail": buyer_email or "comprador@colficultor.local",
        "buyerFullName": buyer_name or "Comprador Colficultor",
        "responseUrl": f"{settings.FRONTEND_URL.rstrip('/')}/index.html",
        "confirmationUrl": f"{settings.BASE_URL_BACKEND.rstrip('/')}/api/pagos/webhook",
        "extra1": str(order["_id"]),  # orderId para reconciliación
        "lng": "es",
    }
    return checkout_url, form_fields


def _map_payu_state_to_internal(state_pol: str) -> PaymentStatus:
    mapping = {
        "4": PaymentStatus.APPROVED,
        "6": PaymentStatus.REJECTED,
        "5": PaymentStatus.FAILED,
        "104": PaymentStatus.FAILED,
        "7": PaymentStatus.PENDING,
    }
    return mapping.get(str(state_pol), PaymentStatus.PENDING)


def _verify_payu_signature(payload: dict) -> None:
    received_sign = str(payload.get("sign", "")).strip().lower()
    if not received_sign:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Firma PayU ausente")

    merchant_id = str(payload.get("merchant_id") or payload.get("merchantId") or "").strip()
    reference_sale = str(payload.get("reference_sale") or payload.get("referenceCode") or "").strip()
    state_pol = str(payload.get("state_pol") or "").strip()
    currency = str(payload.get("currency") or settings.PAYU_CURRENCY).strip().upper()
    value_raw = str(payload.get("value") or payload.get("TX_VALUE") or "").strip()
    if not merchant_id or not reference_sale or not state_pol or not value_raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payload PayU incompleto para validación de firma",
        )

    new_value = _format_payu_confirmation_value(value_raw)
    base = f"{settings.PAYU_API_KEY}~{merchant_id}~{reference_sale}~{new_value}~{currency}~{state_pol}"

    candidates = {
        hashlib.md5(base.encode("utf-8")).hexdigest(),
        hashlib.sha1(base.encode("utf-8")).hexdigest(),
        hashlib.sha256(base.encode("utf-8")).hexdigest(),
    }
    secret = (settings.PAYMENT_SECRET or "").strip()
    if secret:
        candidates.add(hmac.new(secret.encode("utf-8"), base.encode("utf-8"), hashlib.sha256).hexdigest())

    if received_sign not in {candidate.lower() for candidate in candidates}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Firma PayU inválida")


async def _persist_payment_result(
    *,
    provider: str,
    provider_ref: str,
    order_id: str,
    user_id: str | None,
    status_value: PaymentStatus,
    amount: float,
    currency: str,
    raw: dict | None,
) -> PaymentWebhookResponse:
    order = await get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden no encontrada")

    sanitized_raw = _sanitize_raw_payload(raw)

    existing = await get_transaction_by_provider_ref(provider_ref)
    idempotent = False
    if existing:
        if existing.get("status") == status_value.value:
            idempotent = True
        else:
            await update_transaction_status(
                provider_ref=provider_ref,
                status=status_value.value,
                raw=sanitized_raw,
            )
    else:
        now = datetime.utcnow()
        await create_transaction(
            {
                "orderId": order_id,
                "userId": user_id or order["userId"],
                "provider": provider,
                "providerRef": provider_ref,
                "status": status_value.value,
                "amount": float(amount),
                "currency": currency.upper(),
                "raw": sanitized_raw,
                "createdAt": now,
                "updatedAt": now,
            }
        )

    target_status = _target_order_status(status_value)
    if target_status is not None and not idempotent:
        await set_order_status_with_history(
            order_id=order_id,
            new_status=target_status.value,
            changed_by_user_id=None,
            reason=f"payment:{status_value.value}",
        )

    if not idempotent:
        try:
            await notify_payment_result_to_buyer(
                order_id=order_id,
                buyer_id=str(order.get("userId", "")),
                payment_status=status_value.value,
                provider_ref=provider_ref,
                amount=amount,
                currency=currency,
            )
            if status_value == PaymentStatus.APPROVED:
                await notify_payment_approved_to_farmers(
                    order_id=order_id,
                    caficultor_ids=[str(x) for x in order.get("caficultorIds", [])],
                    amount=amount,
                    currency=currency,
                )
        except Exception:
            # No bloquear webhook/confirmación por fallos en notificaciones.
            pass

    return PaymentWebhookResponse(
        accepted=True,
        idempotent=idempotent,
        providerRef=provider_ref,
        orderId=order_id,
        status=status_value,
    )


async def confirm_payu_redirect(
    *,
    transaction_state: str,
    reference_code: str,
    order_id: str,
    tx_value: str,
    currency: str,
    user_id: str,
) -> PaymentWebhookResponse:
    """Procesa el redirect de PayU sandbox desde el frontend.

    PayU redirige al usuario de vuelta al frontend con params en la URL.
    Como el webhook no puede alcanzar localhost en desarrollo, el frontend
    llama a este endpoint para registrar el resultado del pago.
    Solo disponible cuando PAYU_SANDBOX=True.
    """
    if not settings.PAYU_SANDBOX:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este endpoint solo está disponible en modo sandbox",
        )

    payment_status = _map_payu_state_to_internal(str(transaction_state))

    try:
        amount = float(tx_value.replace(",", "."))
    except (ValueError, AttributeError):
        amount = 0.0

    return await _persist_payment_result(
        provider="payu",
        provider_ref=reference_code,
        order_id=order_id,
        user_id=user_id,
        status_value=payment_status,
        amount=amount,
        currency=currency.upper() or "COP",
        raw={"transactionState": transaction_state, "source": "redirect_sandbox"},
    )


async def create_payment_intent(*, order_id: str, user_id: str) -> CreatePaymentIntentResponse:
    order = await get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden no encontrada")

    if order.get("userId") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para pagar esta orden",
        )

    if order.get("estado") == OrderStatus.PAGADA.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La orden ya fue pagada",
        )

    provider = settings.PAYMENT_PROVIDER.strip().lower()
    now = datetime.utcnow()

    if provider == "payu":
        reference_code = f"ORD-{order_id}-{uuid4().hex[:8]}"
        user = await get_user_by_id(user_id)
        checkout_url, form_fields = _build_payu_checkout(
            order,
            provider_ref=reference_code,
            buyer_email=user.email if user else None,
            buyer_name=user.full_name if user else None,
        )
        await create_transaction(
            {
                "orderId": order_id,
                "userId": user_id,
                "provider": provider,
                "providerRef": reference_code,
                "status": PaymentStatus.INITIATED.value,
                "amount": float(order.get("total", 0)),
                "currency": settings.PAYU_CURRENCY.upper(),
                "raw": {"flow": "crear-intento", "mode": "payu-webcheckout"},
                "createdAt": now,
                "updatedAt": now,
            }
        )
        return CreatePaymentIntentResponse(
            orderId=order_id,
            provider=provider,
            providerRef=reference_code,
            status=PaymentStatus.INITIATED,
            paymentUrl=checkout_url,
            redirectMethod="POST",
            formFields=form_fields,
            instructions="Renderiza un formulario HTML y envíalo por POST a paymentUrl con formFields.",
        )

    provider_ref = f"mock_{uuid4().hex}"
    await create_transaction(
        {
            "orderId": order_id,
            "userId": user_id,
            "provider": "mock",
            "providerRef": provider_ref,
            "status": PaymentStatus.INITIATED.value,
            "amount": float(order.get("total", 0)),
            "currency": settings.PAYU_CURRENCY.upper(),
            "raw": {
                "flow": "crear-intento",
                "orderStatus": order.get("estado"),
            },
            "createdAt": now,
            "updatedAt": now,
        }
    )
    return CreatePaymentIntentResponse(
        orderId=order_id,
        provider="mock",
        providerRef=provider_ref,
        status=PaymentStatus.INITIATED,
        paymentUrl=_build_mock_payment_url(order_id=order_id, provider_ref=provider_ref),
        instructions="Usa /api/pagos/mock/emit-event para simular APPROVED/REJECTED/FAILED.",
    )


async def process_payment_webhook_payload(
    *,
    payload: PaymentWebhookPayload,
    webhook_token: str | None,
) -> PaymentWebhookResponse:
    _assert_mock_webhook_token(webhook_token)
    return await _persist_payment_result(
        provider=payload.provider,
        provider_ref=payload.providerRef,
        order_id=payload.orderId,
        user_id=payload.userId,
        status_value=payload.status,
        amount=payload.amount,
        currency=payload.currency,
        raw=payload.raw,
    )


async def process_payu_confirmation(payload: dict) -> PaymentWebhookResponse:
    _verify_payu_signature(payload)

    reference_sale = str(payload.get("reference_sale") or payload.get("referenceCode") or "").strip()
    if not reference_sale:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="reference_sale ausente")

    existing = await get_transaction_by_provider_ref(reference_sale)
    if existing:
        order_id = existing["orderId"]
        user_id = existing.get("userId")
    else:
        order_id = str(payload.get("extra1") or "").strip()
        if not order_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No se pudo reconciliar orderId de la confirmación PayU",
            )
        user_id = None

    state_pol = str(payload.get("state_pol") or "")
    status_value = _map_payu_state_to_internal(state_pol)
    value = float(payload.get("value") or payload.get("TX_VALUE") or 0)
    currency = str(payload.get("currency") or settings.PAYU_CURRENCY).upper()

    return await _persist_payment_result(
        provider="payu",
        provider_ref=reference_sale,
        order_id=order_id,
        user_id=user_id,
        status_value=status_value,
        amount=value,
        currency=currency,
        raw=payload,
    )
