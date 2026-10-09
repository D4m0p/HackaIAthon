"""Acceso al núcleo de IA (backend/nucleo) sin exigir sus dependencias pesadas.

La interfaz reutiliza las reglas y los validadores del núcleo en lugar de copiarlos:
así hay una sola definición de pesos, niveles, límites y controles de seguridad.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import types

from . import rutas  # noqa: F401
from .texto import normalizar

from nucleo import config  # noqa: E402  (no importa nada más)


def _cargar_seguridad():
    try:
        return importlib.import_module("nucleo.seguridad")
    except ImportError:
        # nucleo.seguridad solo toma `normalizar` de nucleo.organizar, pero ese módulo
        # importa numpy y pandas. Sin ellos se le entrega un sustituto con esa función.
        sustituto = types.ModuleType("nucleo.organizar")
        sustituto.normalizar = normalizar
        sys.modules["nucleo.organizar"] = sustituto
        return importlib.import_module("nucleo.seguridad")


seguridad = _cargar_seguridad()


def _instalado(modulo: str) -> bool:
    try:
        return importlib.util.find_spec(modulo) is not None
    except (ImportError, ValueError):
        return False


def nucleo_completo() -> bool:
    """True si se puede generar una ficha nueva con el código del núcleo."""
    return all(_instalado(modulo) for modulo in ("numpy", "pandas", "dotenv"))


def llm_disponible() -> bool:
    if not (nucleo_completo() and _instalado("google.genai")):
        return False
    importlib.import_module("nucleo.llm")  # carga backend/.env
    return bool(os.environ.get("GEMINI_API_KEY"))


def generar_ficha(evento: dict) -> dict:
    """Ficha a pedido para un evento fuera del lote inicial. Usa Gemini si hay clave y
    conexión; si no, la plantilla del núcleo, que solo repite lo que dicen las fuentes."""
    if not nucleo_completo():
        raise RuntimeError(
            "Generar fichas nuevas requiere el entorno del núcleo de IA "
            "(backend/.venv con sus dependencias instaladas)."
        )
    fichas = importlib.import_module("nucleo.fichas")
    if llm_disponible():
        try:
            return fichas.generar_ficha(evento, usar_llm=True)
        except Exception:  # el proveedor falló de una forma que el núcleo no cubre
            pass
    return fichas.generar_ficha(evento, usar_llm=False)
