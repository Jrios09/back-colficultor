import httpx
from typing import Optional
from app.core.config import settings


def _is_dev_env() -> bool:
    return settings.APP_ENV.strip().lower() in {"dev", "development", "local"}


async def verify_recaptcha_token(
    token: str,
    *,
    expected_action: str | None = None,
) -> tuple[bool, Optional[float], str]:
    """
    Verifica un token de reCAPTCHA v3 con Google.

    Returns:
        tuple: (success: bool, score: Optional[float], error_message: str)
    """
    if not token:
        return False, None, "Token de reCAPTCHA no proporcionado"

    if not settings.RECAPTCHA_SECRET_KEY:
        if _is_dev_env():
            print("ADVERTENCIA: RECAPTCHA_SECRET_KEY no configurado — omitiendo verificación solo en dev")
            return True, 1.0, ""
        return False, None, "RECAPTCHA_SECRET_KEY no configurado en el servidor"

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

        if response.status_code != 200:
            return False, None, f"Respuesta inválida del proveedor reCAPTCHA: HTTP {response.status_code}"

        result = response.json()

        if not result.get("success", False):
            error_codes = result.get("error-codes", [])
            return False, None, f"reCAPTCHA inválido: {', '.join(error_codes) if error_codes else 'desconocido'}"

        score = result.get("score", 0.0)
        action = result.get("action", "")

        if expected_action and action != expected_action:
            return (
                False,
                score,
                f"Acción de reCAPTCHA inválida: esperada '{expected_action}', recibida '{action or 'vacía'}'",
            )

        if score < settings.RECAPTCHA_SCORE_THRESHOLD:
            return False, score, f"Puntuación demasiado baja ({score}) — posible bot"

        return True, score, ""

    except httpx.TimeoutException:
        return False, None, "Timeout al verificar reCAPTCHA con Google"
    except Exception as e:
        return False, None, f"Error al verificar reCAPTCHA: {str(e)}"
