"""Schemas Pydantic exclusivos del flujo de autenticación con Google OAuth 2.0."""

from pydantic import BaseModel
from app.schemas.user import UserRole


class GoogleCompleteRegistration(BaseModel):
    """
    Payload que envía el frontend para completar el registro de un usuario nuevo
    de Google, una vez que el usuario seleccionó su rol.

    - temp_token: token de un solo uso generado en el callback de Google.
    - role: rol elegido por el usuario ("caficultor" o "comprador").
    """
    temp_token: str
    role: UserRole
