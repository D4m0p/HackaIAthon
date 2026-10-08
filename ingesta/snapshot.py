"""Construye el paquete congelado a partir de las fuentes públicas.

    python -m ingesta.snapshot                 # descarga y procesa
    python -m ingesta.snapshot --reanudar      # repite solo las descargas que fallaron
    python -m ingesta.snapshot --sin-descarga  # reprocesa lo que ya está en datos/raw

Es el único punto del proyecto que usa internet. La demo lee el resultado.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from . import banco_mundial, gdelt, tvn, usgs
from . import manifest as manifiesto
from .archivos import escribir_csv, escribir_json, leer_json
from .calidad import a_markdown, construir_reporte
from .carga import DIRECTORIO, EVENTOS, INDICADORES, NOTICIAS
from .comun import a_iso_utc, ahora_utc, descargar, leer_iso, sha256_bytes
from .recirculacion import UMBRAL_DIAS, marcar_recirculadas
from .validacion import (
    CAMPOS_INDICADORES, CAMPOS_NOTICIAS, validar_eventos, validar_indicadores, validar_noticias,
)

REGISTRO = "raw/extraccion.json"
EXCLUSIONES = "exclusiones.json"
ARCHIVO_TVN = "tvn_rss.xml"
PAUSA_GDELT = 20.0  # GDELT pide espaciar las consultas

CONDICIONES = {
    "tvn": (
        "Feed RSS público de TVN, sin licencia abierta declarada. Se usan solo titular, URL, "
        "fecha y palabras clave. No se redistribuyen descripciones, cuerpos, imágenes ni videos."
    ),
    "gdelt": (
        "GDELT DOC 2.0, de uso abierto citando a The GDELT Project. No transfiere derechos sobre "
        "los artículos enlazados: se conservan solo titular y metadatos."
    ),
    "banco_mundial": "Banco Mundial, World Development Indicators. CC BY 4.0, con atribución.",
    "usgs": "USGS Earthquake Catalog. Dominio público de EE. UU.; se cita a USGS como fuente.",
}
TRANSFORMACIONES = [
    "Fechas convertidas a ISO 8601 en UTC.",
    "URL normalizadas: sin fragmento, sin parámetros de rastreo y sin barra final.",
    "id_noticia = 'N-' + primeros 12 caracteres del SHA-1 de la URL normalizada.",
    "Noticias deduplicadas por URL normalizada; se conserva la detección más antigua.",
    "Titulares de GDELT: se quitan los espacios insertados alrededor de la puntuación.",
    "fecha_publicacion de GDELT: solo si el medio la incluye en la URL; en otro caso queda nula. "
    "'seendate' se guarda como fecha_deteccion.",
    f"recirculada = verdadero si la fecha original precede a la detección por más de {UMBRAL_DIAS} días.",
    "Indicadores: cuadrícula completa país × indicador × año; lo que la API no entrega queda nulo, nunca cero.",
    "Sismos: tiempos de milisegundos a ISO 8601 UTC; longitud, latitud y profundidad separadas de la geometría.",
    "Registros que no pasan la validación: apartados en processed/rechazados.json con su motivo.",
    "Registros retirados por decisión del equipo: listados por ID y motivo en exclusiones.json.",
]


def _guardar(directorio_raw: Path, relativa: str, contenido: bytes) -> None:
    ruta = directorio_raw / relativa
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(contenido)


def _anotar(descargas: list, fuente: str, url: str, archivo: str, contenido: bytes | None,
            error: str | None = None, **extra) -> None:
    descargas.append(
        {
            "fuente": fuente,
            "url": url,
            "archivo": f"raw/{archivo}",
            "fecha_extraccion": a_iso_utc(ahora_utc()),
            "estado": "error" if error else "ok",
            "bytes": len(contenido) if contenido is not None else None,
            "sha256": sha256_bytes(contenido) if contenido is not None else None,
            **({"error": error} if error else {}),
            **extra,
        }
    )


def _descargar_gdelt(url: str) -> bytes:
    """GDELT responde texto plano cuando rechaza una consulta: se espera y se reintenta."""
    ultimo = ""
    for intento in range(3):
        contenido = descargar(url)
        texto = contenido.decode("utf-8", errors="replace").strip()
        if not texto or texto.startswith("{"):
            return contenido
        ultimo = texto[:120]
        time.sleep(PAUSA_GDELT * (intento + 2))
    raise RuntimeError(f"GDELT no devolvió JSON: {ultimo}")


def _omitir_por_limite(url: str) -> bytes:
    raise RuntimeError("pendiente: GDELT limitó las consultas en esta ejecución")


def descargar_fuentes(directorio: Path, dias: int, maximo: int, reanudar: bool = False) -> dict:
    """Baja las cuatro fuentes a datos/raw y deja el registro de la extracción.

    El registro se guarda tras cada descarga. Con `reanudar`, se conserva lo que
    ya bajó bien y solo se repite lo que falló o quedó pendiente.
    """
    crudo = directorio / "raw"
    ruta_registro = directorio / REGISTRO
    if reanudar and ruta_registro.exists():
        registro = leer_json(ruta_registro)
        registro["descargas"] = [d for d in registro["descargas"] if d["estado"] == "ok"]
    else:
        registro = {"fecha_corte_UTC": a_iso_utc(ahora_utc()), "dias_de_noticias": dias, "descargas": []}
    descargas = registro["descargas"]
    corte = leer_iso(registro["fecha_corte_UTC"])
    hechas = {descarga["archivo"] for descarga in descargas}

    def intentar(fuente, url, archivo, funcion=descargar, **extra) -> bool:
        """Devuelve False si el archivo ya estaba descargado."""
        if f"raw/{archivo}" in hechas:
            return False
        try:
            contenido = funcion(url)
            _guardar(crudo, archivo, contenido)
            _anotar(descargas, fuente, url, archivo, contenido, **extra)
        except (RuntimeError, OSError) as error:
            _anotar(descargas, fuente, url, archivo, None, error=str(error), **extra)
        escribir_json(ruta_registro, registro)
        print(f"  {descargas[-1]['estado']:5} {archivo}", flush=True)
        return True

    print("TVN RSS", flush=True)
    intentar("tvn", tvn.URL_RSS, ARCHIVO_TVN)
    print("Banco Mundial", flush=True)
    for consulta in banco_mundial.planificar():
        intentar("banco_mundial", consulta["url"], consulta["archivo"], indicador_id=consulta["indicador_id"])
    print("USGS", flush=True)
    intentar("usgs", usgs.url_consulta(), usgs.ARCHIVO)
    print("GDELT", flush=True)
    limitado = False
    for consulta in gdelt.planificar(corte, dias=registro["dias_de_noticias"], maximo=maximo):
        # Si GDELT ya rechazó una consulta, insistir solo alarga el bloqueo:
        # el resto queda pendiente para una ejecución con --reanudar.
        funcion = _omitir_por_limite if limitado else _descargar_gdelt
        if intentar(
            "gdelt", consulta["url"], consulta["archivo"], funcion=funcion,
            tema=consulta["tema"], consulta=consulta["consulta"],
            inicio=consulta["inicio"], fin=consulta["fin"],
        ):
            if descargas[-1]["estado"] != "ok":
                limitado = True
            elif not limitado:
                time.sleep(PAUSA_GDELT)

    escribir_json(ruta_registro, registro)
    return registro


def _fusionar(noticias: list[dict]) -> tuple[list[dict], int]:
    """Deja una noticia por URL. Devuelve la lista y cuántos duplicados se fusionaron."""
    unicas: dict[str, dict] = {}
    sin_id, duplicados = [], 0
    for noticia in noticias:
        clave = noticia.get("id_noticia")
        if not clave:
            sin_id.append(noticia)
            continue
        previa = unicas.get(clave)
        if previa is None:
            unicas[clave] = noticia
            continue
        duplicados += 1
        for campo in ("fecha_publicacion", "tema", "palabras_clave", "seccion", "pais_medio", "idioma"):
            if previa.get(campo) is None and noticia.get(campo) is not None:
                previa[campo] = noticia[campo]
        fechas = [leer_iso(previa.get("fecha_deteccion")), leer_iso(noticia.get("fecha_deteccion"))]
        fechas = [fecha for fecha in fechas if fecha]
        if fechas:
            previa["fecha_deteccion"] = a_iso_utc(min(fechas))
    ordenadas = sorted(
        unicas.values(),
        key=lambda fila: (fila.get("fecha_deteccion") or "", fila["id_noticia"]),
        reverse=True,
    )
    return ordenadas + sin_id, duplicados


def _retirar_excluidas(directorio: Path, noticias: list[dict]) -> tuple[list[dict], list[dict]]:
    """Quita las noticias listadas en datos/exclusiones.json y devuelve cuáles se retiraron."""
    ruta = directorio / EXCLUSIONES
    if not ruta.exists():
        return noticias, []
    motivos = {exclusion["id_noticia"]: exclusion["motivo"] for exclusion in leer_json(ruta)}
    presentes = {noticia.get("id_noticia") for noticia in noticias}
    retiradas = [
        {"id_noticia": identificador, "motivo": motivo}
        for identificador, motivo in motivos.items() if identificador in presentes
    ]
    return [noticia for noticia in noticias if noticia.get("id_noticia") not in motivos], retiradas


def procesar(directorio: Path) -> dict:
    """Convierte datos/raw en datos/processed, con reporte de calidad, catálogo y manifest."""
    registro = leer_json(directorio / REGISTRO)
    crudo = directorio / "raw"
    corte = registro["fecha_corte_UTC"]
    incidencias = [
        f"Descarga fallida: {descarga['archivo']} ({descarga.get('error')})"
        for descarga in registro["descargas"] if descarga["estado"] != "ok"
    ]
    correctas = [descarga for descarga in registro["descargas"] if descarga["estado"] == "ok"]

    noticias, indicadores, sismos = [], [], {"type": "FeatureCollection", "features": []}
    for descarga in correctas:
        ruta = directorio / descarga["archivo"]
        if not ruta.exists():
            incidencias.append(f"No está {descarga['archivo']} en esta copia: esa fuente no se reprocesó.")
            continue
        contenido, momento = ruta.read_bytes(), descarga["fecha_extraccion"]
        try:
            if descarga["fuente"] == "tvn":
                noticias += tvn.interpretar(contenido, momento)
            elif descarga["fuente"] == "gdelt":
                noticias += gdelt.interpretar(contenido, descarga["tema"], momento)
            elif descarga["fuente"] == "banco_mundial":
                indicadores += banco_mundial.interpretar(contenido, descarga["indicador_id"], momento)
            elif descarga["fuente"] == "usgs":
                sismos = usgs.interpretar(contenido, momento)
        except (ValueError, KeyError, IndexError, TypeError) as error:
            incidencias.append(f"No se pudo interpretar {descarga['archivo']}: {error}")

    noticias, duplicados = _fusionar(noticias)
    noticias, retiradas = _retirar_excluidas(directorio, noticias)
    marcar_recirculadas(noticias)
    momento_corte = leer_iso(corte)
    resultado_noticias = validar_noticias(noticias, ahora=momento_corte)
    resultado_indicadores = validar_indicadores(indicadores, ahora=momento_corte)
    resultado_eventos = validar_eventos(sismos["features"])

    escribir_csv(directorio / NOTICIAS, resultado_noticias.validas, CAMPOS_NOTICIAS)
    escribir_csv(directorio / INDICADORES, resultado_indicadores.validas, CAMPOS_INDICADORES)
    sismos["features"] = resultado_eventos.validas
    if "metadata" in sismos:
        sismos["metadata"]["cantidad"] = len(resultado_eventos.validas)
    escribir_json(directorio / EVENTOS, sismos)

    rechazados = {
        "noticias": resultado_noticias.rechazadas,
        "indicadores": resultado_indicadores.rechazadas,
        "eventos": resultado_eventos.rechazadas,
    }
    escribir_json(directorio / "processed/rechazados.json", rechazados)

    reporte = construir_reporte(
        resultado_noticias, resultado_indicadores, resultado_eventos, duplicados, incidencias
    )
    escribir_json(directorio / "reporte_calidad.json", reporte)
    (directorio / "reporte_calidad.md").write_text(a_markdown(reporte, corte), encoding="utf-8")

    archivos = {
        NOTICIAS: {
            "registros": len(resultado_noticias.validas),
            "licencia": f"{CONDICIONES['tvn']} {CONDICIONES['gdelt']}",
        },
        INDICADORES: {"registros": len(resultado_indicadores.validas), "licencia": CONDICIONES["banco_mundial"]},
        EVENTOS: {"registros": len(resultado_eventos.validas), "licencia": CONDICIONES["usgs"]},
    }
    manifest = manifiesto.construir(
        directorio, corte, archivos, registro["descargas"], TRANSFORMACIONES,
        {
            "por_validacion": {nombre: len(filas) for nombre, filas in rechazados.items()},
            "por_decision_del_equipo": retiradas,
        },
    )
    escribir_json(directorio / "fuentes.json", _catalogo(registro, reporte, manifest))
    return reporte


def _catalogo(registro: dict, reporte: dict, manifest: dict) -> list[dict]:
    """Catálogo de fuentes, con los mismos campos que pide la página de Notion."""
    def extraccion(fuente):
        fechas = [d["fecha_extraccion"] for d in registro["descargas"] if d["fuente"] == fuente and d["estado"] == "ok"]
        return max(fechas) if fechas else None

    def consultas(fuente):
        return sum(1 for d in registro["descargas"] if d["fuente"] == fuente and d["estado"] == "ok")

    noticias, indicadores, eventos = reporte["noticias"], reporte["indicadores"], reporte["eventos"]
    huella = lambda relativa: manifest["archivos"][relativa]["sha256"]  # noqa: E731
    return [
        {
            "fuente": "TVN · feed RSS público",
            "url": tvn.URL_RSS,
            "fecha_extraccion": extraccion("tvn"),
            "cobertura": f"{noticias['por_origen'].get(tvn.ORIGEN, 0)} titulares: los del día de la extracción más notas antiguas que el feed mantiene. No conserva el histórico completo.",
            "campos": ["titulo", "url", "fecha_publicacion", "palabras_clave", "seccion"],
            "licencia_condiciones": CONDICIONES["tvn"],
            "transformaciones": "Fechas a UTC, URL normalizada, ID estable. Se descartan descripción e imágenes.",
            "archivo": NOTICIAS,
            "sha256_snapshot": huella(NOTICIAS),
        },
        {
            "fuente": "GDELT · DOC 2.0 API (ArtList)",
            "url": gdelt.URL_API,
            "fecha_extraccion": extraccion("gdelt"),
            "cobertura": (
                f"{noticias['por_origen'].get(gdelt.ORIGEN, 0)} titulares únicos en {consultas('gdelt')} consultas "
                f"sobre los {registro['dias_de_noticias']} días previos al corte; detección de "
                f"{noticias['cobertura_deteccion']['minimo']} a {noticias['cobertura_deteccion']['maximo']}."
            ),
            "campos": ["titulo", "url", "medio", "idioma", "fecha_deteccion", "pais_medio", "tema"],
            "licencia_condiciones": CONDICIONES["gdelt"],
            "transformaciones": "'seendate' a fecha_deteccion en UTC, deduplicación por URL, limpieza de espacios del titular.",
            "archivo": NOTICIAS,
            "sha256_snapshot": huella(NOTICIAS),
        },
        {
            "fuente": "Banco Mundial · Indicators API v2",
            "url": banco_mundial.URL_API,
            "fecha_extraccion": extraccion("banco_mundial"),
            "cobertura": (
                f"{len(indicadores['paises'])} países × {len(indicadores['indicadores'])} indicadores × "
                f"{banco_mundial.ANIO_INICIAL}–{banco_mundial.ANIO_FINAL}: {indicadores['combinaciones']} combinaciones, "
                f"{indicadores['con_valor']} con valor y {indicadores['sin_valor']} nulas."
            ),
            "campos": CAMPOS_INDICADORES,
            "licencia_condiciones": CONDICIONES["banco_mundial"],
            "transformaciones": "Una consulta por indicador; cuadrícula completa con nulos explícitos; unidad documentada por indicador.",
            "archivo": INDICADORES,
            "sha256_snapshot": huella(INDICADORES),
        },
        {
            "fuente": "USGS · Earthquake Catalog (FDSN)",
            "url": usgs.url_consulta(),
            "fecha_extraccion": extraccion("usgs"),
            "cobertura": f"{eventos['validas']} sismos de magnitud ≥ 3 en 2024. {usgs.ADVERTENCIA}",
            "campos": ["id", "magnitude", "time", "updated", "longitude", "latitude", "depth", "place", "status", "url"],
            "licencia_condiciones": CONDICIONES["usgs"],
            "transformaciones": "Tiempos a ISO 8601 UTC; coordenadas copiadas a las propiedades.",
            "archivo": EVENTOS,
            "sha256_snapshot": huella(EVENTOS),
        },
    ]


def main() -> None:
    analizador = argparse.ArgumentParser(description="Construye el paquete congelado de datos públicos.")
    analizador.add_argument("--sin-descarga", action="store_true", help="reprocesa datos/raw sin usar internet")
    analizador.add_argument("--reanudar", action="store_true", help="conserva lo ya descargado y repite lo que falló")
    analizador.add_argument("--dias", type=int, default=30, help="días de noticias previos al corte")
    analizador.add_argument("--maximo", type=int, default=75, help="artículos por consulta de GDELT (tope 250)")
    analizador.add_argument("--directorio", type=Path, default=DIRECTORIO)
    opciones = analizador.parse_args()

    if not opciones.sin_descarga:
        descargar_fuentes(
            opciones.directorio, opciones.dias,
            min(opciones.maximo, gdelt.MAXIMO_POR_CONSULTA), opciones.reanudar,
        )
    reporte = procesar(opciones.directorio)
    resumen = {nombre: {"validas": reporte[nombre]["validas"], "rechazadas": reporte[nombre]["rechazadas"]}
               for nombre in ("noticias", "indicadores", "eventos")}
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    for incidencia in reporte["incidencias"]:
        print("INCIDENCIA:", incidencia)


if __name__ == "__main__":
    main()
