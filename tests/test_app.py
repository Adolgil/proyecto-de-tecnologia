import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import get_db
from app.models.models import Base
from app.main import app
from app.schemas.schemas import IngredienteCreate
from app.services.llm_service import build_recipe_prompt, parse_llm_recipe_response

TEST_DB_URL = "sqlite:///./test_recetas.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def test_1_validacion_ingrediente_vacio():
    with pytest.raises(ValidationError):
        IngredienteCreate(nombre="", cantidad="1 taza")


def test_2_validacion_ingrediente_valido():
    ing = IngredienteCreate(nombre="Tomate", cantidad="3 unidades")
    assert ing.nombre == "Tomate"
    assert ing.cantidad == "3 unidades"


def test_3_generacion_prompt_con_inventario():
    prompt = build_recipe_prompt([{"nombre": "Huevo", "cantidad": "4 unidades"}])
    assert "Huevo" in prompt
    assert "4 unidades" in prompt
    assert "nombre_plato" in prompt


def test_4_parseo_respuesta_llm_valida():
    raw = """
    {
      "nombre_plato": "Tortilla de huevo",
      "ingredientes": ["4 huevos", "sal al gusto"],
      "pasos_preparacion": ["Batir los huevos", "Freir a fuego medio"],
      "tiempo_estimado": "10 minutos",
      "dificultad": "Facil"
    }
    """
    receta = parse_llm_recipe_response(raw)
    assert receta.nombre_plato == "Tortilla de huevo"
    assert receta.dificultad == "Facil"


def test_5_parseo_respuesta_llm_invalida_lanza_error():
    with pytest.raises(Exception):
        parse_llm_recipe_response("no es un json valido")


def test_6_endpoint_registro_y_crear_ingrediente():
    res_reg = client.post("/auth/register", json={"email": "chef@test.com", "password": "secret"})
    assert res_reg.status_code == 201
    token = res_reg.json()["access_token"]

    res_ing = client.post(
        "/ingredientes",
        json={"nombre": "Arroz", "cantidad": "2 tazas"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_ing.status_code == 201
    assert res_ing.json()["nombre"] == "Arroz"