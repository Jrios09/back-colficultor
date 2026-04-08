import logging
from dataclasses import dataclass

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.models.producto import (
    append_producto_imagenes,
    clear_producto_imagenes,
    get_producto_by_id,
    remove_producto_imagen_por_id,
)
from app.schemas.product_image import ProductImageMetadata
from app.schemas.user import UserInDB, UserRole
from app.services.cloudinary_service import get_cloudinary_service

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@dataclass
class ValidatedUpload:
    filename: str
    content_type: str
    data: bytes


def _is_admin(user: UserInDB) -> bool:
    return user.role == UserRole.ADMIN


def _can_manage_product_images(user: UserInDB, product: dict) -> bool:
    if user.role not in {UserRole.CAFICULTOR, UserRole.ADMIN}:
        return False
    if _is_admin(user):
        return True
    return product.get("caficultor_id") == user.id


def _get_cloudinary_or_raise():
    try:
        return get_cloudinary_service()
    except RuntimeError as exc:
        logger.exception("Cloudinary no está configurado correctamente")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


async def _validate_file(file: UploadFile) -> ValidatedUpload:
    content_type = file.content_type or ""
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Tipo de archivo no permitido: {content_type}",
        )

    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"El archivo '{file.filename or 'image'}' está vacío",
        )

    if len(data) > settings.PRODUCT_IMAGE_MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"El archivo '{file.filename or 'image'}' supera el tamaño máximo "
                f"de {settings.PRODUCT_IMAGE_MAX_SIZE_BYTES} bytes"
            ),
        )

    return ValidatedUpload(
        filename=file.filename or "image",
        content_type=content_type,
        data=data,
    )


async def upload_product_images(
    *,
    product_id: str,
    files: list[UploadFile],
    current: UserInDB,
) -> list[ProductImageMetadata]:
    product = await get_producto_by_id(product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    if not _can_manage_product_images(current, product):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para gestionar imágenes de este producto")

    if not files:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Debes enviar al menos una imagen")

    existing_images = product.get("imagenes", [])
    if len(existing_images) + len(files) > settings.PRODUCT_IMAGE_MAX_FILES_PER_PRODUCT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Se excede el máximo de imágenes por producto "
                f"({settings.PRODUCT_IMAGE_MAX_FILES_PER_PRODUCT})"
            ),
        )

    validated_files = [await _validate_file(file) for file in files]
    cloudinary = _get_cloudinary_or_raise()

    uploaded: list[ProductImageMetadata] = []
    try:
        for file in validated_files:
            image = await cloudinary.upload_product_image(
                product_id=product_id,
                filename=file.filename,
                file_bytes=file.data,
            )
            uploaded.append(image)
    except Exception as exc:
        logger.exception("Fallo subiendo imagen(es) a Cloudinary para producto %s", product_id)
        for image in uploaded:
            try:
                await cloudinary.delete_image(image.public_id)
            except Exception:
                logger.exception("Error en rollback de Cloudinary para public_id=%s", image.public_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No fue posible subir las imágenes a Cloudinary",
        ) from exc

    try:
        await append_producto_imagenes(
            producto_id=product_id,
            nuevas_imagenes=[image.model_dump() for image in uploaded],
        )
    except Exception as exc:
        logger.exception("Fallo guardando metadatos de imágenes en MongoDB para producto %s", product_id)
        for image in uploaded:
            try:
                await cloudinary.delete_image(image.public_id)
            except Exception:
                logger.exception("Error limpiando Cloudinary tras fallo en MongoDB: public_id=%s", image.public_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible guardar las imágenes en el producto",
        ) from exc

    return uploaded


async def list_product_images(*, product_id: str, current: UserInDB) -> list[ProductImageMetadata]:
    product = await get_producto_by_id(product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    if not _can_manage_product_images(current, product):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para ver imágenes de este producto")

    return [ProductImageMetadata(**img) for img in product.get("imagenes", [])]


async def delete_product_image(*, product_id: str, image_id: str, current: UserInDB) -> ProductImageMetadata:
    product = await get_producto_by_id(product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    if not _can_manage_product_images(current, product):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para gestionar imágenes de este producto")

    target = None
    for image in product.get("imagenes", []):
        if image.get("asset_id") == image_id or image.get("public_id") == image_id:
            target = image
            break

    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imagen no encontrada en el producto")

    cloudinary = _get_cloudinary_or_raise()
    try:
        await cloudinary.delete_image(target["public_id"])
    except Exception as exc:
        logger.exception("No fue posible eliminar la imagen %s en Cloudinary", target["public_id"])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No fue posible eliminar la imagen en Cloudinary",
        ) from exc

    _, removed = await remove_producto_imagen_por_id(producto_id=product_id, image_id=image_id)
    return ProductImageMetadata(**removed)


async def replace_product_image(
    *,
    product_id: str,
    file: UploadFile,
    current: UserInDB,
) -> ProductImageMetadata:
    """Reemplaza todas las imágenes del producto por una nueva.

    Orden de operaciones:
    1. Sube la nueva imagen a Cloudinary.
    2. Elimina las imágenes anteriores de Cloudinary.
    3. Actualiza MongoDB con solo la nueva imagen.

    Si el paso 3 falla se borra la imagen recién subida (rollback) para no
    dejar huérfanos en Cloudinary.
    """
    product = await get_producto_by_id(product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    if not _can_manage_product_images(current, product):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para gestionar imágenes de este producto",
        )

    validated = await _validate_file(file)
    cloudinary = _get_cloudinary_or_raise()

    # 1. Subir nueva imagen
    try:
        new_image = await cloudinary.upload_product_image(
            product_id=product_id,
            filename=validated.filename,
            file_bytes=validated.data,
        )
    except Exception as exc:
        logger.exception("Fallo subiendo nueva imagen a Cloudinary para producto %s", product_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No fue posible subir la imagen a Cloudinary",
        ) from exc

    # 2. Eliminar imágenes anteriores de Cloudinary (best-effort)
    for old in product.get("imagenes", []):
        public_id = old.get("public_id")
        if not public_id:
            continue
        try:
            await cloudinary.delete_image(public_id)
        except Exception:
            logger.warning(
                "No se pudo eliminar imagen anterior de Cloudinary: public_id=%s — se continúa",
                public_id,
            )

    # 3. Actualizar MongoDB
    try:
        await clear_producto_imagenes(producto_id=product_id)
        await append_producto_imagenes(
            producto_id=product_id,
            nuevas_imagenes=[new_image.model_dump()],
        )
    except Exception as exc:
        logger.exception(
            "Fallo actualizando MongoDB tras reemplazar imagen del producto %s — "
            "intentando rollback en Cloudinary",
            product_id,
        )
        try:
            await cloudinary.delete_image(new_image.public_id)
        except Exception:
            logger.exception(
                "Error en rollback: no se pudo borrar nueva imagen huérfana public_id=%s",
                new_image.public_id,
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible guardar la nueva imagen en el producto",
        ) from exc

    return new_image


async def delete_all_product_images_for_product(product: dict) -> None:
    images = product.get("imagenes", [])
    if not images:
        return

    cloudinary = None
    try:
        cloudinary = _get_cloudinary_or_raise()
    except HTTPException:
        logger.warning(
            "Cloudinary no disponible al eliminar producto=%s. Se limpiarán solo metadatos en MongoDB.",
            product.get("_id"),
        )

    deleted_count = 0
    failed_count = 0
    if cloudinary is not None:
        for image in images:
            public_id = image.get("public_id")
            if not public_id:
                continue
            try:
                await cloudinary.delete_image(public_id)
                deleted_count += 1
            except Exception:
                failed_count += 1
                logger.warning(
                    "No se pudo eliminar imagen de Cloudinary para producto=%s public_id=%s",
                    product["_id"],
                    public_id,
                )

    try:
        await clear_producto_imagenes(producto_id=product["_id"])
    except Exception:
        logger.warning(
            "No se pudieron limpiar metadatos de imágenes en MongoDB para producto=%s",
            product["_id"],
        )

    logger.info(
        "Eliminación de imágenes para producto=%s: eliminadas=%s fallidas=%s",
        product["_id"],
        deleted_count,
        failed_count,
    )
