from datetime import datetime

from pydantic import BaseModel, Field


class ReviewCreateRequest(BaseModel):
    productId: str = Field(..., min_length=1)
    calificacion: int = Field(..., ge=1, le=5)
    comentario: str = Field(..., min_length=3, max_length=1200)


class ReviewResponse(BaseModel):
    id: str = Field(alias="_id")
    productId: str
    userId: str
    calificacion: int
    comentario: str
    createdAt: datetime
    updatedAt: datetime


class ProductReviewsResponse(BaseModel):
    productId: str
    promedio: float
    total: int
    items: list[ReviewResponse]
