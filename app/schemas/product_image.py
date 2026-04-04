from pydantic import BaseModel, Field


class ProductImageMetadata(BaseModel):
    url: str
    secure_url: str
    public_id: str
    asset_id: str
    format: str | None = None
    width: int | None = None
    height: int | None = None
    bytes: int | None = None


class ProductImageResponse(BaseModel):
    product_id: str
    images: list[ProductImageMetadata] = Field(default_factory=list)


class ProductImageDeleteResponse(BaseModel):
    message: str
    image: ProductImageMetadata
