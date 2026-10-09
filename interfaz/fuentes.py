"""Carga de lo que producen los otros equipos: el paquete de datos (A) y los artefactos del núcleo (B).

La interfaz no recalcula nada de eso: lee `eventos.json` y `fichas.jsonl`, y arma
con ellos el índice de evidencia que permite resolver cada cita [ID:campo].
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import rutas
from .puente import config, seguridad

from ingesta import a_hora_panama, cargar_paquete  # noqa: E402
from ingesta.archivos import a_decimal, a_entero, leer_csv, leer_json  # noqa: E402

PAISES = {
    "PAN": "Panamá", "CRI": "Costa Rica", "COL": "Colombia",
    "DOM": "República Dominicana", "MEX": "México", "GTM": "Guatemala",
}


@dataclass
class Corpus:
    """Todo lo que la interfaz muestra o consulta, ya cargado en memoria."""

    modo: str                      # "real" o "ejemplo"
    carpeta_artefactos: Path
    carpeta_datos: Path
    eventos: list[dict] = field(default_factory=list)
    fichas: dict[str, dict] = field(default_factory=dict)      # id_evento -> ficha
    indicadores: list[dict] = field(default_factory=list)
    sismos: list[dict] = field(default_factory=list)
    excluidas_idioma: list[dict] = field(default_factory=list)
    fecha_corte: str | None = None
    manifest: dict | None = None
    reporte: dict | None = None
    incidencias: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    @property
    def carpeta_estado(self) -> Path:
        """Las decisiones sobre datos de ejemplo nunca se mezclan con las del reto."""
        return rutas.ESTADO / self.modo

    def evento(self, id_evento: str) -> dict | None:
        return next((evento for evento in self.eventos if evento["id_evento"] == id_evento), None)


# ---------------------------------------------------------------------------
# Datos oficiales, en una sola forma sea cual sea su origen
# ---------------------------------------------------------------------------
def _indicador(fila: dict) -> dict:
    codigo = fila.get("indicador_id")
    nombre = fila.get("indicador_nombre") or config.INDICADORES.get(codigo, {}).get("nombre") or codigo
    return {
        "pais_iso3": fila.get("pais_iso3"),
        "indicador_id": codigo,
        "nombre": nombre,
        "anio": a_entero(fila.get("anio")),
        "valor": a_decimal(fila.get("valor")),   # None si la fuente no publica el dato
        "unidad": fila.get("unidad"),
        "fuente_url": fila.get("fuente_url"),
        "licencia": fila.get("licencia"),
    }


def _fecha_sismo(valor) -> str | None:
    """USGS entrega milisegundos; el paquete congelado, texto ISO 8601."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        momento = datetime.fromtimestamp(valor / 1000, tz=timezone.utc)
    else:
        momento = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    return momento.astimezone(timezone.utc).isoformat()


def _sismo(propiedades: dict, coordenadas=None, id_feature=None) -> dict:
    lon, lat, prof = coordenadas or (
        propiedades.get("longitude"), propiedades.get("latitude"), propiedades.get("depth"))
    return {
        "id": propiedades.get("id") or id_feature,
        "magnitud": propiedades.get("magnitude", propiedades.get("mag")),
        "lugar": propiedades.get("place") or "",
        "fecha_utc": _fecha_sismo(propiedades.get("time")),
        "profundidad_km": prof,
        "estado": propiedades.get("status"),
        "fuente_url": propiedades.get("url"),
        "latitud": lat,
        "longitud": lon,
    }


def _datos_de_ejemplo(carpeta: Path) -> tuple[list[dict], list[dict], str | None]:
    indicadores = [_indicador(fila) for fila in leer_csv(carpeta / "indicadores_ejemplo.csv")]
    sismos = []
    for feature in leer_json(carpeta / "eventos_ejemplo.geojson").get("features", []):
        geometria = feature.get("geometry") or {}
        sismos.append(_sismo(feature["properties"], geometria.get("coordinates"), feature.get("id")))
    extracciones = [fila.get("fecha_extraccion") for fila in leer_csv(carpeta / "noticias_ejemplo.csv")]
    corte = max((fecha for fecha in extracciones if fecha), default=None)
    return indicadores, sismos, corte


# ---------------------------------------------------------------------------
# Artefactos del núcleo
# ---------------------------------------------------------------------------
def _leer_fichas(ruta: Path) -> dict[str, dict]:
    fichas = {}
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            if linea.strip():
                ficha = json.loads(linea)
                fichas[ficha["id_evento"]] = ficha
    return fichas


def hay_corrida_real() -> bool:
    return (rutas.ARTEFACTOS_REAL / "eventos.json").exists()


def cargar(modo: str = "auto", carpeta_artefactos: Path | str | None = None,
           carpeta_datos: Path | str | None = None) -> Corpus:
    """Carga el corpus sin abrir conexiones.

    modo "auto": la corrida real del núcleo si existe; si no, los datos de ejemplo.
    """
    avisos = []
    if carpeta_artefactos:
        modo = "real" if modo == "auto" else modo
    elif modo == "auto":
        modo = "real" if hay_corrida_real() else "ejemplo"
        if modo == "ejemplo":
            avisos.append(
                "Todavía no existe la corrida del núcleo sobre el paquete real "
                "(backend/artefactos/eventos.json). Se muestran los datos de ejemplo sintéticos.")

    ejemplo = modo == "ejemplo"
    artefactos = Path(carpeta_artefactos) if carpeta_artefactos else (
        rutas.ARTEFACTOS_EJEMPLO if ejemplo else rutas.ARTEFACTOS_REAL)
    datos = Path(carpeta_datos) if carpeta_datos else (rutas.DATOS_EJEMPLO if ejemplo else rutas.DATOS_REAL)

    corpus = Corpus(modo=modo, carpeta_artefactos=artefactos, carpeta_datos=datos, avisos=avisos)

    ruta_eventos = artefactos / "eventos.json"
    if not ruta_eventos.exists():
        raise FileNotFoundError(
            f"No se encontró {ruta_eventos}. Ejecute primero el núcleo de IA "
            "(cd backend && python -m nucleo.pipeline --paquete ../datos --offline) o use --ejemplo.")
    corpus.eventos = sorted(leer_json(ruta_eventos), key=lambda evento: evento["prioridad"]["posicion"])
    corpus.fichas = _leer_fichas(artefactos / "fichas.jsonl")
    ruta_excluidas = artefactos / "excluidas_idioma.json"
    corpus.excluidas_idioma = leer_json(ruta_excluidas) if ruta_excluidas.exists() else []

    if (datos / "manifest.json").exists() or (datos / "processed").exists():
        paquete = cargar_paquete(datos)
        corpus.indicadores = [_indicador(fila) for fila in paquete.indicadores]
        corpus.sismos = [_sismo(propiedades) for propiedades in paquete.eventos]
        corpus.fecha_corte = paquete.fecha_corte
        corpus.manifest, corpus.reporte, corpus.incidencias = paquete.manifest, paquete.reporte, paquete.incidencias
    else:
        corpus.indicadores, corpus.sismos, corpus.fecha_corte = _datos_de_ejemplo(datos)

    # Fichas pedidas desde la interfaz para eventos fuera del lote inicial
    for id_evento, ficha in _leer_fichas(corpus.carpeta_estado / "fichas_a_pedido.jsonl").items():
        if corpus.evento(id_evento):
            corpus.fichas.setdefault(id_evento, ficha)
    return corpus


def guardar_ficha_a_pedido(corpus: Corpus, ficha: dict) -> None:
    corpus.carpeta_estado.mkdir(parents=True, exist_ok=True)
    with open(corpus.carpeta_estado / "fichas_a_pedido.jsonl", "a", encoding="utf-8") as archivo:
        archivo.write(json.dumps(ficha, ensure_ascii=False) + "\n")
    corpus.fichas[ficha["id_evento"]] = ficha


# ---------------------------------------------------------------------------
# Evidencia citable
# ---------------------------------------------------------------------------
def evidencia_de_evento(evento: dict) -> tuple[dict, list[dict]]:
    """{id_evidencia: datos} con todo lo que una afirmación sobre el evento puede citar,
    con la misma forma que usa el núcleo al redactar. Los titulares que intentan dar
    instrucciones quedan fuera y se devuelven aparte, marcados como no confiables."""
    evidencia, no_confiable = {}, []
    for noticia in evento["noticias"]:
        patrones = seguridad.detectar_inyeccion(noticia["titulo"])
        if patrones:
            no_confiable.append({"id_noticia": noticia["id_noticia"], "medio": noticia["medio"],
                                 "titulo": noticia["titulo"], "patrones": patrones})
            continue
        evidencia[noticia["id_noticia"]] = {
            "tipo": "noticia",
            "titulo": noticia["titulo"],
            "medio": noticia["medio"],
            "fecha": noticia.get("fecha"),
            "tipo_fecha": noticia.get("tipo_fecha"),
            "antiguedad": noticia.get("antiguedad"),
            "url": noticia.get("url"),
            "alcance_texto": noticia.get("alcance_texto"),
        }
    for contexto in evento.get("contexto", []):
        evidencia[contexto["id_evidencia"]] = {
            clave: valor for clave, valor in contexto.items() if clave not in ("id_evidencia", "motivo_vinculo")}
    return evidencia, no_confiable


def evidencia_de_indicador(fila: dict) -> tuple[str, dict]:
    """Un dato del Banco Mundial como elemento citable, con el ID que usa el núcleo."""
    id_evidencia = f"WB:{fila['pais_iso3']}:{fila['indicador_id']}:{fila['anio']}"
    return id_evidencia, {
        "tipo": "indicador_banco_mundial",
        "indicador_id": fila["indicador_id"],
        "nombre": fila["nombre"],
        "pais": fila["pais_iso3"],
        "pais_nombre": PAISES.get(fila["pais_iso3"], fila["pais_iso3"]),
        "anio": fila["anio"],
        "valor": fila["valor"],
        "unidad": fila["unidad"],
        "fuente_url": fila["fuente_url"],
        "licencia": fila["licencia"],
        "advertencia": f"Dato anual {fila['anio']} del Banco Mundial. No es una medición actual.",
    }


def evidencia_de_sismo(sismo: dict) -> tuple[str, dict]:
    return f"USGS:{sismo['id']}", {
        "tipo": "sismo_usgs",
        "magnitud": sismo["magnitud"],
        "lugar": sismo["lugar"],
        "fecha_utc": sismo["fecha_utc"],
        "profundidad_km": sismo["profundidad_km"],
        "estado": sismo["estado"],
        "fuente_url": sismo["fuente_url"],
        "advertencia": "Dato sísmico oficial de USGS. Solo respalda hechos sísmicos "
                       "(magnitud, hora, ubicación), no daños ni pérdidas.",
    }


def hora_panama(fecha_iso: str | None) -> str | None:
    return a_hora_panama(fecha_iso)
