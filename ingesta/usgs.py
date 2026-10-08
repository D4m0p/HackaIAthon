"""Extractor de sismos del catálogo de USGS (servicio FDSN)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlencode

from .comun import a_iso_utc

URL_API = "https://earthquake.usgs.gov/fdsnws/event/1/query"
# Caja regional del reto. No equivale al territorio de Panamá.
PARAMETROS = {
    "format": "geojson",
    "starttime": "2024-01-01",
    "endtime": "2024-12-31T23:59:59",
    "minlatitude": 5,
    "maxlatitude": 12,
    "minlongitude": -86,
    "maxlongitude": -76,
    "minmagnitude": 3,
    "orderby": "time-asc",
}
ARCHIVO = "usgs/sismos_2024.geojson"
ADVERTENCIA = (
    "Caja regional lat 5 a 12, lon -86 a -76: incluye zonas fuera de Panamá. "
    "Solo sustenta hechos sísmicos; no es evidencia de inundaciones ni de pérdidas económicas."
)


def url_consulta() -> str:
    return f"{URL_API}?{urlencode(PARAMETROS)}"


def _fecha_ms(milisegundos) -> str | None:
    if milisegundos is None:
        return None
    try:
        return a_iso_utc(datetime.fromtimestamp(milisegundos / 1000, tz=timezone.utc))
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def interpretar(contenido: bytes, fecha_extraccion: str) -> dict:
    """Devuelve un FeatureCollection con las propiedades del contrato."""
    original = json.loads(contenido.decode("utf-8"))
    eventos = []
    for evento in original.get("features", []):
        propiedades = evento.get("properties") or {}
        coordenadas = ((evento.get("geometry") or {}).get("coordinates") or [None, None, None])
        coordenadas = list(coordenadas) + [None] * (3 - len(coordenadas))
        eventos.append(
            {
                "type": "Feature",
                "id": evento.get("id"),
                "geometry": evento.get("geometry"),
                "properties": {
                    "id": evento.get("id"),
                    "magnitude": propiedades.get("mag"),
                    "time": _fecha_ms(propiedades.get("time")),
                    "updated": _fecha_ms(propiedades.get("updated")),
                    "longitude": coordenadas[0],
                    "latitude": coordenadas[1],
                    "depth": coordenadas[2],
                    "place": propiedades.get("place"),
                    "status": propiedades.get("status"),
                    "url": propiedades.get("url"),
                    "magnitude_type": propiedades.get("magType"),
                    "fecha_extraccion": fecha_extraccion,
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "metadata": {
            "fuente": "USGS Earthquake Catalog",
            "consulta": url_consulta(),
            "fecha_extraccion": fecha_extraccion,
            "cantidad": len(eventos),
            "unidades": {"magnitude": "magnitud", "depth": "km", "time": "UTC"},
            "advertencia": ADVERTENCIA,
        },
        "features": eventos,
    }
