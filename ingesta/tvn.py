"""Extractor del RSS público de TVN. Solo conserva titular y metadatos."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

from .comun import a_iso_utc, id_estable, normalizar_url

URL_RSS = "https://www.tvn-2.com/rss/"
MEDIO = "TVN"
ORIGEN = "tvn_rss"
ALCANCE = "titular_y_metadatos"
ESPACIO_MEDIA = "{http://search.yahoo.com/mrss/}"


def _fecha_rss(texto: str | None) -> str | None:
    if not texto:
        return None
    try:
        return a_iso_utc(parsedate_to_datetime(texto.strip()))
    except (TypeError, ValueError):
        return None


def _seccion(url: str) -> str | None:
    segmentos = [parte for parte in urlsplit(url).path.split("/") if parte]
    return segmentos[0] if len(segmentos) > 1 else None


def interpretar(contenido: bytes, fecha_extraccion: str) -> list[dict]:
    """Convierte el XML del RSS en registros con el contrato de noticias.csv.

    La descripción y las imágenes del feed no se copian: el patrocinio no da
    derechos de republicación.
    """
    raiz = ET.fromstring(contenido)
    idioma = (raiz.findtext("channel/language") or "es").split("-")[0].lower()
    registros = []
    for elemento in raiz.iter("item"):
        url = normalizar_url(elemento.findtext("link") or elemento.findtext("guid"))
        titulo = (elemento.findtext("title") or "").strip()
        palabras = (elemento.findtext(f"{ESPACIO_MEDIA}keywords") or "").strip()
        registros.append(
            {
                "id_noticia": id_estable("N", url) if url else None,
                "titulo": titulo or None,
                "url": url,
                "medio": MEDIO,
                "idioma": idioma,
                "fecha_publicacion": _fecha_rss(elemento.findtext("pubDate")),
                "fecha_deteccion": fecha_extraccion,
                "fecha_extraccion": fecha_extraccion,
                "tema": None,
                "origen": ORIGEN,
                "alcance_texto": ALCANCE,
                "palabras_clave": palabras or None,
                "seccion": _seccion(url) if url else None,
            }
        )
    return registros
