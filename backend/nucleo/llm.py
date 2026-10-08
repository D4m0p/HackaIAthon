"""
Capa única para hablar con el LLM (Gemini).

Todo el proyecto llama a generar() y nada más. Así:
- Cambiar de modelo o de proveedor se hace solo aquí.
- Cada respuesta se guarda en caché: la misma pregunta no se paga dos veces y
  la demo funciona sin internet con lo que ya se calculó.
- Cada llamada queda registrada (modelo, tokens, tiempo) para las métricas.
"""

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from nucleo import config

CARPETA_BACKEND = Path(__file__).parent.parent
CARPETA_CACHE_LLM = CARPETA_BACKEND / config.CARPETA_CACHE / "llm"
RUTA_LOG = CARPETA_BACKEND / config.CARPETA_CACHE / "llm_log.jsonl"

load_dotenv(CARPETA_BACKEND / ".env")

_cliente = None


class LLMNoDisponible(Exception):
    """No se pudo obtener respuesta del LLM (sin internet, sin clave o error).
    Quien llama debe usar su plan de respaldo."""


def _obtener_cliente():
    global _cliente
    if _cliente is None:
        clave = os.environ.get("GEMINI_API_KEY")
        if not clave:
            raise LLMNoDisponible("Falta GEMINI_API_KEY en backend/.env")
        from google import genai
        _cliente = genai.Client(api_key=clave)
    return _cliente


def _clave_cache(modelo, instrucciones, contenido, esquema):
    texto = json.dumps([modelo, config.TEMPERATURA, instrucciones, contenido, esquema],
                       ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _registrar(datos):
    RUTA_LOG.parent.mkdir(parents=True, exist_ok=True)
    datos["fecha_utc"] = datetime.now(timezone.utc).isoformat()
    with open(RUTA_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(datos, ensure_ascii=False) + "\n")


def _codigo_error(e):
    """Nombre corto del error para el registro (ej. '503', 'ReadTimeout')."""
    return str(getattr(e, "code", None) or type(e).__name__)


def generar(instrucciones, contenido, esquema, modelos=config.MODELOS_RAPIDOS, tarea="sin_nombre"):
    """Pide al LLM una respuesta JSON que cumpla `esquema`.
    Devuelve (respuesta_como_dict, modelo_que_respondio).

    - instrucciones: qué debe hacer el modelo (va como instrucción de sistema).
    - contenido: los datos a procesar (titulares, evidencia). Va SEPARADO de las
      instrucciones: el texto de las fuentes es dato, nunca instrucción.
    - esquema: JSON Schema de la respuesta esperada.
    - modelos: lista en orden de preferencia; si uno falla se usa el siguiente.
    - tarea: nombre corto para el registro (ej. "clasificar_temas").
    """
    if isinstance(modelos, str):
        modelos = [modelos]
    clave = _clave_cache(modelos, instrucciones, contenido, esquema)
    ruta_cache = CARPETA_CACHE_LLM / f"{clave}.json"

    if ruta_cache.exists():
        guardado = json.loads(ruta_cache.read_text(encoding="utf-8"))
        _registrar({"tarea": tarea, "modelo": guardado["modelo"], "desde_cache": True})
        return guardado["respuesta"], guardado["modelo"]

    from google.genai import types

    cliente = _obtener_cliente()
    ajustes = types.GenerateContentConfig(
        system_instruction=instrucciones,
        temperature=config.TEMPERATURA,
        response_mime_type="application/json",
        response_json_schema=esquema,
        http_options=types.HttpOptions(timeout=config.TIMEOUT_LLM_SEGUNDOS * 1000),
    )

    errores = []
    for ronda in range(config.REINTENTOS_LLM):
        for modelo in modelos:
            inicio = time.time()
            try:
                respuesta = cliente.models.generate_content(model=modelo, contents=contenido, config=ajustes)
                resultado = json.loads(respuesta.text)
            except Exception as e:  # saturado (503), límite (429), sin internet, timeout, JSON roto...
                errores.append(f"{modelo}: {_codigo_error(e)}")
                _registrar({"tarea": tarea, "modelo": modelo, "desde_cache": False, "fallo": _codigo_error(e),
                            "segundos": round(time.time() - inicio, 2)})
                continue

            uso = respuesta.usage_metadata
            _registrar({
                "tarea": tarea,
                "modelo": modelo,
                "desde_cache": False,
                "segundos": round(time.time() - inicio, 2),
                "tokens_entrada": uso.prompt_token_count,
                "tokens_salida": uso.candidates_token_count,
                "tokens_total": uso.total_token_count,
            })
            CARPETA_CACHE_LLM.mkdir(parents=True, exist_ok=True)
            ruta_cache.write_text(json.dumps({"modelo": modelo, "respuesta": resultado},
                                             ensure_ascii=False, indent=2), encoding="utf-8")
            return resultado, modelo

        if ronda < config.REINTENTOS_LLM - 1:
            time.sleep(2 ** (ronda + 1))

    raise LLMNoDisponible("Ningún modelo respondió: " + "; ".join(errores))
