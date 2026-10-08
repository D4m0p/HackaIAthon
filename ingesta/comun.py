"""Utilidades compartidas por los extractores y la carga."""

from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

AGENTE = "hackiathon-senales/1.0 (prototipo academico; datos publicos)"
ZONA_PANAMA = timezone(timedelta(hours=-5))
FORMATO_ISO = "%Y-%m-%dT%H:%M:%SZ"
PARAMETROS_RASTREO = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid")


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def a_iso_utc(momento: datetime) -> str:
    """Devuelve la fecha en ISO 8601, siempre en UTC y con sufijo Z."""
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(timezone.utc).strftime(FORMATO_ISO)


def leer_iso(texto: str | None) -> datetime | None:
    """Interpreta una fecha ISO 8601. Devuelve None si no es válida."""
    if not texto or not isinstance(texto, str):
        return None
    try:
        momento = datetime.fromisoformat(texto.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(timezone.utc)


def a_hora_panama(texto_iso: str | None) -> str | None:
    """Convierte una fecha UTC del paquete a hora de Panamá para la interfaz."""
    momento = leer_iso(texto_iso)
    if momento is None:
        return None
    return momento.astimezone(ZONA_PANAMA).strftime("%Y-%m-%d %H:%M") + " (hora de Panamá)"


def sha256_bytes(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def sha256_archivo(ruta: Path) -> str:
    resumen = hashlib.sha256()
    with open(ruta, "rb") as archivo:
        for bloque in iter(lambda: archivo.read(65536), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


def normalizar_url(url: str | None) -> str | None:
    """Unifica una URL para deduplicar: sin fragmento ni parámetros de rastreo."""
    if not url or not isinstance(url, str):
        return None
    partes = urlsplit(url.strip())
    if not partes.scheme or not partes.netloc:
        return url.strip()
    consulta = [
        (clave, valor)
        for clave, valor in parse_qsl(partes.query, keep_blank_values=True)
        if not clave.lower().startswith(PARAMETROS_RASTREO)
    ]
    ruta = partes.path.rstrip("/") or "/"
    return urlunsplit(
        (partes.scheme.lower(), partes.netloc.lower(), ruta, urlencode(consulta), "")
    )


def id_estable(prefijo: str, texto: str) -> str:
    """ID que no cambia entre extracciones: depende solo del texto dado."""
    return f"{prefijo}-{hashlib.sha1(texto.encode('utf-8')).hexdigest()[:12]}"


def descargar(url: str, intentos: int = 4, espera: float = 6.0, tiempo_limite: float = 60.0) -> bytes:
    """Descarga una URL pública con reintentos. Solo se usa al construir el snapshot."""
    ultimo_error: Exception | None = None
    for intento in range(intentos):
        try:
            peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})
            with urllib.request.urlopen(peticion, timeout=tiempo_limite) as respuesta:
                return respuesta.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            ultimo_error = error
            time.sleep(espera * (intento + 1))
    raise RuntimeError(f"No se pudo descargar {url}: {ultimo_error}")
