from datetime import datetime

from fastapi import HTTPException, status

from app.repositories.orders_repository import user_has_paid_order_for_product
from app.repositories.reviews_repository import (
    ReviewAlreadyExistsError,
    create_review,
    get_product_owner_id,
    get_review_by_id,
    list_reviews_by_product,
    list_reviews_by_user,
    product_exists,
    set_review_reply,
)
from app.schemas.reviews import ReviewCreateRequest, ReviewReplyRequest


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
            detail="Solo puedes reseñar productos que ya compraste y cuyo pedido ya fue pagado o entregado",
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


async def reply_to_review_as_farmer(
    *,
    review_id: str,
    farmer_id: str,
    payload: ReviewReplyRequest,
) -> dict:
    review = await get_review_by_id(review_id)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reseña no encontrada",
        )

    owner_id = await get_product_owner_id(review.get("productId", ""))
    if not owner_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto asociado a la reseña no encontrado",
        )

    if owner_id != farmer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para responder esta reseña",
        )

    updated = await set_review_reply(review_id=review_id, reply_text=payload.respuesta.strip())
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reseña no encontrada",
        )
    return updated
