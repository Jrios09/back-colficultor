import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.core.config import settings
from app.core.rate_limit import InMemoryRateLimiter
from app.schemas.user import UserCreate, UserPublic, UserInDB
from app.schemas.auth import Token
from app.schemas.password_recovery import (
    ForgotPasswordRequest,
    GenericMessageResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    ResetPasswordValidateResponse,
)
from app.api.deps import get_current_user
from app.models.user import create_user, authenticate_user
from app.core.auth import create_access_token, revoke_token
from app.services.password_recovery_service import (
    request_password_reset,
    reset_password_with_token,
    validate_reset_token,
)
from app.services.recaptcha_service import verify_recaptcha_token


router = APIRouter(prefix="/api/auth", tags=["auth"])
_auth_rate_limiter = InMemoryRateLimiter()
_RATE_LIMIT_ERROR_MESSAGE = "Demasiados intentos. Intenta nuevamente más tarde."


class RecaptchaToken(BaseModel):
    recaptcha_token: str


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        real_ip = forwarded_for.split(",")[0].strip()
        if real_ip:
            return real_ip
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _normalize_identifier(value: str) -> str:
    return value.strip().lower()


def _is_dev_env() -> bool:
    return settings.APP_ENV.strip().lower() in {"dev", "development", "local"}


def _hash_key_part(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _enforce_rate_limit(*, key: str, limit: int, window_seconds: int) -> None:
    if _auth_rate_limiter.is_allowed(key=key, limit=limit, window_seconds=window_seconds):
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=_RATE_LIMIT_ERROR_MESSAGE,
    )


async def _verify_recaptcha(request: Request, *, expected_action: str | None = None) -> None:
    """Verifica reCAPTCHA v3. Lanza HTTPException si falla."""
    if not settings.RECAPTCHA_ENABLED:
        if _is_dev_env():
            return
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuración insegura: RECAPTCHA_ENABLED=false fuera de desarrollo",
        )

    recaptcha_token = request.headers.get("x-recaptcha-token")
    if not recaptcha_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de reCAPTCHA no proporcionado",
        )
    ok, score, msg = await verify_recaptcha_token(
        recaptcha_token,
        expected_action=expected_action,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Verificación de seguridad fallida{': ' + msg if msg else ''}",
        )


@router.post("/register", response_model=UserPublic)
async def register(user_in: UserCreate, request: Request):
    rate_key = f"auth:register:{_client_ip(request)}"
    _enforce_rate_limit(
        key=rate_key,
        limit=settings.AUTH_REGISTER_RATE_LIMIT,
        window_seconds=settings.AUTH_REGISTER_RATE_LIMIT_WINDOW_SECONDS,
    )
    await _verify_recaptcha(request, expected_action="register")
    return await create_user(user_in)


@router.post("/login", response_model=Token)
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    normalized_login = _normalize_identifier(form_data.username)
    rate_key = f"auth:login:{_client_ip(request)}:{_hash_key_part(normalized_login)}"
    _enforce_rate_limit(
        key=rate_key,
        limit=settings.AUTH_LOGIN_RATE_LIMIT,
        window_seconds=settings.AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )
    await _verify_recaptcha(request, expected_action="login")

    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )
    token = create_access_token(user_id=user.id, role=user.role.value)
    return Token(access_token=token)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    current: UserInDB = Depends(get_current_user),
):
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    await revoke_token(token)


@router.post("/forgot-password", response_model=GenericMessageResponse)
async def forgot_password(payload: ForgotPasswordRequest, request: Request):
    rate_key = f"auth:forgot-password:{_client_ip(request)}:{_hash_key_part(_normalize_identifier(payload.email))}"
    _enforce_rate_limit(
        key=rate_key,
        limit=settings.AUTH_FORGOT_PASSWORD_RATE_LIMIT,
        window_seconds=settings.AUTH_FORGOT_PASSWORD_RATE_LIMIT_WINDOW_SECONDS,
    )
    await _verify_recaptcha(request, expected_action="forgot_password")
    message = await request_password_reset(
        email=payload.email,
        client_ip=request.client.host if request.client else None,
    )
    return GenericMessageResponse(message=message)


@router.get("/reset-password/validate", response_model=ResetPasswordValidateResponse)
async def validate_password_reset_token(
    request: Request,
    token: str = Query(..., min_length=20, max_length=512),
):
    rate_key = f"auth:reset-password-validate:{_client_ip(request)}"
    _enforce_rate_limit(
        key=rate_key,
        limit=settings.AUTH_RESET_VALIDATE_RATE_LIMIT,
        window_seconds=settings.AUTH_RESET_VALIDATE_RATE_LIMIT_WINDOW_SECONDS,
    )

    await validate_reset_token(token)
    return ResetPasswordValidateResponse(valid=True, message="Token válido")


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(payload: ResetPasswordRequest, request: Request):
    normalized_token = payload.token.strip()
    rate_key = f"auth:reset-password:{_client_ip(request)}:{_hash_key_part(normalized_token)}"
    _enforce_rate_limit(
        key=rate_key,
        limit=settings.AUTH_RESET_PASSWORD_RATE_LIMIT,
        window_seconds=settings.AUTH_RESET_PASSWORD_RATE_LIMIT_WINDOW_SECONDS,
    )

    message = await reset_password_with_token(
        token=payload.token,
        new_password=payload.newPassword,
    )
    return ResetPasswordResponse(message=message)
