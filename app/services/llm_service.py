import json
import httpx
from fastapi import HTTPException, status
from app.config import settings
from app.schemas.schemas import RecetaGeneradaLLM


def build_recipe_prompt(ingredientes: list[dict]) -> str:
    items_texto = "\n".join([f"- {item['nombre']}: {item['cantidad']}" for item in ingredientes])
    return (
        "Genera una receta de cocina usando principalmente los siguientes ingredientes disponibles:\n"
        f"{items_texto}\n\n"
        "Responde EXCLUSIVAMENTE con un objeto JSON válido (sin markdown ni texto extra) "
        "con exactamente estas claves:\n"
        "{\n"
        '  "nombre_plato": "string",\n'
        '  "ingredientes": ["string con cantidad"],\n'
        '  "pasos_preparacion": ["paso 1", "paso 2"],\n'
        '  "tiempo_estimado": "string",\n'
        '  "dificultad": "Facil | Media | Dificil"\n'
        "}"
    )


def parse_llm_recipe_response(raw_content: str) -> RecetaGeneradaLLM:
    cleaned = raw_content.strip()
    if cleaned.startswith("`"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("`"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "`":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        data = json.loads(cleaned)
        return RecetaGeneradaLLM(**data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"El modelo no devolvió un JSON válido para la receta: {exc}",
        )


def generar_receta_con_llm(ingredientes: list[dict]) -> RecetaGeneradaLLM:
    if not ingredientes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes tener al menos un ingrediente en tu inventario para generar una receta.",
        )
    if not settings.LLM_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falta configurar LLM_API_KEY en el entorno.",
        )

    prompt = build_recipe_prompt(ingredientes)
    url = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.LLM_MODEL,
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "Eres un chef estructurador de recetas. Responde únicamente en JSON válido.",
            },
            {"role": "user", "content": prompt},
        ],
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
            return parse_llm_recipe_response(content)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error al consultar el proveedor LLM: {exc}",
        )
