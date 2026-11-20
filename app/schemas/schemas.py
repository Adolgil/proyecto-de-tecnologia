from typing import List, Optional
from pydantic import BaseModel, Field


class UsuarioCreate(BaseModel):
    email: str = Field(..., min_length=4, max_length=120)
    password: str = Field(..., min_length=4, max_length=100)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class IngredienteCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    cantidad: str = Field(..., min_length=1, max_length=60)


class IngredienteOut(BaseModel):
    id: int
    nombre: str
    cantidad: str

    class Config:
        from_attributes = True


class RecetaGeneradaLLM(BaseModel):
    nombre_plato: str
    ingredientes: List[str]
    pasos_preparacion: List[str]
    tiempo_estimado: str
    dificultad: str


class CalificacionCreate(BaseModel):
    puntuacion: int = Field(..., ge=1, le=5)
    comentario: Optional[str] = None
