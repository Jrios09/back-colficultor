from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class PqrTipo(str, Enum):
    PETICION = "PETICION"
    QUEJA = "QUEJA"
    RECLAMO = "RECLAMO"
    SOPORTE = "SOPORTE"


class PqrEstado(str, Enum):
    ABIERTO = "ABIERTO"
    EN_PROCESO = "EN_PROCESO"
    CERRADO = "CERRADO"


class PqrCreateRequest(BaseModel):
    tipo: PqrTipo
    asunto: str = Field(..., min_length=3, max_length=200)
    descripcion: str = Field(..., min_length=5, max_length=3000)


class PqrEstadoUpdateRequest(BaseModel):
    estado: PqrEstado


class PqrRespuestaRequest(BaseModel):
    respuesta: str = Field(..., min_length=3, max_length=3000)


class PqrTicketResponse(BaseModel):
    id: str = Field(alias="_id")
    userId: str
    tipo: PqrTipo
    asunto: str
    descripcion: str
    estado: PqrEstado
    respuesta: str | None = None
    createdAt: datetime
    updatedAt: datetime
