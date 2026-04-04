"""
Rutas de autenticación con Google OAuth 2.0.

Endpoints:
  GET  /api/auth/google/init
       → Inicia el flujo: redirige al usuario a la pantalla de Google.

  GET  /api/auth/google/callback
       → Google redirige aquí con el código de autorización.
         • Usuario existente: crea JWT y redirige al frontend con ?token=...
         • Usuario nuevo:     crea token temporal y redirige con ?google_pending=...
         • Error:             redirige con ?google_error=...

  POST /api/auth/google/complete
       → El frontend envía el temp_token + rol elegido.
         Crea el usuario en BD y retorna el JWT.
"""

import logging

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.core.auth import create_access_token
from app.models.user import get_user_by_email, get_user_by_google_sub, create_google_user
from app.schemas.auth import Token
from app.schemas.google_auth import GoogleCompleteRegistration
from app.services.google_auth_service import (
    build_google_auth_url,
    create_oauth_state,
    verify_and_consume_state,
    exchange_code_for_user_info,
    create_pending_registration,
    consume_pending_registration,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/google", tags=["google-auth"])


# ─────────────────────────────────────────────────────────────────────────────
# 1. Iniciar flujo OAuth
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/init", summary="Iniciar autenticación con Google")
async def google_auth_init():
    """
    Genera un `state` CSRF, construye la URL de autorización de Google
    y redirige al navegador del usuario.
    """
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autenticación con Google no está configurada en el servidor.",
        )

    state = await create_oauth_state()
    auth_url = build_google_auth_url(state)
    return RedirectResponse(url=auth_url)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Callback de Google
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/callback", summary="Callback OAuth de Google")
async def google_auth_callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
):
    """
    Google redirige aquí después de que el usuario autoriza (o rechaza).
    Maneja tres casos:
      - Error explícito de Google.
      - State CSRF inválido o expirado.
      - Usuario nuevo o existente.
    """
    frontend = settings.FRONTEND_URL

    # — El usuario canceló o hubo error en Google —
    if error:
        logger.warning("Google OAuth retornó error: %s", error)
        return RedirectResponse(url=f"{frontend}?google_error=access_denied")

    # — Parámetros requeridos ausentes —
    if not code or not state:
        return RedirectResponse(url=f"{frontend}?google_error=invalid_request")

    # — Validar state CSRF —
    logger.info("[Google OAuth] Verificando state CSRF...")
    if not await verify_and_consume_state(state):
        logger.warning("[Google OAuth] State inválido o expirado: %s", state)
        return RedirectResponse(url=f"{frontend}?google_error=invalid_state")
    logger.info("[Google OAuth] State CSRF válido")

    # — Intercambiar código por info de usuario —
    logger.info("[Google OAuth] Intercambiando código por info de usuario...")
    try:
        user_info = await exchange_code_for_user_info(code)
    except Exception as exc:
        logger.error("[Google OAuth] Error al intercambiar código: %s", exc)
        return RedirectResponse(url=f"{frontend}?google_error=exchange_failed")

    google_sub: str | None = user_info.get("sub")
    email: str | None = user_info.get("email")
    logger.info("[Google OAuth] Info recibida — email: %s, sub: %s", email, google_sub)

    if not google_sub or not email:
        logger.error("[Google OAuth] userinfo incompleto: %s", user_info)
        return RedirectResponse(url=f"{frontend}?google_error=missing_info")

    # — Verificar si el usuario ya existe (por sub o por email) —
    existing = await get_user_by_google_sub(google_sub)
    logger.info("[Google OAuth] Búsqueda por google_sub: %s", "ENCONTRADO" if existing else "no encontrado")

    if not existing:
        existing = await get_user_by_email(email)
        logger.info("[Google OAuth] Búsqueda por email: %s", "ENCONTRADO" if existing else "no encontrado")

    if existing:
        if not existing.is_active:
            logger.warning("[Google OAuth] Cuenta inactiva: %s", email)
            return RedirectResponse(url=f"{frontend}?google_error=account_inactive")
        logger.info("[Google OAuth] Usuario existente → login directo (rol: %s)", existing.role.value)
        token = create_access_token(user_id=existing.id, role=existing.role.value)
        return RedirectResponse(url=f"{frontend}?token={token}")

    # — Usuario nuevo: guardar datos temporalmente y pedir rol —
    logger.info("[Google OAuth] Usuario NUEVO → redirigiendo a selección de rol")
    full_name: str = user_info.get("name") or email.split("@")[0]
    picture: str | None = user_info.get("picture")

    temp_token = await create_pending_registration(
        google_sub=google_sub,
        email=email,
        full_name=full_name,
        picture=picture,
    )
    logger.info("[Google OAuth] Token pendiente creado → redirigiendo a frontend con google_pending")
    return RedirectResponse(url=f"{frontend}?google_pending={temp_token}")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Completar registro (elegir rol)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/complete", response_model=Token, summary="Completar registro Google con rol")
async def google_complete_registration(payload: GoogleCompleteRegistration):
    """
    El frontend envía el `temp_token` (recibido en la URL) y el `role` elegido.
    Si el token es válido, se crea el usuario y se retorna el JWT de sesión.
    """
    # Consumir el token temporal (un solo uso)
    pending = await consume_pending_registration(payload.temp_token)
    if not pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de registro expiró o ya fue usado. Inicia sesión con Google nuevamente.",
        )

    # Race condition: verificar que el email no fue registrado en el ínterin
    existing = await get_user_by_email(pending["email"])
    if existing:
        if not existing.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="La cuenta está inactiva.",
            )
        # Ya existe → login directo
        token = create_access_token(user_id=existing.id, role=existing.role.value)
        return Token(access_token=token)

    # Crear el usuario en la base de datos
    user = await create_google_user(
        email=pending["email"],
        full_name=pending["full_name"],
        google_sub=pending["google_sub"],
        picture=pending.get("picture"),
        role=payload.role,
    )

    token = create_access_token(user_id=user.id, role=user.role.value)
    return Token(access_token=token)
