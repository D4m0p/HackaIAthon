"""Extractor de GDELT DOC 2.0 (modo ArtList). Solo entrega titulares y metadatos."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from urllib.parse import urlencode

from .comun import a_iso_utc, id_estable, normalizar_url

URL_API = "https://api.gdeltproject.org/api/v2/doc/doc"
ORIGEN = "gdelt_doc"
ALCANCE = "titular_y_metadatos"
MAXIMO_POR_CONSULTA = 250  # límite de la API

# Una consulta por tema del reto, con términos en español e inglés porque GDELT
# indexa los artículos traducidos. "tvn" refuerza la cobertura del patrocinador
# más allá de lo que conserva el RSS.
CONSULTAS = {
    "general": "panama sourcecountry:PM",
    "economia": "panama (economy OR inflation OR employment OR investment OR economía OR inflación OR empleo)",
    "logistica": "panama (canal OR logistics OR shipping OR port OR logística OR puerto)",
    "turismo": "panama (tourism OR tourists OR hotel OR turismo OR turistas)",
    "eventos_naturales": "panama (earthquake OR flood OR flooding OR rains OR sismo OR inundaciones OR lluvias)",
    "tvn": "domain:tvn-2.com",
}

IDIOMAS = {
    "spanish": "es", "english": "en", "portuguese": "pt", "french": "fr", "german": "de",
    "italian": "it", "greek": "el", "chinese": "zh", "arabic": "ar", "thai": "th",
    "russian": "ru", "japanese": "ja", "korean": "ko", "turkish": "tr", "dutch": "nl",
}
MEDIOS = {"tvn-2.com": "TVN"}
FECHA_EN_URL = re.compile(r"(?<!\d)(20\d{2})[/-](\d{1,2})[/-](\d{1,2})(?!\d)")
ESPACIO_ANTES_DE_SIGNO = re.compile(r"\s+([,.;:!?%)\]])")
ESPACIO_DESPUES_DE_APERTURA = re.compile(r"([(\[¿¡])\s+")


def planificar(fecha_corte: datetime, dias: int = 30, dias_por_ventana: int = 10,
               maximo: int = MAXIMO_POR_CONSULTA) -> list[dict]:
    """Divide el período en ventanas para no chocar con el tope de 250 artículos."""
    plan = []
    inicio_total = fecha_corte - timedelta(days=dias)
    for tema, consulta in CONSULTAS.items():
        inicio = inicio_total
        while inicio < fecha_corte:
            fin = min(inicio + timedelta(days=dias_por_ventana), fecha_corte)
            parametros = {
                "query": consulta,
                "mode": "ArtList",
                "format": "json",
                "sort": "DateDesc",
                "maxrecords": maximo,
                "startdatetime": inicio.strftime("%Y%m%d%H%M%S"),
                "enddatetime": fin.strftime("%Y%m%d%H%M%S"),
            }
            plan.append(
                {
                    "tema": tema,
                    "consulta": consulta,
                    "inicio": a_iso_utc(inicio),
                    "fin": a_iso_utc(fin),
                    "url": f"{URL_API}?{urlencode(parametros)}",
                    "archivo": f"gdelt/{tema}_{inicio:%Y%m%d}_{fin:%Y%m%d}.json",
                }
            )
            inicio = fin
    return plan


def _fecha_gdelt(texto: str | None) -> str | None:
    try:
        return a_iso_utc(datetime.strptime(texto, "%Y%m%dT%H%M%SZ"))
    except (TypeError, ValueError):
        return None


def fecha_en_url(url: str | None) -> str | None:
    """Fecha de publicación cuando el medio la incluye en la URL; si no, None.

    GDELT solo informa cuándo detectó el artículo ("seendate"), no cuándo se
    publicó. No se inventa una fecha de publicación.
    """
    hallazgo = FECHA_EN_URL.search(url or "")
    if not hallazgo:
        return None
    try:
        return a_iso_utc(datetime(*map(int, hallazgo.groups())))
    except ValueError:
        return None


def limpiar_titulo(titulo: str | None) -> str | None:
    """Quita los espacios que GDELT inserta alrededor de la puntuación."""
    if not titulo:
        return None
    texto = ESPACIO_ANTES_DE_SIGNO.sub(r"\1", titulo)
    texto = ESPACIO_DESPUES_DE_APERTURA.sub(r"\1", texto)
    return " ".join(texto.split()) or None


def interpretar(contenido: bytes, tema: str, fecha_extraccion: str) -> list[dict]:
    """Convierte una respuesta ArtList en registros con el contrato de noticias.csv."""
    texto = contenido.decode("utf-8", errors="replace").strip()
    if not texto:
        return []
    articulos = json.loads(texto, strict=False).get("articles", [])
    registros = []
    for articulo in articulos:
        url = normalizar_url(articulo.get("url"))
        dominio = (articulo.get("domain") or "").lower()
        idioma = (articulo.get("language") or "").strip().lower()
        registros.append(
            {
                "id_noticia": id_estable("N", url) if url else None,
                "titulo": limpiar_titulo(articulo.get("title")),
                "url": url,
                "medio": MEDIOS.get(dominio, dominio or None),
                "idioma": IDIOMAS.get(idioma, idioma or None),
                "fecha_publicacion": fecha_en_url(url),
                "fecha_deteccion": _fecha_gdelt(articulo.get("seendate")),
                "fecha_extraccion": fecha_extraccion,
                "tema": tema,
                "origen": ORIGEN,
                "alcance_texto": ALCANCE,
                "palabras_clave": None,
                "seccion": None,
                "pais_medio": articulo.get("sourcecountry") or None,
            }
        )
    return registros
