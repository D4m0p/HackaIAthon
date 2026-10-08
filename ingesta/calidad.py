"""Reporte de calidad del paquete: qué entró, qué se apartó y por qué."""

from __future__ import annotations

from collections import Counter

from .validacion import (
    CAMPOS_EVENTOS, CAMPOS_INDICADORES, CAMPOS_NOTICIAS, Resultado, es_vacio,
)


def _motivos(resultado: Resultado) -> dict:
    conteo = Counter()
    for rechazada in resultado.rechazadas:
        for motivo in rechazada["motivos"]:
            conteo[motivo.split(":")[0]] += 1
    return dict(conteo.most_common())


def _nulos(filas: list[dict], campos: list[str]) -> dict:
    conteo = {campo: sum(1 for fila in filas if es_vacio(fila.get(campo))) for campo in campos}
    return {campo: cantidad for campo, cantidad in conteo.items() if cantidad}


def _rango(valores: list) -> dict:
    presentes = sorted(valor for valor in valores if not es_vacio(valor))
    return {"minimo": presentes[0], "maximo": presentes[-1]} if presentes else {"minimo": None, "maximo": None}


def _base(resultado: Resultado) -> dict:
    total = len(resultado.validas) + len(resultado.rechazadas)
    return {
        "leidas": total,
        "validas": len(resultado.validas),
        "rechazadas": len(resultado.rechazadas),
        "motivos_de_rechazo": _motivos(resultado),
    }


def resumen_noticias(resultado: Resultado, duplicados_por_url: int = 0) -> dict:
    filas = resultado.validas
    resumen = _base(resultado)
    resumen.update(
        {
            "duplicados_por_url_fusionados": duplicados_por_url,
            "de_tvn": sum(1 for fila in filas if fila.get("medio") == "TVN"),
            "por_origen": dict(Counter(fila.get("origen") for fila in filas).most_common()),
            "por_idioma": dict(Counter(fila.get("idioma") or "sin dato" for fila in filas).most_common()),
            "por_tema_de_consulta": dict(Counter(fila.get("tema") or "sin dato" for fila in filas).most_common()),
            "medios_distintos": len({fila.get("medio") for fila in filas}),
            "recirculadas": sum(1 for fila in filas if fila.get("recirculada")),
            "sin_fecha_de_publicacion": sum(1 for fila in filas if es_vacio(fila.get("fecha_publicacion"))),
            "cobertura_deteccion": _rango([fila.get("fecha_deteccion") for fila in filas]),
            "nulos_por_campo": _nulos(filas, CAMPOS_NOTICIAS),
        }
    )
    return resumen


def resumen_indicadores(resultado: Resultado) -> dict:
    filas = resultado.validas
    con_valor = [fila for fila in filas if not es_vacio(fila.get("valor"))]
    faltantes = Counter(fila.get("indicador_id") for fila in filas if es_vacio(fila.get("valor")))
    resumen = _base(resultado)
    resumen.update(
        {
            "combinaciones": len(filas),
            "con_valor": len(con_valor),
            "sin_valor": len(filas) - len(con_valor),
            "sin_valor_por_indicador": dict(faltantes.most_common()),
            "paises": sorted({fila.get("pais_iso3") for fila in filas}),
            "indicadores": sorted({fila.get("indicador_id") for fila in filas}),
            "cobertura_anios": _rango([fila.get("anio") for fila in filas]),
            "nulos_por_campo": _nulos(filas, CAMPOS_INDICADORES),
        }
    )
    return resumen


def resumen_eventos(resultado: Resultado) -> dict:
    propiedades = [evento["properties"] for evento in resultado.validas]
    resumen = _base(resultado)
    resumen.update(
        {
            "cobertura": _rango([fila.get("time") for fila in propiedades]),
            "magnitud": _rango([fila.get("magnitude") for fila in propiedades]),
            "por_estado": dict(Counter(fila.get("status") or "sin dato" for fila in propiedades).most_common()),
            "nulos_por_campo": _nulos(propiedades, CAMPOS_EVENTOS),
        }
    )
    return resumen


def construir_reporte(noticias: Resultado, indicadores: Resultado, eventos: Resultado,
                      duplicados_por_url: int = 0, incidencias: list[str] | None = None) -> dict:
    return {
        "noticias": resumen_noticias(noticias, duplicados_por_url),
        "indicadores": resumen_indicadores(indicadores),
        "eventos": resumen_eventos(eventos),
        "incidencias": list(incidencias or []),
    }


def _tabla(pares: dict) -> list[str]:
    if not pares:
        return ["Ninguno.", ""]
    lineas = ["| Concepto | Cantidad |", "|---|---|"]
    lineas += [f"| {clave} | {valor} |" for clave, valor in pares.items()]
    return lineas + [""]


def a_markdown(reporte: dict, fecha_corte: str | None = None) -> str:
    """Versión legible del reporte, lista para pegar en Notion."""
    noticias, indicadores, eventos = reporte["noticias"], reporte["indicadores"], reporte["eventos"]
    lineas = ["# Reporte de calidad del paquete", ""]
    if fecha_corte:
        lineas += [f"Fecha de corte (UTC): {fecha_corte}", ""]

    lineas += ["## Resumen", "", "| Archivo | Leídas | Válidas | Apartadas |", "|---|---|---|---|"]
    for nombre, bloque in (("noticias.csv", noticias), ("indicadores.csv", indicadores), ("eventos.geojson", eventos)):
        lineas.append(f"| {nombre} | {bloque['leidas']} | {bloque['validas']} | {bloque['rechazadas']} |")
    lineas.append("")

    lineas += ["## Noticias", ""]
    cobertura = noticias["cobertura_deteccion"]
    lineas += [
        f"- Registros únicos: {noticias['validas']} (meta 200, mínimo operativo 100).",
        f"- De TVN: {noticias['de_tvn']} (mínimo 20).",
        f"- Medios distintos: {noticias['medios_distintos']}.",
        f"- Duplicados por URL fusionados: {noticias['duplicados_por_url_fusionados']}.",
        f"- Cobertura efectiva de detección: {cobertura['minimo']} a {cobertura['maximo']}.",
        f"- Sin fecha de publicación conocida: {noticias['sin_fecha_de_publicacion']} "
        "(GDELT solo informa la detección; no se inventa la publicación).",
        f"- Marcadas como recirculadas: {noticias['recirculadas']}.",
        "",
        "### Por origen", "",
    ]
    lineas += _tabla(noticias["por_origen"])
    lineas += ["### Por tema de la consulta de extracción", ""] + _tabla(noticias["por_tema_de_consulta"])
    lineas += ["### Por idioma", ""] + _tabla(noticias["por_idioma"])
    lineas += ["### Motivos de rechazo", ""] + _tabla(noticias["motivos_de_rechazo"])
    lineas += ["### Nulos conservados por campo", ""] + _tabla(noticias["nulos_por_campo"])

    lineas += ["## Indicadores", ""]
    anios = indicadores["cobertura_anios"]
    lineas += [
        f"- Cuadrícula: {indicadores['combinaciones']} combinaciones país × indicador × año "
        f"({len(indicadores['paises'])} países, {len(indicadores['indicadores'])} indicadores, "
        f"{anios['minimo']} a {anios['maximo']}).",
        f"- Con valor: {indicadores['con_valor']}. Sin valor (conservadas como nulo): {indicadores['sin_valor']}.",
        "",
        "### Observaciones faltantes por indicador", "",
    ]
    lineas += _tabla(indicadores["sin_valor_por_indicador"])
    lineas += ["### Motivos de rechazo", ""] + _tabla(indicadores["motivos_de_rechazo"])

    lineas += ["## Eventos sísmicos", ""]
    lineas += [
        f"- Eventos: {eventos['validas']}.",
        f"- Período: {eventos['cobertura']['minimo']} a {eventos['cobertura']['maximo']}.",
        f"- Magnitud: {eventos['magnitud']['minimo']} a {eventos['magnitud']['maximo']}.",
        "",
        "### Motivos de rechazo", "",
    ]
    lineas += _tabla(eventos["motivos_de_rechazo"])

    lineas += ["## Incidencias", ""]
    lineas += [f"- {incidencia}" for incidencia in reporte["incidencias"]] or ["Ninguna."]
    return "\n".join(lineas).rstrip() + "\n"
