"""Ubicación de los datos de los otros equipos y del estado propio de la interfaz."""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BACKEND = RAIZ / "backend"
WEB = Path(__file__).resolve().parent / "web"

ARTEFACTOS_REAL = BACKEND / "artefactos"
ARTEFACTOS_EJEMPLO = ARTEFACTOS_REAL / "ejemplo"
DATOS_REAL = RAIZ / "datos"
DATOS_EJEMPLO = BACKEND / "datos_ejemplo"

# Decisiones de revisión y registro de consultas: estado local, fuera de git.
ESTADO = Path(__file__).resolve().parent / "estado"

for _carpeta in (RAIZ, BACKEND):
    if str(_carpeta) not in sys.path:
        sys.path.insert(0, str(_carpeta))
