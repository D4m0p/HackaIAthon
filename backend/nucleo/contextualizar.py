"""
Etapa 3 · Contextualizar

Vincula cada evento con datos oficiales pertinentes:
- Indicadores del Banco Mundial, si los titulares mencionan el tema del indicador.
- Sismos de USGS, si los titulares hablan de un sismo y coinciden fecha y lugar o magnitud.

Reglas del reto que se respetan aquí:
- Si no hay relación sustentada, NO se fuerza: el evento queda sin contexto y se explica por qué.
- Un dato anual no es una medición de hoy: siempre va con año, unidad y advertencia (T04).
- Los valores faltantes se muestran como "sin dato", nunca como 0.
"""

import json
import re
from datetime import datetime, timezone

import pandas as pd

from nucleo import config
from nucleo.organizar import normalizar


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------
def _normalizar_indicadores(df):
    df["anio"] = df["anio"].astype(int)
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df["valor"] = df["valor"].astype(object).where(df["valor"].notna(), None)
    return df


def cargar_indicadores(ruta_csv):
    """Lee indicadores.csv. Los valores vacíos quedan como None (no como 0)."""
    return _normalizar_indicadores(pd.read_csv(ruta_csv))


def indicadores_desde_lista(filas):
    """Lo mismo, a partir de la lista que entrega ingesta.cargar_paquete() (equipo A)."""
    return _normalizar_indicadores(pd.DataFrame(filas))


def _fecha_sismo(valor):
    """USGS original da milisegundos; el paquete del equipo A, texto ISO 8601."""
    if isinstance(valor, (int, float)):
        return datetime.fromtimestamp(valor / 1000, tz=timezone.utc)
    return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))


def _sismo(propiedades, coordenadas=None, id_feature=None):
    """Un sismo en nuestro formato. Acepta las propiedades de USGS ("mag", "time" en ms)
    y las del paquete del equipo A ("magnitude", "time" ISO, longitude/latitude/depth)."""
    p = propiedades
    lon, lat, prof = coordenadas or (p.get("longitude"), p.get("latitude"), p.get("depth"))
    return {
        "id": p.get("id") or id_feature,
        "magnitud": p.get("magnitude", p.get("mag")),
        "lugar": p.get("place") or "",
        "fecha": _fecha_sismo(p["time"]),
        "estado": p.get("status"),
        "url": p.get("url"),
        "latitud": lat, "longitud": lon, "profundidad_km": prof,
    }


def cargar_sismos(ruta_geojson):
    """Lee eventos.geojson y lo aplana a una lista de dicts."""
    with open(ruta_geojson, encoding="utf-8") as f:
        datos = json.load(f)
    sismos = []
    for feature in datos["features"]:
        geometria = feature.get("geometry") or {}
        sismos.append(_sismo(feature["properties"], geometria.get("coordinates"), feature.get("id")))
    return sismos


def sismos_desde_lista(propiedades):
    """A partir de la lista que entrega ingesta.cargar_paquete() (propiedades ya aplanadas)."""
    return [_sismo(p) for p in propiedades]


# ---------------------------------------------------------------------------
# Banco Mundial
# ---------------------------------------------------------------------------
def _palabra_encontrada(texto, palabras):
    return next((p for p in palabras if p in texto), None)


def _valor_o_sin_dato(valor):
    return valor if valor is not None else "sin dato"


def _vinculo_indicador(indicadores, indicador_id, palabra):
    """Arma la evidencia de un indicador: último año con dato de Panamá,
    serie corta y comparación con otros países en ese mismo año."""
    datos = indicadores[indicadores["indicador_id"] == indicador_id]
    panama = datos[(datos["pais_iso3"] == config.PAIS_PRINCIPAL) & datos["valor"].notna()]
    if panama.empty:
        return None

    ultimo = panama.sort_values("anio").iloc[-1]
    anio = int(ultimo["anio"])
    serie = datos[datos["pais_iso3"] == config.PAIS_PRINCIPAL].sort_values("anio").tail(config.ANIOS_SERIE)

    comparacion = []
    for pais in config.PAISES_COMPARACION:
        fila = datos[(datos["pais_iso3"] == pais) & (datos["anio"] == anio)]
        valor = fila.iloc[0]["valor"] if not fila.empty else None
        comparacion.append({"pais": pais, "anio": anio, "valor": _valor_o_sin_dato(valor)})

    return {
        "tipo": "indicador_banco_mundial",
        # ID de evidencia: lo que se citará en fichas y borradores
        "id_evidencia": f"WB:{config.PAIS_PRINCIPAL}:{indicador_id}:{anio}",
        "indicador_id": indicador_id,
        "nombre": config.INDICADORES[indicador_id]["nombre"],
        "pais": config.PAIS_PRINCIPAL,
        "anio": anio,
        "valor": ultimo["valor"],
        "unidad": ultimo["unidad"],
        "serie": [{"anio": int(r["anio"]), "valor": _valor_o_sin_dato(r["valor"])} for _, r in serie.iterrows()],
        "comparacion": comparacion,
        "fuente_url": ultimo["fuente_url"],
        "licencia": ultimo["licencia"],
        "advertencia": f"Dato anual {anio} del Banco Mundial. No es una medición actual "
                       f"ni describe lo que reporta la noticia.",
        "motivo_vinculo": f"los titulares mencionan '{palabra}'",
    }


def vincular_indicadores(evento, indicadores):
    texto = normalizar(" ".join(n["titulo"] for n in evento["noticias"]))
    vinculos = []
    for indicador_id, info in config.INDICADORES.items():
        palabra = _palabra_encontrada(texto, info["palabras"])
        if palabra:
            vinculo = _vinculo_indicador(indicadores, indicador_id, palabra)
            if vinculo:
                vinculos.append(vinculo)
    return vinculos


# ---------------------------------------------------------------------------
# USGS
# ---------------------------------------------------------------------------
def _magnitudes_en_texto(texto):
    """Números tipo magnitud en los titulares: '4.8', '5,1' -> [4.8, 5.1]"""
    return [float(m.replace(",", ".")) for m in re.findall(r"\b\d[.,]\d\b", texto)]


def vincular_sismos(evento, sismos):
    texto = normalizar(" ".join(n["titulo"] for n in evento["noticias"]))
    if not _palabra_encontrada(texto, config.PALABRAS_SISMO) or not evento["fecha_primera"]:
        return []  # solo hechos sísmicos; nunca para inundaciones u otros eventos

    fecha_evento = datetime.fromisoformat(evento["fecha_primera"])
    magnitudes = _magnitudes_en_texto(texto)
    palabras_titular = set(re.findall(r"\w+", texto))

    vinculos = []
    for s in sismos:
        dias = abs((s["fecha"] - fecha_evento).total_seconds()) / 86400
        if dias > config.VENTANA_DIAS_SISMO:
            continue
        coincide_magnitud = any(abs(m - s["magnitud"]) <= config.TOLERANCIA_MAGNITUD for m in magnitudes)
        # Nombres de lugar en común (palabras de 4+ letras, sin contar "panama")
        palabras_lugar = {p for p in re.findall(r"\w+", normalizar(s["lugar"])) if len(p) >= 4}
        lugares_comunes = (palabras_titular & palabras_lugar) - {"panama"}
        if not (coincide_magnitud or lugares_comunes):
            continue

        motivos = [f"fecha a {dias:.1f} días"]
        if coincide_magnitud:
            motivos.append(f"magnitud {s['magnitud']} coincide con el titular")
        if lugares_comunes:
            motivos.append(f"lugar en común: {', '.join(sorted(lugares_comunes))}")

        vinculos.append({
            "tipo": "sismo_usgs",
            "id_evidencia": f"USGS:{s['id']}",
            "magnitud": s["magnitud"],
            "lugar": s["lugar"],
            "fecha_utc": s["fecha"].isoformat(),
            "profundidad_km": s["profundidad_km"],
            "estado": s["estado"],
            "fuente_url": s["url"],
            "advertencia": "Dato sísmico oficial de USGS. Solo respalda hechos sísmicos "
                           "(magnitud, hora, ubicación), no daños ni pérdidas.",
            "motivo_vinculo": "; ".join(motivos),
        })
    return vinculos


# ---------------------------------------------------------------------------
# Función principal de la etapa
# ---------------------------------------------------------------------------
def contextualizar(eventos, indicadores, sismos):
    """Agrega a cada evento la lista 'contexto' con los datos oficiales vinculados."""
    for evento in eventos:
        evento["contexto"] = vincular_indicadores(evento, indicadores) + vincular_sismos(evento, sismos)
        if not evento["contexto"]:
            evento["sin_contexto_motivo"] = ("No se encontró un dato oficial pertinente en el corpus; "
                                             "no se fuerza una relación.")
    return eventos
