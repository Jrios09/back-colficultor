from datetime import datetime

from fastapi import HTTPException, status

from app.repositories.orders_repository import user_has_paid_order_for_product
from app.repositories.reviews_repository import (
    ReviewAlreadyExistsError,
    create_review,
    list_reviews_by_product,
    list_reviews_by_user,
    product_exists,
)
from app.schemas.reviews import ReviewCreateRequest


async def create_review_for_user(*, user_id: str, payload: ReviewCreateRequest) -> dict:
    if not await product_exists(payload.productId):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado",
        )

    has_paid_purchase = await user_has_paid_order_for_product(
        user_id=user_id,
        product_id=payload.productId,
    )
    if not has_paid_purchase:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo puedes reseñar productos que ya compraste en una orden pagada",
        )

    now = datetime.utcnow()
    review_doc = {
        "productId": payload.productId,
        "userId": user_id,
        "calificacion": payload.calificacion,
        "comentario": payload.comentario.strip(),
        "createdAt": now,
        "updatedAt": now,
    }

    try:
        return await create_review(review_doc)
    except ReviewAlreadyExistsError as ex:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya registraste una reseña para este producto",
        ) from ex


async def get_reviews_for_product(product_id: str) -> dict:
    if not await product_exists(product_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado",
        )

    reviews = await list_reviews_by_product(product_id)
    total = len(reviews)
    promedio = round(sum(r["calificacion"] for r in reviews) / total, 2) if total > 0 else 0.0

    return {
        "productId": product_id,
        "promedio": promedio,
        "total": total,
        "items": reviews,
    }


async def get_reviews_for_user(user_id: str) -> list[dict]:
    return await list_reviews_by_user(user_id)
