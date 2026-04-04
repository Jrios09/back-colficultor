from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user, require_role
from app.schemas.reviews import ProductReviewsResponse, ReviewCreateRequest, ReviewResponse
from app.schemas.user import UserInDB, UserRole
from app.services.reviews_service import (
    create_review_for_user,
    get_reviews_for_product,
    get_reviews_for_user,
)

router = APIRouter(prefix="/api", tags=["resenas"])


@router.post("/resenas", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    payload: ReviewCreateRequest,
    current: UserInDB = Depends(require_role(UserRole.COMPRADOR)),
):
    return await create_review_for_user(user_id=current.id, payload=payload)


@router.get("/productos/{product_id}/resenas", response_model=ProductReviewsResponse)
async def list_product_reviews(product_id: str):
    return await get_reviews_for_product(product_id)


@router.get("/resenas/mis", response_model=list[ReviewResponse])
async def list_my_reviews(current: UserInDB = Depends(get_current_user)):
    return await get_reviews_for_user(current.id)
