import io
import logging
import re
import time
from uuid import uuid4

from cloudinary import uploader

from app.core.cloudinary import configure_cloudinary
from app.schemas.product_image import ProductImageMetadata

logger = logging.getLogger(__name__)


class CloudinaryService:
    def __init__(self) -> None:
        configure_cloudinary()

    @staticmethod
    def _slug_filename(filename: str) -> str:
        name = filename.rsplit(".", 1)[0].strip().lower()
        slug = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
        return slug or "image"

    async def upload_product_image(
        self,
        *,
        product_id: str,
        filename: str,
        file_bytes: bytes,
    ) -> ProductImageMetadata:
        folder = f"colficultor/products/{product_id}"
        slug = self._slug_filename(filename)
        public_id = f"{slug}-{int(time.time())}-{uuid4().hex[:8]}"

        result = uploader.upload(
            io.BytesIO(file_bytes),
            resource_type="image",
            folder=folder,
            public_id=public_id,
            unique_filename=False,
            overwrite=False,
        )

        return ProductImageMetadata(
            url=result.get("url", ""),
            secure_url=result.get("secure_url", ""),
            public_id=result["public_id"],
            asset_id=result["asset_id"],
            format=result.get("format"),
            width=result.get("width"),
            height=result.get("height"),
            bytes=result.get("bytes"),
        )

    async def delete_image(self, public_id: str) -> None:
        result = uploader.destroy(public_id, resource_type="image")
        status = result.get("result")
        if status not in {"ok", "not found"}:
            logger.error("Error eliminando imagen en Cloudinary: public_id=%s, result=%s", public_id, result)
            raise RuntimeError("No fue posible eliminar la imagen en Cloudinary")


_cloudinary_service: CloudinaryService | None = None


def get_cloudinary_service() -> CloudinaryService:
    global _cloudinary_service
    if _cloudinary_service is None:
        _cloudinary_service = CloudinaryService()
    return _cloudinary_service
