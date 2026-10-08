"""Etapa 1 · Cargar: lee el paquete congelado sin usar internet.

Uso:

    from ingesta import cargar_paquete
    paquete = cargar_paquete()
    paquete.noticias, paquete.indicadores, paquete.eventos, paquete.reporte
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import manifest as manifiesto
from .archivos import a_booleano, a_decimal, a_entero, leer_csv, leer_json
from .calidad import construir_reporte
from .validacion import Resultado, validar_eventos, validar_indicadores, validar_noticias

DIRECTORIO = Path(__file__).resolve().parent.parent / "datos"
NOTICIAS = "processed/noticias.csv"
INDICADORES = "processed/indicadores.csv"
EVENTOS = "processed/eventos.geojson"


@dataclass
class Paquete:
    """Datos validados más todo lo necesario para explicar su calidad."""

    noticias: list[dict] = field(default_factory=list)
    indicadores: list[dict] = field(default_factory=list)
    eventos: list[dict] = field(default_factory=list)
    rechazados: dict = field(default_factory=dict)
    reporte: dict = field(default_factory=dict)
    manifest: dict | None = None
    incidencias: list[str] = field(default_factory=list)

    @property
    def integro(self) -> bool:
        """True si todos los archivos existen y coinciden con el manifest."""
        return not self.incidencias

    @property
    def fecha_corte(self) -> str | None:
        return (self.manifest or {}).get("fecha_corte_UTC")


def _leer(ruta: Path, lector, incidencias: list[str]) -> list:
    """Lee un archivo; si falta o está dañado lo anota y devuelve una lista vacía."""
    if not ruta.exists():
        return []  # la ausencia ya la reporta la verificación del manifest
    try:
        return lector(ruta)
    except (OSError, ValueError, KeyError, TypeError) as error:
        incidencias.append(f"No se pudo leer {ruta.name}: {error}")
        return []


def _leer_noticias(ruta: Path) -> list[dict]:
    filas = leer_csv(ruta)
    for fila in filas:
        fila["recirculada"] = a_booleano(fila.get("recirculada"))
    return filas


def _leer_indicadores(ruta: Path) -> list[dict]:
    filas = leer_csv(ruta)
    for fila in filas:
        fila["anio"] = a_entero(fila.get("anio"))
        fila["valor"] = a_decimal(fila.get("valor"))
    return filas


def _leer_eventos(ruta: Path) -> list[dict]:
    return leer_json(ruta).get("features", [])


def cargar_paquete(directorio: Path | str | None = None) -> Paquete:
    """Carga, verifica y valida el paquete congelado.

    Nunca lanza una excepción por datos defectuosos ni abre conexiones:
    - una fila inválida se aparta en `rechazados` con su motivo;
    - un archivo ausente, ilegible o alterado se anota en `incidencias` y los
      demás se cargan igual.
    """
    directorio = Path(directorio) if directorio else DIRECTORIO
    manifest = _leer_manifest(directorio)
    incidencias = manifiesto.verificar(directorio, manifest)
    for relativa in (NOTICIAS, INDICADORES, EVENTOS):
        aviso = f"Falta el archivo {relativa}."
        if not (directorio / relativa).exists() and aviso not in incidencias:
            incidencias.append(aviso)

    noticias = validar_noticias(_leer(directorio / NOTICIAS, _leer_noticias, incidencias))
    indicadores = validar_indicadores(_leer(directorio / INDICADORES, _leer_indicadores, incidencias))
    eventos = validar_eventos(_leer(directorio / EVENTOS, _leer_eventos, incidencias))

    return Paquete(
        noticias=noticias.validas,
        indicadores=indicadores.validas,
        eventos=[evento["properties"] for evento in eventos.validas],
        rechazados=_rechazados(noticias, indicadores, eventos),
        reporte=construir_reporte(noticias, indicadores, eventos, incidencias=incidencias),
        manifest=manifest,
        incidencias=incidencias,
    )


def _leer_manifest(directorio: Path) -> dict | None:
    try:
        return manifiesto.leer(directorio)
    except (OSError, ValueError):
        return None


def _rechazados(noticias: Resultado, indicadores: Resultado, eventos: Resultado) -> dict:
    return {
        "noticias": noticias.rechazadas,
        "indicadores": indicadores.rechazadas,
        "eventos": eventos.rechazadas,
    }
