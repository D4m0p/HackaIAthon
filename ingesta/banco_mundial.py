"""Extractor de indicadores del Banco Mundial (Indicators API v2)."""

from __future__ import annotations

import json

URL_API = "https://api.worldbank.org/v2"
LICENCIA = "CC BY 4.0"
PAISES = {"PAN": "PA", "CRI": "CR", "COL": "CO", "DOM": "DO", "MEX": "MX", "GTM": "GT"}
ANIO_INICIAL, ANIO_FINAL = 2010, 2024

# La API no informa la unidad en un campo propio: se documenta aquí.
INDICADORES = {
    "NY.GDP.MKTP.KD.ZG": ("Crecimiento del PIB", "% anual"),
    "FP.CPI.TOTL.ZG": ("Inflación, precios al consumidor", "% anual"),
    "SL.UEM.TOTL.ZS": ("Desempleo total (estimación modelada OIT)", "% de la población activa"),
    "SP.POP.TOTL": ("Población total", "personas"),
    "IT.NET.USER.ZS": ("Personas que usan internet", "% de la población"),
    "NE.EXP.GNFS.ZS": ("Exportaciones de bienes y servicios", "% del PIB"),
}


def planificar() -> list[dict]:
    """Una consulta por indicador, con los seis países a la vez."""
    paises = ";".join(PAISES)
    return [
        {
            "indicador_id": indicador,
            "url": (
                f"{URL_API}/country/{paises}/indicator/{indicador}"
                f"?format=json&date={ANIO_INICIAL}:{ANIO_FINAL}&per_page=1000"
            ),
            "archivo": f"banco_mundial/{indicador}.json",
        }
        for indicador in INDICADORES
    ]


def url_fuente(indicador: str, pais_iso3: str) -> str:
    return f"https://data.worldbank.org/indicator/{indicador}?locations={PAISES[pais_iso3]}"


def interpretar(contenido: bytes, indicador: str, fecha_extraccion: str) -> list[dict]:
    """Devuelve la cuadrícula completa país × año de un indicador.

    Las combinaciones que la API no entrega, o entrega sin valor, se conservan
    con valor None. Nunca se rellenan con cero.
    """
    respuesta = json.loads(contenido.decode("utf-8-sig"))
    observaciones = respuesta[1] if isinstance(respuesta, list) and len(respuesta) > 1 else []
    actualizado = respuesta[0].get("lastupdated") if isinstance(respuesta, list) and respuesta else None
    valores = {}
    for observacion in observaciones or []:
        pais = observacion.get("countryiso3code")
        try:
            anio = int(observacion.get("date"))
        except (TypeError, ValueError):
            continue
        valores[(pais, anio)] = observacion.get("value")

    nombre, unidad = INDICADORES[indicador]
    filas = []
    for pais in PAISES:
        for anio in range(ANIO_INICIAL, ANIO_FINAL + 1):
            filas.append(
                {
                    "pais_iso3": pais,
                    "indicador_id": indicador,
                    "anio": anio,
                    "valor": valores.get((pais, anio)),
                    "unidad": unidad,
                    "fuente_url": url_fuente(indicador, pais),
                    "fecha_extraccion": fecha_extraccion,
                    "licencia": LICENCIA,
                    "indicador_nombre": nombre,
                    "actualizacion_fuente": actualizado,
                }
            )
    return filas
