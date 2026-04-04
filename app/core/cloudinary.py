import logging

import cloudinary

from app.core.config import settings

logger = logging.getLogger(__name__)

_is_configured = False


def configure_cloudinary() -> None:
    """Configura Cloudinary una sola vez usando variables de entorno."""
    global _is_configured

    if _is_configured:
        return

    required = {
        "CLOUDINARY_CLOUD_NAME": settings.CLOUDINARY_CLOUD_NAME,
        "CLOUDINARY_API_KEY": settings.CLOUDINARY_API_KEY,
        "CLOUDINARY_API_SECRET": settings.CLOUDINARY_API_SECRET,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise RuntimeError(
            f"Configuración incompleta de Cloudinary. Faltan: {', '.join(missing)}"
        )

    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )
    _is_configured = True
    logger.info("Cloudinary configurado correctamente")
