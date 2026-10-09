"""
Capa única para hablar con el LLM (Gemini y, como respaldo, Groq).

Todo el proyecto llama a generar() y nada más. Así:
- Cambiar de modelo o de proveedor se hace solo aquí (config.MODELOS_*).
- Cada respuesta se guarda en caché: la misma pregunta no se paga dos veces y
  la demo funciona sin internet con lo que ya se calculó.
- Cada llamada queda registrada (modelo, tokens, tiempo) para las métricas.

Los modelos se nombran así en config.py:
- "gemini-3.8-flash"                     -> Gemini (GEMINI_API_KEY)
- "groq:openai/gpt-oss-120b"             -> Groq   (GROQ_API_KEY)
Si falta la clave de un proveedor, sus modelos se saltan sin error.
"""

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from nucleo import config

CARPETA_BACKEND = Path(__file__).parent.parent
CARPETA_CACHE_LLM = CARPETA_BACKEND / config.CARPETA_CACHE / "llm"
RUTA_LOG = CARPETA_BACKEND / config.CARPETA_CACHE / "llm_log.jsonl"
URL_GROQ = "https://api.groq.com/openai/v1/chat/completions"

load_dotenv(CARPETA_BACKEND / ".env")

_cliente = None
# Modelos que respondieron 429 (cuota agotada) durante esta ejecución
_modelos_sin_cuota = set()


class LLMNoDisponible(Exception):
    """No se pudo obtener respuesta del LLM (sin internet, sin clave o error).
    Quien llama debe usar su plan de respaldo."""


class ErrorProveedor(Exception):
    """Error de un proveedor con un código corto ('429', '503', 'sin_clave', 'esquema'...)."""

    def __init__(self, code, detalle=""):
        super().__init__(f"{code} {detalle}".strip())
        self.code = code


def _obtener_cliente():
    global _cliente
    if _cliente is None:
        clave = os.environ.get("GEMINI_API_KEY")
        if not clave:
            raise ErrorProveedor("sin_clave", "falta GEMINI_API_KEY en backend/.env")
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


# ---------------------------------------------------------------------------
# Proveedores: cada uno devuelve (resultado_dict, uso_dict)
# ---------------------------------------------------------------------------
def _llamar_gemini(modelo, instrucciones, contenido, esquema):
    from google.genai import types
    ajustes = types.GenerateContentConfig(
        system_instruction=instrucciones,
        temperature=config.TEMPERATURA,
        response_mime_type="application/json",
        response_json_schema=esquema,
        http_options=types.HttpOptions(timeout=config.TIMEOUT_LLM_SEGUNDOS * 1000),
    )
    respuesta = _obtener_cliente().models.generate_content(model=modelo, contents=contenido, config=ajustes)
    uso = respuesta.usage_metadata
    return json.loads(respuesta.text), {
        "tokens_entrada": uso.prompt_token_count,
        "tokens_salida": uso.candidates_token_count,
        "tokens_total": uso.total_token_count,
    }


def _llamar_groq(modelo, instrucciones, contenido, esquema):
    """Groq usa la API estilo OpenAI. Pide JSON y le pasa el esquema en las
    instrucciones; después se verifica que la respuesta lo cumpla."""
    import httpx

    clave = os.environ.get("GROQ_API_KEY")
    if not clave:
        raise ErrorProveedor("sin_clave", "falta GROQ_API_KEY en backend/.env")
    sistema = (f"{instrucciones}\n\nResponde SOLO con un objeto JSON válido que cumpla este JSON Schema:\n"
               f"{json.dumps(esquema, ensure_ascii=False)}")
    cuerpo = {
        "model": modelo,
        "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": contenido}],
        "temperature": config.TEMPERATURA,
        "response_format": {"type": "json_object"},
        # Groq reserva de antemano los tokens de salida contra el límite por minuto:
        # sin este tope reservaría el máximo del modelo y respondería 429 siempre
        "max_completion_tokens": config.GROQ_MAX_TOKENS_SALIDA,
    }
    if modelo.startswith("openai/gpt-oss"):
        # Estos modelos "piensan" antes de responder; en nivel bajo gastan muchos menos tokens
        cuerpo["reasoning_effort"] = "low"
    for intento in range(2):
        respuesta = httpx.post(URL_GROQ, headers={"Authorization": f"Bearer {clave}"}, json=cuerpo,
                               timeout=config.TIMEOUT_LLM_SEGUNDOS)
        if respuesta.status_code != 429:
            break
        # 429 por tokens por minuto: Groq dice cuánto esperar. Si es poco, se espera y se
        # reintenta; si se agotó el cupo diario de llamadas, el modelo queda sin cuota
        sin_cupo_diario = respuesta.headers.get("x-ratelimit-remaining-requests") == "0"
        espera = _segundos(respuesta.headers.get("retry-after") or respuesta.headers.get("x-ratelimit-reset-tokens"))
        if sin_cupo_diario:
            raise ErrorProveedor("429")  # cupo diario agotado: el modelo queda sin cuota
        if intento == 1 or espera is None or espera > config.GROQ_ESPERA_MAXIMA:
            raise ErrorProveedor("429_minuto")  # límite por minuto: se podrá volver a usar
        time.sleep(espera + 1)
    if respuesta.status_code != 200:
        raise ErrorProveedor(str(respuesta.status_code))
    datos = respuesta.json()
    uso = datos.get("usage", {})
    return json.loads(datos["choices"][0]["message"]["content"]), {
        "tokens_entrada": uso.get("prompt_tokens"),
        "tokens_salida": uso.get("completion_tokens"),
        "tokens_total": uso.get("total_tokens"),
    }


def _segundos(valor):
    """Convierte '19.672s', '142ms', '1m30s' o '20' a segundos (None si no se entiende)."""
    if not valor:
        return None
    if valor.replace(".", "", 1).isdigit():
        return float(valor)
    total, numero = 0.0, ""
    unidades = {"h": 3600, "m": 60, "s": 1, "ms": 0.001}
    for parte in re.findall(r"[\d.]+|[a-z]+", valor):
        if parte[0].isdigit():
            numero = parte
        elif parte in unidades and numero:
            total += float(numero) * unidades[parte]
            numero = ""
        else:
            return None
    return total


def _cumple_esquema(dato, esquema):
    """Verificación simple del JSON Schema: tipos, campos obligatorios y valores
    permitidos. Gemini ya lo garantiza; Groq solo garantiza que sea JSON."""
    tipo = esquema.get("type")
    if tipo == "object":
        if not isinstance(dato, dict) or any(c not in dato for c in esquema.get("required", [])):
            return False
        return all(_cumple_esquema(dato[c], sub) for c, sub in esquema.get("properties", {}).items() if c in dato)
    if tipo == "array":
        return (isinstance(dato, list) and len(dato) >= esquema.get("minItems", 0)
                and all(_cumple_esquema(x, esquema.get("items", {})) for x in dato))
    if tipo == "string":
        return isinstance(dato, str) and ("enum" not in esquema or dato in esquema["enum"])
    return True


def _llamar(modelo, instrucciones, contenido, esquema):
    if modelo.startswith("groq:"):
        resultado, uso = _llamar_groq(modelo.removeprefix("groq:"), instrucciones, contenido, esquema)
    else:
        resultado, uso = _llamar_gemini(modelo, instrucciones, contenido, esquema)
    if not _cumple_esquema(resultado, esquema):
        raise ErrorProveedor("esquema", "la respuesta no cumple el esquema")
    return resultado, uso


# ---------------------------------------------------------------------------
# Función pública
# ---------------------------------------------------------------------------
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

    errores = []
    for ronda in range(config.REINTENTOS_LLM):
        disponibles = [m for m in modelos if m not in _modelos_sin_cuota]
        if not disponibles:
            break  # todos sin cuota (o sin clave): esperar no sirve, se avisa de inmediato
        for modelo in disponibles:
            inicio = time.time()
            try:
                resultado, uso = _llamar(modelo, instrucciones, contenido, esquema)
            except Exception as e:  # saturado (503), límite (429), sin clave, sin internet, JSON roto...
                codigo = _codigo_error(e)
                errores.append(f"{modelo}: {codigo}")
                _registrar({"tarea": tarea, "modelo": modelo, "desde_cache": False, "fallo": codigo,
                            "segundos": round(time.time() - inicio, 2)})
                if codigo in ("429", "sin_clave"):
                    # La cuota es por modelo: este no se vuelve a intentar en esta ejecución
                    # (reintentarlo solo gasta llamadas), pero los otros modelos sí
                    _modelos_sin_cuota.add(modelo)
                continue

            _registrar({"tarea": tarea, "modelo": modelo, "desde_cache": False,
                        "segundos": round(time.time() - inicio, 2), **uso})
            CARPETA_CACHE_LLM.mkdir(parents=True, exist_ok=True)
            ruta_cache.write_text(json.dumps({"modelo": modelo, "respuesta": resultado},
                                             ensure_ascii=False, indent=2), encoding="utf-8")
            return resultado, modelo

        if ronda < config.REINTENTOS_LLM - 1 and any(m not in _modelos_sin_cuota for m in modelos):
            # Si la ronda falló por el límite por minuto de Groq, hay que darle tiempo a que se libere
            por_minuto = any(e.endswith("429_minuto") for e in errores)
            time.sleep(config.ESPERA_LIMITE_POR_MINUTO if por_minuto else 2 ** (ronda + 1))

    if all(m in _modelos_sin_cuota for m in modelos):
        raise LLMNoDisponible("Sin cuota o sin clave en todos los modelos: " + ", ".join(modelos))
    raise LLMNoDisponible("Ningún modelo respondió: " + "; ".join(errores))
