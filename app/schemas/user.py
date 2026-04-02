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

class UserUpdate(BaseModel):
    """Campos que un usuario puede editarsolos."""
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)