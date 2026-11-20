import json
from typing import List
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.database import Base, engine, get_db
from app.models.models import Calificacion, Ingrediente, Receta, Usuario
from app.schemas.schemas import (
    CalificacionCreate,
    IngredienteCreate,
    IngredienteOut,
    Token,
    UsuarioCreate,
)
from app.services.llm_service import generar_receta_con_llm

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Generador de Recetas con Inventario e IA")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse("static/favicon.ico")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/auth/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(payload: UsuarioCreate, db: Session = Depends(get_db)):
    exists = db.query(Usuario).filter(Usuario.email == payload.email).first()
    if exists:
        raise HTTPException(status_code=400, detail="El correo ya está registrado.")
    user = Usuario(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": user.email})
    return {"access_token": token, "token_type": "bearer"}


@app.post("/auth/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")
    token = create_access_token({"sub": user.email})
    return {"access_token": token, "token_type": "bearer"}


@app.get("/ingredientes", response_model=List[IngredienteOut])
def listar_ingredientes(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Ingrediente).filter(Ingrediente.usuario_id == current_user.id).all()


@app.post("/ingredientes", response_model=IngredienteOut, status_code=status.HTTP_201_CREATED)
def crear_ingrediente(
    payload: IngredienteCreate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ing = Ingrediente(usuario_id=current_user.id, nombre=payload.nombre.strip(), cantidad=payload.cantidad.strip())
    db.add(ing)
    db.commit()
    db.refresh(ing)
    return ing


@app.put("/ingredientes/{ingrediente_id}", response_model=IngredienteOut)
def actualizar_ingrediente(
    ingrediente_id: int,
    payload: IngredienteCreate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ing = (
        db.query(Ingrediente)
        .filter(Ingrediente.id == ingrediente_id, Ingrediente.usuario_id == current_user.id)
        .first()
    )
    if not ing:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado.")
    ing.nombre = payload.nombre.strip()
    ing.cantidad = payload.cantidad.strip()
    db.commit()
    db.refresh(ing)
    return ing


@app.delete("/ingredientes/{ingrediente_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_ingrediente(
    ingrediente_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ing = (
        db.query(Ingrediente)
        .filter(Ingrediente.id == ingrediente_id, Ingrediente.usuario_id == current_user.id)
        .first()
    )
    if not ing:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado.")
    db.delete(ing)
    db.commit()


@app.post("/recetas/generar", status_code=status.HTTP_201_CREATED)
def generar_receta(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    ingredientes = db.query(Ingrediente).filter(Ingrediente.usuario_id == current_user.id).all()
    inv_list = [{"nombre": i.nombre, "cantidad": i.cantidad} for i in ingredientes]
    receta_llm = generar_receta_con_llm(inv_list)

    receta = Receta(
        usuario_id=current_user.id,
        nombre_plato=receta_llm.nombre_plato,
        ingredientes_json=json.dumps(receta_llm.ingredientes, ensure_ascii=False),
        pasos_json=json.dumps(receta_llm.pasos_preparacion, ensure_ascii=False),
        tiempo_estimado=receta_llm.tiempo_estimado,
        dificultad=receta_llm.dificultad,
    )
    db.add(receta)
    db.commit()
    db.refresh(receta)
    return {
        "id": receta.id,
        "nombre_plato": receta.nombre_plato,
        "ingredientes": receta_llm.ingredientes,
        "pasos_preparacion": receta_llm.pasos_preparacion,
        "tiempo_estimado": receta.tiempo_estimado,
        "dificultad": receta.dificultad,
        "calificaciones": [],
    }


@app.get("/recetas")
def historial_recetas(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    recetas = (
        db.query(Receta)
        .filter(Receta.usuario_id == current_user.id)
        .order_by(Receta.id.desc())
        .all()
    )
    resultado = []
    for r in recetas:
        califs = [{"id": c.id, "puntuacion": c.puntuacion, "comentario": c.comentario} for c in r.calificaciones]
        resultado.append(
            {
                "id": r.id,
                "nombre_plato": r.nombre_plato,
                "ingredientes": json.loads(r.ingredientes_json),
                "pasos_preparacion": json.loads(r.pasos_json),
                "tiempo_estimado": r.tiempo_estimado,
                "dificultad": r.dificultad,
                "calificaciones": califs,
            }
        )
    return resultado


@app.post("/recetas/{receta_id}/calificar", status_code=status.HTTP_201_CREATED)
def calificar_receta(
    receta_id: int,
    payload: CalificacionCreate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    receta = db.query(Receta).filter(Receta.id == receta_id, Receta.usuario_id == current_user.id).first()
    if not receta:
        raise HTTPException(status_code=404, detail="Receta no encontrada.")
    calif = Calificacion(
        receta_id=receta.id,
        usuario_id=current_user.id,
        puntuacion=payload.puntuacion,
        comentario=payload.comentario,
    )
    db.add(calif)
    db.commit()
    db.refresh(calif)
    return {"id": calif.id, "receta_id": receta.id, "puntuacion": calif.puntuacion, "comentario": calif.comentario}


@app.delete("/recetas/{receta_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_receta(
    receta_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    receta = db.query(Receta).filter(Receta.id == receta_id, Receta.usuario_id == current_user.id).first()
    if not receta:
        raise HTTPException(status_code=404, detail="Receta no encontrada.")
    db.delete(receta)
    db.commit()
