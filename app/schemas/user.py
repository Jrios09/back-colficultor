from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from enum import Enum
from typing import Optional

class UserRole(str, Enum):
    CAFICULTOR = "caficultor"
    COMPRADOR = "comprador"
    ADMIN = "admin"

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=100)
    role: UserRole = UserRole.COMPRADOR
    is_active: bool = True

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserInDB(UserBase):
    id: str = Field(alias="_id")
    password_hash: str
    created_at: datetime
    updated_at: datetime

class UserPublic(BaseModel):
    id: str = Field(alias="_id")
    email: EmailStr
    full_name: Optional[str]
    role: UserRole
    is_active: bool
    created_at: datetime

class PerfilUpdate(BaseModel):
    """
    Campos editables del perfil de usuario.
    Nunca incluye role, is_active o password_hash.
    """
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    perfil_ciudad: Optional[str] = Field(None, max_length=100)
    perfil_departamento: Optional[str] = Field(None, max_length=100)
    perfil_direccion: Optional[str] = Field(None, max_length=200)
    perfil_telefono: Optional[str] = Field(None, max_length=20)
    perfil_preferencias: Optional[str] = Field(None, max_length=500)