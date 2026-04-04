from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.deps import get_current_user
from app.schemas.product_image import (
    ProductImageDeleteResponse,
    ProductImageReplaceResponse,
    ProductImageResponse,
)
from app.schemas.user import UserInDB
from app.services.product_images_service import (
    delete_product_image,
    list_product_images,
    replace_product_image,
    upload_product_images,
)

router = APIRouter(prefix="/api/products", tags=["product-images"])


@router.post(
    "/{product_id}/images",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subir imágenes de un producto",
)
async def upload_images_endpoint(
    product_id: str,
    files: Annotated[list[UploadFile], File(description="Imágenes del producto")],
    current: UserInDB = Depends(get_current_user),
):
    images = await upload_product_images(product_id=product_id, files=files, current=current)
    return ProductImageResponse(product_id=product_id, images=images)


@router.get(
    "/{product_id}/images",
    response_model=ProductImageResponse,
    summary="Listar imágenes de un producto",
)
async def list_images_endpoint(
    product_id: str,
    current: UserInDB = Depends(get_current_user),
):
    images = await list_product_images(product_id=product_id, current=current)
    return ProductImageResponse(product_id=product_id, images=images)


@router.put(
    "/{product_id}/images",
    response_model=ProductImageReplaceResponse,
    summary="Reemplazar la imagen de un producto",
    description=(
        "Elimina todas las imágenes existentes del producto en Cloudinary y en la base de datos, "
        "y sube la nueva imagen proporcionada como imagen principal."
    ),
)
async def replace_image_endpoint(
    product_id: str,
    file: Annotated[UploadFile, File(description="Nueva imagen del producto")],
    current: UserInDB = Depends(get_current_user),
):
    image = await replace_product_image(product_id=product_id, file=file, current=current)
    return ProductImageReplaceResponse(product_id=product_id, image=image)


@router.delete(
    "/{product_id}/images/{image_id}",
    response_model=ProductImageDeleteResponse,
    summary="Eliminar imagen de un producto",
)
async def delete_image_endpoint(
    product_id: str,
    image_id: str,
    current: UserInDB = Depends(get_current_user),
):
    image = await delete_product_image(product_id=product_id, image_id=image_id, current=current)
    return ProductImageDeleteResponse(message="Imagen eliminada correctamente", image=image)
