"""
Etapa 4 · Priorizar

Calcula para cada evento:
- Un puntaje de atención P = 30R + 25I + 20U + 15N + 10E (0 a 100), con cada
  componente explicado. Es una herramienta para ORDENAR la revisión: no es una
  probabilidad de que la noticia sea cierta.
- Un estado de evidencia (insuficiente / parcial / suficiente para el borrador),
  INDEPENDIENTE del puntaje. Una prioridad alta no habilita publicar nada.
"""

import re
from datetime import datetime

import numpy as np

from nucleo import config
from nucleo.organizar import embeber, normalizar

AVISO_SOLO_TITULAR = "Basado únicamente en titular/metadatos."
AVISO_PRIORIDAD = "La prioridad ordena la revisión; no confirma la noticia ni habilita su publicación."


def _fecha(valor):
    return datetime.fromisoformat(valor.replace("Z", "+00:00")) if valor else None


def _limitar(x):
    return max(0.0, min(1.0, x))


def _texto(evento):
    return normalizar(" ".join(n["titulo"] for n in evento["noticias"]))


def _tiene_dato_oficial(evento):
    return bool(evento.get("contexto"))


# ---------------------------------------------------------------------------
# Componentes (cada uno devuelve valor 0-1 y una explicación en español)
# ---------------------------------------------------------------------------
def relevancia(evento):
    """R: mitad por ser un tema del reto, mitad por estar vinculado con Panamá.
    Si el tema es "otro", R = 0: el reto define relevancia como relación con
    Panamá Y con los temas de la modalidad."""
    es_tema_del_reto = evento["tema"] != "otro"
    if not es_tema_del_reto:
        return 0.0, "tema 'otro': fuera de los temas del reto"
    texto = _texto(evento)
    lugar = next((l for l in config.LUGARES_PANAMA if re.search(rf"\b{l}\b", texto)), None)
    medio_local = next((n["medio"] for n in evento["noticias"]
                        if normalizar(n["medio"]) in config.MEDIOS_PANAMENOS), None)
    vinculo_panama = lugar or medio_local

    valor = 0.5 + 0.5 * bool(vinculo_panama)
    partes = [f"tema '{evento['tema']}' es del reto"]
    if lugar:
        partes.append(f"menciona '{lugar}'")
    elif medio_local:
        partes.append(f"publicado por {medio_local}")
    else:
        partes.append("sin vínculo explícito con Panamá")
    return valor, "; ".join(partes)


def impacto(evento):
    """I: peso base del tema + bonus si un dato oficial respalda el alcance."""
    base = config.IMPACTO_BASE_TEMA.get(evento["tema"], config.IMPACTO_BASE_TEMA["otro"])
    bonus = config.BONUS_IMPACTO_DATO_OFICIAL if _tiene_dato_oficial(evento) else 0.0
    explicacion = f"peso base del tema {base}"
    if bonus:
        explicacion += f" + {bonus} por dato oficial vinculado"
    return _limitar(base + bonus), explicacion


def urgencia(evento, fecha_corte):
    """U: 1 si se publicó en la fecha de corte, baja a 0 en DIAS_URGENCIA días.
    Usa la fecha de PUBLICACIÓN, no la de detección."""
    if not evento["fecha_ultima"]:
        return 0.0, "sin fecha conocida"
    dias = (fecha_corte - _fecha(evento["fecha_ultima"])).total_seconds() / 86400
    valor = _limitar(1 - dias / config.DIAS_URGENCIA)
    # La fecha puede ser de publicación o de detección: se dice cuál (§7)
    tipo = next((n["tipo_fecha"] for n in evento["noticias"] if n["fecha"] and
                 _fecha(n["fecha"]) == _fecha(evento["fecha_ultima"])), None)
    return valor, (f"fecha más reciente ({tipo or 'desconocida'}) hace {dias:.1f} días "
                   f"(ventana de {config.DIAS_URGENCIA})")


def es_recirculada(evento):
    """Noticia antigua que volvió a circular (la marca viene de organizar.py,
    que usa el campo "recirculada" del equipo A cuando existe)."""
    return next((n for n in evento["noticias"] if n["antiguedad"] == "recirculada"), None)


def es_antigua_en_feed(evento):
    """Nota de TVN con fecha de publicación antigua que sigue en el feed RSS.
    No es "recirculada": nadie la volvió a difundir, solo es vieja."""
    return next((n for n in evento["noticias"] if n["antiguedad"] == "antigua_en_feed"), None)


def novedad(evento, anteriores, vectores):
    """N: qué tan distinto es de los eventos publicados antes (últimos DIAS_NOVEDAD días).
    El número de noticias del evento NO se usa: duplicar no suma."""
    vieja = es_recirculada(evento)
    if vieja:
        return 0.0, (f"posible noticia recirculada: {vieja['id_noticia']} con fecha original "
                     f"{vieja['fecha'][:10]} ({vieja['tipo_fecha']}), detectada {(vieja['fecha_deteccion'] or '?')[:10]}")
    antigua = es_antigua_en_feed(evento)
    if antigua:
        return 0.0, (f"nota antigua que sigue en el feed de TVN: {antigua['id_noticia']} "
                     f"publicada {antigua['fecha'][:10]}; no es un hecho nuevo")
    if not anteriores:
        return 1.0, "no hay eventos anteriores parecidos"

    sims = [float(vectores[evento["id_evento"]] @ vectores[a["id_evento"]]) for a in anteriores]
    mayor = int(np.argmax(sims))
    sim = sims[mayor]
    valor = _limitar((config.NOVEDAD_SIM_MAX - sim) / (config.NOVEDAD_SIM_MAX - config.NOVEDAD_SIM_MIN))
    return valor, f"parecido {sim:.2f} con el evento anterior más cercano ({anteriores[mayor]['id_evento']})"


def evidencia_disponible(evento):
    """E: hasta 0.6 por fuentes independientes (1 fuente = 0, 3 o más = 0.6)
    + 0.4 si hay un dato oficial vinculado."""
    n = evento["n_fuentes_independientes"]
    por_fuentes = 0.6 * _limitar((n - 1) / 2)
    por_oficial = 0.4 if _tiene_dato_oficial(evento) else 0.0
    explicacion = f"{n} fuente(s) independiente(s)"
    explicacion += "; con dato oficial" if por_oficial else "; sin dato oficial"
    return por_fuentes + por_oficial, explicacion


# ---------------------------------------------------------------------------
# Estado de evidencia (independiente del puntaje)
# ---------------------------------------------------------------------------
def posibles_contradicciones(evento):
    """Detecta titulares del mismo evento con porcentajes distintos (ej. 9.5% vs 7.4%).
    Es una alerta para revisión, no decide cuál es la cifra correcta."""
    cifras = {}
    for n in evento["noticias"]:
        for cifra in re.findall(r"\d+(?:[.,]\d+)?\s*%", n["titulo"]):
            cifras.setdefault(cifra.replace(" ", "").replace(",", "."), []).append(n["id_noticia"])
    if len(cifras) < 2:
        return []
    return [{"cifra": c, "ids_noticia": ids} for c, ids in cifras.items()]


def estado_evidencia(evento):
    n = evento["n_fuentes_independientes"]
    oficial = _tiene_dato_oficial(evento)
    if evento["posibles_contradicciones"]:
        return "parcial", "los titulares reportan cifras distintas; requiere verificar cuál es la correcta"
    if n >= 2 and oficial:
        return "suficiente para el borrador", f"{n} fuentes independientes y dato oficial"
    if n >= 2 or oficial:
        return "parcial", f"{n} fuente(s) independiente(s)" + (" y dato oficial" if oficial else ", sin dato oficial")
    return "insuficiente", "una sola procedencia y sin dato oficial"


# ---------------------------------------------------------------------------
# Función principal de la etapa
# ---------------------------------------------------------------------------
def _nivel(puntaje):
    return next(nombre for minimo, nombre in config.NIVELES if puntaje >= minimo)


def priorizar(eventos, fecha_corte):
    """Agrega 'prioridad' y 'estado_evidencia' a cada evento y los devuelve ordenados.
    fecha_corte: fecha del snapshot (manifest), NO la fecha de hoy, para que el
    resultado sea reproducible."""
    if isinstance(fecha_corte, str):
        fecha_corte = _fecha(fecha_corte)

    # Un vector por evento: promedio de los vectores de sus titulares
    vectores = {}
    for e in eventos:
        v = embeber(n["titulo"] for n in e["noticias"]).mean(axis=0)
        vectores[e["id_evento"]] = v / np.linalg.norm(v)

    for e in eventos:
        inicio = _fecha(e["fecha_primera"])
        anteriores = [a for a in eventos
                      if a is not e and a["fecha_primera"] and inicio
                      and 0 < (inicio - _fecha(a["fecha_primera"])).days <= config.DIAS_NOVEDAD]

        componentes = {
            "R": relevancia(e),
            "I": impacto(e),
            "U": urgencia(e, fecha_corte),
            "N": novedad(e, anteriores, vectores),
            "E": evidencia_disponible(e),
        }
        puntaje_formula = round(sum(config.PESOS[k] * v for k, (v, _) in componentes.items()), 1)

        # Regla explícita: una noticia recirculada nunca pasa del nivel "bajo"
        ajuste = None
        puntaje = puntaje_formula
        if es_recirculada(e) and puntaje_formula >= config.TOPE_RECIRCULADA:
            puntaje = config.TOPE_RECIRCULADA - 0.1
            ajuste = (f"posible noticia recirculada: el puntaje de la fórmula ({puntaje_formula}) "
                      f"se limita a {puntaje} para que no pase del nivel 'bajo'")

        e["prioridad"] = {
            "puntaje": puntaje,
            "puntaje_formula": puntaje_formula,
            "ajuste": ajuste,
            "nivel": _nivel(puntaje),
            "componentes": {k: {"valor": round(v, 3), "peso": config.PESOS[k],
                                "aporte": round(config.PESOS[k] * v, 1), "explicacion": txt}
                            for k, (v, txt) in componentes.items()},
            "formula": "P = 30R + 25I + 20U + 15N + 10E",
            "version_reglas": config.VERSION_REGLAS,
            "aviso": AVISO_PRIORIDAD,
        }
        e["posibles_contradicciones"] = posibles_contradicciones(e)
        e["estado_evidencia"], e["motivo_estado_evidencia"] = estado_evidencia(e)
        # El paquete del equipo A usa "titular_y_metadatos"; los datos de ejemplo, "titular"
        if all(n["alcance_texto"] in config.ALCANCES_SOLO_TITULAR for n in e["noticias"]):
            e["aviso_alcance"] = AVISO_SOLO_TITULAR

    # Orden: mayor puntaje; empates -> mayor urgencia y luego ID
    eventos.sort(key=lambda e: (-e["prioridad"]["puntaje"],
                                -e["prioridad"]["componentes"]["U"]["valor"],
                                e["id_evento"]))
    for posicion, e in enumerate(eventos, start=1):
        e["prioridad"]["posicion"] = posicion
    return eventos
