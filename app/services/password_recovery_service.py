import logging
from datetime import datetime, timedelta
from secrets import token_urlsafe
from urllib.parse import quote

from fastapi import HTTPException, status

from app.core.config import settings
from app.core.security import hash_reset_token
from app.models.user import get_user_by_email, get_user_by_id, set_user_password
from app.repositories.password_reset_repository import (
    create_password_reset_token,
    get_valid_password_reset_by_token_hash,
    invalidate_active_tokens_for_user,
    mark_password_reset_token_used,
)
from app.services.mail_service import MailDeliveryError, send_email

logger = logging.getLogger(__name__)

GENERIC_FORGOT_PASSWORD_MESSAGE = (
    "Si el correo está registrado, recibirás un enlace de recuperación en breve."
)


def _generate_reset_token() -> str:
    # 48 bytes aleatorios => token URL-safe suficientemente largo para un solo uso.
    return token_urlsafe(48)


def _build_reset_link(token: str) -> str:
    base_url = settings.FRONTEND_URL.rstrip("/")
    return f"{base_url}/reset-password.html?token={quote(token, safe='')}"


def _build_reset_email_html(reset_link: str) -> str:
    return f"""
    <html>
      <body style=\"font-family: Arial, sans-serif; color: #1f2937;\">
        <h2 style=\"margin-bottom: 8px;\">Recuperación de contraseña - Colficultor</h2>
        <p>Recibimos una solicitud para restablecer tu contraseña.</p>
        <p>
          <a href=\"{reset_link}\" style=\"display: inline-block; padding: 10px 16px; background: #0f766e; color: white; text-decoration: none; border-radius: 6px;\">Restablecer contraseña</a>
        </p>
        <p>Este enlace expira en {settings.RESET_TOKEN_EXPIRE_MINUTES} minutos y solo puede usarse una vez.</p>
        <p>Si no solicitaste este cambio, ignora este correo. Tu cuenta seguirá segura.</p>
      </body>
    </html>
    """


def _build_password_changed_email_html() -> str:
    return """
    <html>
      <body style=\"font-family: Arial, sans-serif; color: #1f2937;\">
        <h2 style=\"margin-bottom: 8px;\">Contraseña actualizada - Colficultor</h2>
        <p>Tu contraseña fue cambiada correctamente.</p>
        <p>Si no fuiste tú, contacta al soporte de inmediato.</p>
      </body>
    </html>
    """


async def request_password_reset(email: str, client_ip: str | None = None) -> str:
    normalized_email = email.strip().lower()

    user = await get_user_by_email(normalized_email)
    if not user:
        return GENERIC_FORGOT_PASSWORD_MESSAGE

    await invalidate_active_tokens_for_user(user.id)

    token = _generate_reset_token()
    token_hash = hash_reset_token(token)
    expires_at = datetime.utcnow() + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)

    token_id = await create_password_reset_token(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    reset_link = _build_reset_link(token)
    subject = "Recuperación de contraseña - Colficultor"
    html = _build_reset_email_html(reset_link)

    try:
        await send_email(to_email=user.email, subject=subject, html_body=html)
    except MailDeliveryError:
        await mark_password_reset_token_used(token_id=token_id)
        logger.exception("Error enviando correo de recuperación para user_id=%s", user.id)

    return GENERIC_FORGOT_PASSWORD_MESSAGE


async def validate_reset_token(token: str) -> None:
    token_hash = hash_reset_token(token)
    reset_doc = await get_valid_password_reset_by_token_hash(token_hash)
    if not reset_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El token es inválido, ya fue usado o expiró.",
        )


async def reset_password_with_token(token: str, new_password: str) -> str:
    token_hash = hash_reset_token(token)
    reset_doc = await get_valid_password_reset_by_token_hash(token_hash)
    if not reset_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El token es inválido, ya fue usado o expiró.",
        )

    user_id = str(reset_doc["user_id"])
    user = await get_user_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo restablecer la contraseña.",
        )

    password_updated = await set_user_password(user_id=user_id, plain_password=new_password)
    if not password_updated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo restablecer la contraseña.",
        )

    await mark_password_reset_token_used(token_id=str(reset_doc["_id"]))
    await invalidate_active_tokens_for_user(user_id=user_id)

    try:
        await send_email(
            to_email=user.email,
            subject="Tu contraseña fue actualizada - Colficultor",
            html_body=_build_password_changed_email_html(),
        )
    except MailDeliveryError:
        logger.exception("Error enviando correo de confirmación para user_id=%s", user.id)

    return "Contraseña actualizada correctamente."
