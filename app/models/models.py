from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(120), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow)

    ingredientes = relationship("Ingrediente", back_populates="usuario", cascade="all, delete-orphan")
    recetas = relationship("Receta", back_populates="usuario", cascade="all, delete-orphan")
    calificaciones = relationship("Calificacion", back_populates="usuario", cascade="all, delete-orphan")


class Ingrediente(Base):
    __tablename__ = "ingredientes"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    nombre = Column(String(100), nullable=False)
    cantidad = Column(String(60), nullable=False)

    usuario = relationship("Usuario", back_populates="ingredientes")


class Receta(Base):
    __tablename__ = "recetas"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    nombre_plato = Column(String(150), nullable=False)
    ingredientes_json = Column(Text, nullable=False)
    pasos_json = Column(Text, nullable=False)
    tiempo_estimado = Column(String(60), nullable=False)
    dificultad = Column(String(40), nullable=False)
    creada_en = Column(DateTime, default=datetime.utcnow)

    usuario = relationship("Usuario", back_populates="recetas")
    calificaciones = relationship("Calificacion", back_populates="receta", cascade="all, delete-orphan")


class Calificacion(Base):
    __tablename__ = "calificaciones"

    id = Column(Integer, primary_key=True, index=True)
    receta_id = Column(Integer, ForeignKey("recetas.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    puntuacion = Column(Integer, nullable=False)
    comentario = Column(Text, nullable=True)

    receta = relationship("Receta", back_populates="calificaciones")
    usuario = relationship("Usuario", back_populates="calificaciones")
