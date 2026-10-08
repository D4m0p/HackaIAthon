"""Validación de los tres archivos del paquete.

Ninguna fila defectuosa detiene la carga: se separa con su motivo y el resto
continúa. Los nulos permitidos se conservan como None.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from .comun import leer_iso

CAMPOS_NOTICIAS = [
    "id_noticia", "titulo", "url", "medio", "idioma", "fecha_publicacion",
    "fecha_deteccion", "fecha_extraccion", "tema", "origen", "alcance_texto",
    "palabras_clave", "seccion", "pais_medio", "recirculada", "fecha_original",
]
CAMPOS_INDICADORES = [
    "pais_iso3", "indicador_id", "anio", "valor", "unidad", "fuente_url",
    "fecha_extraccion", "licencia", "indicador_nombre", "actualizacion_fuente",
]
CAMPOS_EVENTOS = [
    "id", "magnitude", "time", "updated", "longitude", "latitude", "depth",
    "place", "status", "url",
]

OBLIGATORIOS_NOTICIAS = [
    "id_noticia", "titulo", "url", "medio", "fecha_extraccion", "origen", "alcance_texto",
]
OBLIGATORIOS_INDICADORES = [
    "pais_iso3", "indicador_id", "anio", "unidad", "fuente_url", "fecha_extraccion", "licencia",
]
OBLIGATORIOS_EVENTOS = ["id", "magnitude", "time", "longitude", "latitude", "url"]

# Límite inferior de las normas de extracción del reto.
INICIO_INTERVALO = datetime(2024, 1, 1, tzinfo=timezone.utc)
MARGEN_FUTURO = timedelta(days=1)


@dataclass
class Resultado:
    """Filas aceptadas y filas apartadas, cada una con sus motivos."""

    validas: list[dict] = field(default_factory=list)
    rechazadas: list[dict] = field(default_factory=list)

    def rechazar(self, numero: int, registro: dict, motivos: list[str], clave: str) -> None:
        self.rechazadas.append(
            {"fila": numero, "id": registro.get(clave), "motivos": motivos, "registro": registro}
        )


def es_vacio(valor) -> bool:
    if valor is None:
        return True
    if isinstance(valor, float) and math.isnan(valor):
        return True
    return isinstance(valor, str) and not valor.strip()


def _fila_vacia(registro: dict) -> bool:
    return all(es_vacio(valor) for valor in registro.values())


def _faltantes(registro: dict, obligatorios: list[str]) -> list[str]:
    return [f"falta {campo}" for campo in obligatorios if es_vacio(registro.get(campo))]


def url_valida(url) -> bool:
    if es_vacio(url) or not isinstance(url, str):
        return False
    partes = urlsplit(url.strip())
    return partes.scheme in ("http", "https") and "." in partes.netloc and " " not in url.strip()


def _fecha(registro: dict, campo: str, motivos: list[str]) -> datetime | None:
    """Lee una fecha opcional. Si está presente pero no es ISO 8601, la reporta."""
    valor = registro.get(campo)
    if es_vacio(valor):
        return None
    momento = leer_iso(valor)
    if momento is None:
        motivos.append(f"{campo} inválida: {valor!r}")
    return momento


def _numero(valor) -> float | None:
    if isinstance(valor, bool) or es_vacio(valor):
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(numero) or math.isinf(numero) else numero


def validar_noticias(filas: list[dict], ahora: datetime | None = None) -> Resultado:
    resultado = Resultado()
    vistos: set[str] = set()
    ahora = ahora or datetime.now(timezone.utc)
    for numero, registro in enumerate(filas, start=1):
        if _fila_vacia(registro):
            resultado.rechazar(numero, registro, ["fila vacía"], "id_noticia")
            continue
        motivos = _faltantes(registro, OBLIGATORIOS_NOTICIAS)
        if not es_vacio(registro.get("url")) and not url_valida(registro.get("url")):
            motivos.append(f"url inválida: {registro.get('url')!r}")

        publicacion = _fecha(registro, "fecha_publicacion", motivos)
        deteccion = _fecha(registro, "fecha_deteccion", motivos)
        extraccion = _fecha(registro, "fecha_extraccion", motivos)
        if es_vacio(registro.get("fecha_publicacion")) and es_vacio(registro.get("fecha_deteccion")):
            motivos.append("sin fecha de publicación ni de detección")

        # El intervalo se mide con la detección: una nota antigua que vuelve a
        # circular se conserva y se marca, no se descarta.
        referencia = deteccion or publicacion
        limite = (extraccion or ahora) + MARGEN_FUTURO
        if referencia and referencia < INICIO_INTERVALO:
            motivos.append("fuera del intervalo: anterior a 2024-01-01")
        if referencia and referencia > limite:
            motivos.append("fuera del intervalo: fecha posterior a la extracción")
        if publicacion and publicacion > limite:
            motivos.append("fecha_publicacion posterior a la extracción")

        identificador = registro.get("id_noticia")
        if not es_vacio(identificador):
            if identificador in vistos:
                motivos.append(f"id_noticia duplicado: {identificador}")
            elif not motivos:
                vistos.add(identificador)

        if motivos:
            resultado.rechazar(numero, registro, motivos, "id_noticia")
        else:
            resultado.validas.append(registro)
    return resultado


def validar_indicadores(filas: list[dict], ahora: datetime | None = None) -> Resultado:
    resultado = Resultado()
    vistos: set[tuple] = set()
    anio_maximo = (ahora or datetime.now(timezone.utc)).year
    for numero, registro in enumerate(filas, start=1):
        if _fila_vacia(registro):
            resultado.rechazar(numero, registro, ["fila vacía"], "indicador_id")
            continue
        motivos = _faltantes(registro, OBLIGATORIOS_INDICADORES)
        pais = registro.get("pais_iso3")
        if not es_vacio(pais) and not (isinstance(pais, str) and len(pais) == 3 and pais.isalpha() and pais.isupper()):
            motivos.append(f"pais_iso3 inválido: {pais!r}")

        anio = registro.get("anio")
        if not es_vacio(anio):
            if isinstance(anio, bool) or not isinstance(anio, int):
                motivos.append(f"anio inválido: {anio!r}")
            elif not 1960 <= anio <= anio_maximo:
                motivos.append(f"anio fuera de rango: {anio}")

        # El valor puede faltar (None); lo que no puede es ser un texto no numérico.
        valor = registro.get("valor")
        if not es_vacio(valor) and _numero(valor) is None:
            motivos.append(f"valor no numérico: {valor!r}")
        if not es_vacio(registro.get("fuente_url")) and not url_valida(registro.get("fuente_url")):
            motivos.append(f"fuente_url inválida: {registro.get('fuente_url')!r}")
        _fecha(registro, "fecha_extraccion", motivos)

        clave = (pais, registro.get("indicador_id"), anio)
        if not motivos:
            if clave in vistos:
                motivos.append(f"combinación duplicada: {clave}")
            else:
                vistos.add(clave)

        if motivos:
            resultado.rechazar(numero, registro, motivos, "indicador_id")
        else:
            resultado.validas.append(registro)
    return resultado


def validar_eventos(eventos: list[dict]) -> Resultado:
    """Valida las propiedades de cada sismo (lista de Feature de GeoJSON)."""
    resultado = Resultado()
    vistos: set[str] = set()
    for numero, evento in enumerate(eventos, start=1):
        propiedades = (evento or {}).get("properties") or {}
        if _fila_vacia(propiedades):
            resultado.rechazar(numero, propiedades, ["fila vacía"], "id")
            continue
        motivos = _faltantes(propiedades, OBLIGATORIOS_EVENTOS)
        for campo, minimo, maximo in (
            ("magnitude", -2, 10), ("latitude", -90, 90), ("longitude", -180, 180),
        ):
            valor = propiedades.get(campo)
            if es_vacio(valor):
                continue
            numero_valor = _numero(valor)
            if numero_valor is None:
                motivos.append(f"{campo} no numérico: {valor!r}")
            elif not minimo <= numero_valor <= maximo:
                motivos.append(f"{campo} fuera de rango: {valor}")
        _fecha(propiedades, "time", motivos)
        _fecha(propiedades, "updated", motivos)
        if not es_vacio(propiedades.get("url")) and not url_valida(propiedades.get("url")):
            motivos.append(f"url inválida: {propiedades.get('url')!r}")

        identificador = propiedades.get("id")
        if not es_vacio(identificador):
            if identificador in vistos:
                motivos.append(f"id duplicado: {identificador}")
            elif not motivos:
                vistos.add(identificador)

        if motivos:
            resultado.rechazar(numero, propiedades, motivos, "id")
        else:
            resultado.validas.append(evento)
    return resultado
