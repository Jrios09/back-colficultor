from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class CatalogSort(str, Enum):
    PRECIO_ASC = "precio_asc"
    PRECIO_DESC = "precio_desc"
    RECIENTES = "recientes"


class CatalogItem(BaseModel):
    id: str = Field(alias="_id")
    caficultor_id: str
    nombre: str
    descripcion: str
    precio: float
    stock: int
    region: str
    is_active: bool
    created_at: datetime


class CatalogListResponse(BaseModel):
    items: list[CatalogItem]
    total: int
    page: int
    limit: int
