import httpx
from typing import Optional
from app.core.config import settings


async def verify_recaptcha_token(token: str) -> tuple[bool, Optional[float], str]:
    """
    Verifica un token de reCAPTCHA v3 con Google.

    Returns:
        tuple: (success: bool, score: Optional[float], error_message: str)
    """
    if not token:
        return False, None, "Token de reCAPTCHA no proporcionado"

    if not settings.RECAPTCHA_SECRET_KEY:
        # Si no está configurado, Permitir en desarrollo
        print("ADVERTENCIA: RECAPTCHA_SECRET_KEY no configurado — omitiendo verificación")
        return True, 1.0, ""

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.RECAPTCHA_VERIFY_URL,
                data={
                    "secret": settings.RECAPTCHA_SECRET_KEY,
                    "response": token,
                },
                timeout=10.0,
            )

        result = response.json()

        if not result.get("success", False):
            error_codes = result.get("error-codes", [])
            return False, None, f"reCAPTCHA inválido: {', '.join(error_codes) if error_codes else 'desconocido'}"

        score = result.get("score", 0.0)
        action = result.get("action", "")

        if score < settings.RECAPTCHA_SCORE_THRESHOLD:
            return False, score, f"Puntuación demasiado baja ({score}) — posible bot"

        return True, score, ""

    except httpx.TimeoutException:
        return False, None, "Timeout al verificar reCAPTCHA con Google"
    except Exception as e:
        return False, None, f"Error al verificar reCAPTCHA: {str(e)}"
