"""Detección de noticias antiguas que vuelven a circular.

Una nota recirculada conserva su fecha original y se marca, para que nadie la
presente como un hecho nuevo.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import timedelta

from .comun import a_iso_utc, leer_iso

UMBRAL_DIAS = 7
NO_ALFANUMERICO = re.compile(r"[^a-z0-9 ]+")


def normalizar_titulo(titulo: str | None) -> str:
    texto = unicodedata.normalize("NFKD", (titulo or "").lower())
    texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
    return " ".join(NO_ALFANUMERICO.sub(" ", texto).split())


def _fechas(noticia: dict):
    return leer_iso(noticia.get("fecha_publicacion")), leer_iso(noticia.get("fecha_deteccion"))


def marcar_recirculadas(noticias: list[dict], umbral_dias: int = UMBRAL_DIAS) -> list[dict]:
    """Agrega `recirculada` y `fecha_original` a cada noticia (modifica y devuelve la lista).

    `fecha_original` es la fecha más antigua que se conoce del contenido: su
    publicación, o la primera vez que el mismo titular apareció en el paquete.
    Una noticia es recirculada si esa fecha precede a su detección por más del umbral.
    """
    umbral = timedelta(days=umbral_dias)
    primera_aparicion: dict[str, object] = {}
    for noticia in noticias:
        clave = normalizar_titulo(noticia.get("titulo"))
        conocidas = [fecha for fecha in _fechas(noticia) if fecha]
        if not clave or not conocidas:
            continue
        anterior = primera_aparicion.get(clave)
        candidata = min(conocidas)
        if anterior is None or candidata < anterior:
            primera_aparicion[clave] = candidata

    for noticia in noticias:
        publicacion, deteccion = _fechas(noticia)
        candidatas = [fecha for fecha in (publicacion, deteccion) if fecha]
        del_grupo = primera_aparicion.get(normalizar_titulo(noticia.get("titulo")))
        if del_grupo:
            candidatas.append(del_grupo)
        original = min(candidatas) if candidatas else None
        referencia = deteccion or publicacion
        noticia["recirculada"] = bool(original and referencia and referencia - original > umbral)
        noticia["fecha_original"] = a_iso_utc(original) if original else None
    return noticias


def fecha_para_mostrar(noticia: dict) -> str | None:
    """Fecha que debe ver el usuario: la original, nunca la de detección de una recirculada."""
    return noticia.get("fecha_original") or noticia.get("fecha_publicacion") or noticia.get("fecha_deteccion")
