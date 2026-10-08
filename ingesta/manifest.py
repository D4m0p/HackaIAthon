"""Manifest del paquete: qué archivos lo componen y con qué huella."""

from __future__ import annotations

from pathlib import Path

from .archivos import escribir_json, leer_json
from .comun import sha256_archivo

NOMBRE = "manifest.json"
VERSION = "Panamá · Señales y Evidencias v1"


def construir(directorio: Path, fecha_corte: str, archivos: dict, consultas: list[dict],
              transformaciones: list[str], excluidos: dict) -> dict:
    """`archivos` asocia cada ruta relativa con su cantidad de registros y su licencia."""
    detalle = {}
    for relativa, datos in archivos.items():
        ruta = directorio / relativa
        detalle[relativa] = {
            "registros": datos["registros"],
            "licencia_condiciones": datos["licencia"],
            "bytes": ruta.stat().st_size,
            "sha256": sha256_archivo(ruta),
        }
    manifest = {
        "version": VERSION,
        "fecha_corte_UTC": fecha_corte,
        "codificacion": "UTF-8",
        "formato_fechas": "ISO 8601 en UTC",
        "archivos": detalle,
        "consultas": consultas,
        "transformaciones": transformaciones,
        "registros_excluidos": excluidos,
    }
    escribir_json(directorio / NOMBRE, manifest)
    return manifest


def leer(directorio: Path) -> dict | None:
    ruta = directorio / NOMBRE
    return leer_json(ruta) if ruta.exists() else None


def verificar(directorio: Path, manifest: dict | None) -> list[str]:
    """Compara cada archivo con su huella. Devuelve la lista de problemas (vacía si todo coincide)."""
    if manifest is None:
        return [f"No existe {NOMBRE}: no se puede comprobar la integridad del paquete."]
    problemas = []
    for relativa, datos in manifest.get("archivos", {}).items():
        ruta = directorio / relativa
        if not ruta.exists():
            problemas.append(f"Falta el archivo {relativa}.")
        elif sha256_archivo(ruta) != datos.get("sha256"):
            problemas.append(f"El archivo {relativa} no coincide con el SHA-256 del manifest.")
    return problemas
