"""
Servicio de autenticación con Google OAuth 2.0.

Responsabilidades:
  1. Construir la URL de autorización de Google.
  2. Gestionar el parámetro `state` para protección CSRF
     (almacenado en MongoDB con TTL de 10 minutos, de un solo uso).
  3. Intercambiar el código de autorización por info de usuario
     (usando el endpoint userinfo de Google).
  4. Gestionar tokens temporales para registros pendientes de rol
     (almacenados en MongoDB con TTL de 15 minutos, de un solo uso).

No depende de librerías externas adicionales: usa `httpx` (ya instalado)
y `python-jose` / primitivas de la stdlib.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.db.mongodb import get_oauth_states_collection, get_google_pending_collection

# ── Constantes Google OAuth ────────────────────────────────────────────────────
_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
_GOOGLE_SCOPES = "openid email profile"

# ── TTLs ───────────────────────────────────────────────────────────────────────
_STATE_TTL_SECONDS = 600    # 10 minutos para completar el flujo OAuth
_PENDING_TTL_SECONDS = 900  # 15 minutos para seleccionar el rol


# ─────────────────────────────────────────────────────────────────────────────
# URL de autorización
# ─────────────────────────────────────────────────────────────────────────────

def build_google_auth_url(state: str) -> str:
    """Construye la URL de redirección a la pantalla de consent de Google."""
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_CALLBACK_URL,
        "response_type": "code",
        "scope": _GOOGLE_SCOPES,
        "state": state,
        "access_type": "online",
        # Fuerza la pantalla de selección de cuenta (mejor UX para multi-cuenta)
        "prompt": "select_account",
    }
    return f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"


# ─────────────────────────────────────────────────────────────────────────────
# Manejo de state CSRF
# ─────────────────────────────────────────────────────────────────────────────

async def create_oauth_state() -> str:
    """
    Genera un valor `state` aleatorio y lo guarda en MongoDB.
    El índice TTL lo elimina automáticamente tras 10 minutos.
    """
    state = secrets.token_urlsafe(32)
    col = get_oauth_states_collection()
    await col.insert_one({
        "state": state,
        "expires_at": datetime.utcnow() + timedelta(seconds=_STATE_TTL_SECONDS),
    })
    return state


async def verify_and_consume_state(state: str) -> bool:
    """
    Verifica que el `state` existe, no expiró y lo elimina (un solo uso).
    Retorna True si es válido, False si no existe o está expirado.
    """
    col = get_oauth_states_collection()
    result = await col.find_one_and_delete({
        "state": state,
        "expires_at": {"$gt": datetime.utcnow()},
    })
    return result is not None


# ─────────────────────────────────────────────────────────────────────────────
# Intercambio de código → info de usuario
# ─────────────────────────────────────────────────────────────────────────────

async def exchange_code_for_user_info(code: str) -> dict:
    """
    Realiza dos llamadas a Google:
      1. Intercambia el código por un access_token.
      2. Obtiene el perfil del usuario con ese token.

    Retorna un dict con al menos: sub, email, name, picture.
    Lanza ValueError si algo falla.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        # — Paso 1: intercambiar código por tokens —
        token_resp = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_CALLBACK_URL,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise ValueError(
                f"Google token exchange falló: {token_resp.status_code} {token_resp.text}"
            )
        tokens = token_resp.json()

        access_token = tokens.get("access_token")
        if not access_token:
            raise ValueError("Google no retornó access_token")

        # — Paso 2: obtener información del usuario —
        userinfo_resp = await client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code != 200:
            raise ValueError(
                f"Google userinfo falló: {userinfo_resp.status_code} {userinfo_resp.text}"
            )
        return userinfo_resp.json()


# ─────────────────────────────────────────────────────────────────────────────
# Token temporal para registro pendiente
# ─────────────────────────────────────────────────────────────────────────────

def _hash_token(token: str) -> str:
    """SHA-256 del token — solo el hash se persiste, nunca el token en claro."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_pending_registration(
    google_sub: str,
    email: str,
    full_name: str,
    picture: str | None,
) -> str:
    """
    Crea un registro temporal en `google_pending` con la info del usuario Google.
    El usuario debe completar el registro eligiendo un rol.

    Retorna el token en claro (solo se envía al frontend una vez).
    Solo el hash se almacena en la BD.
    """
    temp_token = secrets.token_urlsafe(48)
    col = get_google_pending_collection()
    await col.insert_one({
        "temp_token_hash": _hash_token(temp_token),
        "google_sub": google_sub,
        "email": email,
        "full_name": full_name,
        "picture": picture,
        "expires_at": datetime.utcnow() + timedelta(seconds=_PENDING_TTL_SECONDS),
    })
    return temp_token


async def consume_pending_registration(temp_token: str) -> dict | None:
    """
    Busca el registro pendiente por hash del token, lo elimina (un solo uso)
    y lo retorna.
    Retorna None si el token no existe o expiró.
    """
    col = get_google_pending_collection()
    result = await col.find_one_and_delete({
        "temp_token_hash": _hash_token(temp_token),
        "expires_at": {"$gt": datetime.utcnow()},
    })
    return result
