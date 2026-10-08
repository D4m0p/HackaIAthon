import json
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingesta import manifest as manifiesto  # noqa: E402
from ingesta.archivos import escribir_csv, escribir_json  # noqa: E402
from ingesta.carga import EVENTOS, INDICADORES, NOTICIAS  # noqa: E402
from ingesta.validacion import CAMPOS_INDICADORES, CAMPOS_NOTICIAS  # noqa: E402

EXTRACCION = "2026-10-08T18:00:00Z"


def noticia(numero: int, **cambios) -> dict:
    base = {
        "id_noticia": f"N-{numero:012d}",
        "titulo": f"Titular de prueba {numero}",
        "url": f"https://ejemplo.com/nota-{numero}",
        "medio": "ejemplo.com",
        "idioma": "es",
        "fecha_publicacion": "2026-10-05T12:00:00Z",
        "fecha_deteccion": "2026-10-05T13:00:00Z",
        "fecha_extraccion": EXTRACCION,
        "tema": "economia",
        "origen": "gdelt_doc",
        "alcance_texto": "titular_y_metadatos",
    }
    base.update(cambios)
    return base


def indicador(pais: str = "PAN", anio: int = 2023, valor=7.2, **cambios) -> dict:
    base = {
        "pais_iso3": pais,
        "indicador_id": "NY.GDP.MKTP.KD.ZG",
        "anio": anio,
        "valor": valor,
        "unidad": "% anual",
        "fuente_url": "https://data.worldbank.org/indicator/NY.GDP.MKTP.KD.ZG?locations=PA",
        "fecha_extraccion": EXTRACCION,
        "licencia": "CC BY 4.0",
    }
    base.update(cambios)
    return base


def sismo(identificador: str = "us0001", **cambios) -> dict:
    propiedades = {
        "id": identificador,
        "magnitude": 4.5,
        "time": "2024-03-01T10:00:00Z",
        "updated": "2024-03-02T10:00:00Z",
        "longitude": -82.5,
        "latitude": 8.1,
        "depth": 10.0,
        "place": "10 km S of David, Panama",
        "status": "reviewed",
        "url": f"https://earthquake.usgs.gov/earthquakes/eventpage/{identificador}",
    }
    propiedades.update(cambios)
    return {"type": "Feature", "id": identificador, "geometry": None, "properties": propiedades}


def escribir_paquete(directorio: Path, noticias, indicadores, sismos, con_manifest: bool = True) -> Path:
    """Arma en disco un paquete pequeño con la misma forma que el real."""
    escribir_csv(directorio / NOTICIAS, noticias, CAMPOS_NOTICIAS)
    escribir_csv(directorio / INDICADORES, indicadores, CAMPOS_INDICADORES)
    escribir_json(directorio / EVENTOS, {"type": "FeatureCollection", "features": sismos})
    if con_manifest:
        archivos = {
            NOTICIAS: {"registros": len(noticias), "licencia": "prueba"},
            INDICADORES: {"registros": len(indicadores), "licencia": "prueba"},
            EVENTOS: {"registros": len(sismos), "licencia": "prueba"},
        }
        manifiesto.construir(directorio, EXTRACCION, archivos, [], [], {})
    return directorio


@pytest.fixture
def paquete_valido(tmp_path):
    return escribir_paquete(
        tmp_path,
        [noticia(1), noticia(2), noticia(3)],
        [indicador(anio=2022), indicador(anio=2023), indicador(anio=2024, valor=None)],
        [sismo("us0001"), sismo("us0002")],
    )


@pytest.fixture
def sin_internet(monkeypatch):
    """Hace fallar cualquier intento de abrir una conexión."""
    def bloquear(*argumentos, **opciones):
        raise AssertionError("La carga intentó usar la red.")

    monkeypatch.setattr(socket, "socket", bloquear)
    monkeypatch.setattr(socket, "create_connection", bloquear)
    monkeypatch.setattr(socket, "getaddrinfo", bloquear)


def leer_texto(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def cargar_json(ruta: Path):
    return json.loads(leer_texto(ruta))
