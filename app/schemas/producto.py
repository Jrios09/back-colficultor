from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ProductoBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=200)
    descripcion: str = Field(..., max_length=2000)
    precio: float = Field(..., gt=0, description="Precio en COP, debe ser mayor a 0")
    stock: int = Field(..., ge=0, description="Cantidad disponible, 0 o más")
    region: str = Field(..., max_length=100, description="Región de origen del café")


class ProductoCreate(ProductoBase):
    """Payload para crear un producto nuevo."""
    pass


class ProductoUpdate(BaseModel):
    """
    Payload para actualizar un producto existente.
    Todos los campos son opcionales para permitir actualización parcial (PATCH).
    """
    nombre: Optional[str] = Field(None, min_length=1, max_length=200)
    descripcion: Optional[str] = Field(None, max_length=2000)
    precio: Optional[float] = Field(None, gt=0)
    stock: Optional[int] = Field(None, ge=0)
    region: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = Field(None, description="Activar o desactivar producto")


class ProductoInDB(ProductoBase):
    """Representación completa del producto tal como se almacena en MongoDB."""
    id: str = Field(alias="_id")
    caficultor_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductoPublic(BaseModel):
    """Producto expuesto al cliente (sin internals como password_hash de otras entidades)."""
    id: str = Field(alias="_id")
    caficultor_id: str
    nombre: str
    descripcion: str
    precio: float
    stock: int
    region: str
    is_active: bool
    created_at: datetime
