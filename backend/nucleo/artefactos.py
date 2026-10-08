"""
Artefactos versionados: resultados del LLM y de los embeddings guardados en
backend/artefactos/ (esta carpeta SÍ se sube a git).

Para qué sirve:
- La demo funciona sin internet con exactamente los mismos resultados (T10).
- El ranking es idéntico con y sin conexión: los temas salen del archivo.
- Cada resultado guarda qué modelo lo generó y un hash de su entrada, así se
  sabe cuándo quedó desactualizado.

Archivos:
- temas.json:        {id_noticia: {hash_titulo, tema, motivo, modelo, fecha_utc}}
- redacciones.json:  {id_evento: {hash_evidencia, redaccion, modelo, fecha_utc}}
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from nucleo import config

CARPETA = Path(__file__).parent.parent / config.CARPETA_ARTEFACTOS


def huella(*partes):
    """Hash SHA-256 corto de cualquier combinación de datos (para detectar cambios)."""
    texto = json.dumps(partes, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def ahora_utc():
    return datetime.now(timezone.utc).isoformat()


def cargar(nombre):
    ruta = CARPETA / nombre
    if not ruta.exists():
        return {}
    return json.loads(ruta.read_text(encoding="utf-8"))


def guardar(nombre, datos):
    CARPETA.mkdir(exist_ok=True)
    (CARPETA / nombre).write_text(json.dumps(datos, ensure_ascii=False, indent=1, sort_keys=True),
                                  encoding="utf-8")
