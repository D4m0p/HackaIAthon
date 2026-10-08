"""
Ficha y borrador por plantilla (sin LLM).

Se usa cuando no hay conexión o el LLM no responde. Arma, solo con código, la
misma estructura que devuelve el LLM, usando únicamente frases que se pueden
citar tal cual: lo que cada medio publicó y los datos oficiales con su año.
No interpreta ni infiere nada; por eso es más pobre que la redacción del LLM,
pero nunca inventa. Pasa por el mismo validador que el LLM.
"""

NOMBRE_TEMA = {
    "economia": "economía",
    "logistica_canal": "logística y Canal",
    "turismo": "turismo",
    "servicios_publicos": "servicios públicos",
    "eventos_naturales": "eventos naturales",
    "regulacion": "regulación",
    "otro": "otros temas",
}


def _afirmaciones(paquete):
    afirmaciones = []
    for id_ev, e in paquete.items():
        if e["tipo"] == "noticia":
            afirmaciones.append({
                "texto": f"{e['medio']} publicó el titular: «{e['titulo']}» [{id_ev}:titulo].",
                "tipo": "declaracion",
                "citas": [{"id_evidencia": id_ev, "campo": "titulo"}],
            })
        elif e["tipo"] == "indicador_banco_mundial":
            afirmaciones.append({
                "texto": (f"Según el Banco Mundial, el dato anual de {e['anio']} [{id_ev}:anio] de "
                          f"{e['nombre'].lower()} en Panamá fue {e['valor']} ({e['unidad']}) [{id_ev}:valor]."),
                "tipo": "hecho",
                "citas": [{"id_evidencia": id_ev, "campo": "valor"}, {"id_evidencia": id_ev, "campo": "anio"}],
            })
        elif e["tipo"] == "sismo_usgs":
            afirmaciones.append({
                "texto": (f"USGS registró un sismo de magnitud {e['magnitud']} [{id_ev}:magnitud] "
                          f"({e['lugar']}) el {e['fecha_utc'][:10]} UTC [{id_ev}:fecha_utc]."),
                "tipo": "hecho",
                "citas": [{"id_evidencia": id_ev, "campo": "magnitud"}, {"id_evidencia": id_ev, "campo": "fecha_utc"}],
            })
    return afirmaciones


def _pendientes(evento, paquete):
    pendientes = []
    if evento.get("aviso_alcance"):
        pendientes.append("Solo se dispone del titular: falta la nota completa para confirmar los detalles.")
    if evento["posibles_contradicciones"]:
        cifras = ", ".join(c["cifra"] for c in evento["posibles_contradicciones"])
        pendientes.append(f"Las fuentes reportan cifras distintas ({cifras}): verificar cuál es la correcta "
                          f"y a qué periodo corresponde.")
    if evento["n_fuentes_independientes"] < 2:
        pendientes.append("Hay una sola procedencia: falta una confirmación independiente.")
    indicadores = [e for e in paquete.values() if e["tipo"] == "indicador_banco_mundial"]
    if indicadores:
        pendientes.append("El dato del Banco Mundial es anual e histórico: no describe la situación actual.")
    if not evento.get("contexto"):
        pendientes.append("No hay un dato oficial vinculado en el corpus.")
    return pendientes


def _accion(estado):
    return {
        "insuficiente": "Investigar antes de producir: buscar la fuente primaria y una segunda fuente independiente.",
        "parcial": "Verificar lo pendiente antes de aprobar el borrador.",
    }.get(estado, "Revisar el borrador y comprobar cada cita antes de aprobarlo.")


def _preguntas(evento):
    titulo = evento["titulo_representativo"]
    segunda = ("¿Cuál de las cifras reportadas es la correcta y a qué periodo corresponde?"
               if evento["posibles_contradicciones"] else
               "¿Qué otras fuentes independientes confirman o contradicen lo reportado?")
    return [f"¿Cuál es la fuente primaria de «{titulo}»?",
            segunda,
            "¿A quién afecta directamente y desde cuándo?"]


def redaccion_por_plantilla(evento, paquete, con_borrador):
    """Devuelve un dict con la misma forma que la respuesta del LLM."""
    afirmaciones = _afirmaciones(paquete)
    pendientes = _pendientes(evento, paquete)
    n_noticias = sum(1 for e in paquete.values() if e["tipo"] == "noticia")

    redaccion = {
        "que_se_reporta": (f"{n_noticias} titular(es) de {evento['n_fuentes_independientes']} procedencia(s) "
                           f"independiente(s) sobre {NOMBRE_TEMA.get(evento['tema'], evento['tema'])}."),
        "afirmaciones": afirmaciones,
        "que_falta_verificar": pendientes,
        "accion_recomendada": _accion(evento["estado_evidencia"]),
        "preguntas_investigacion": _preguntas(evento),
    }
    if not con_borrador:
        return redaccion

    frases = " ".join(a["texto"] for a in afirmaciones)
    pendiente = " ".join(pendientes)
    primera = afirmaciones[0]["texto"] if afirmaciones else ""
    redaccion["borrador"] = {
        "titulo_propuesto": f"(Plantilla) «{evento['titulo_representativo']}»",
        "enfoque_interes_publico": "Pendiente de definir por la persona editora: la plantilla no propone enfoque.",
        "brief": f"{frases} Pendiente: {pendiente}",
        "verificaciones_pendientes": pendientes,
        "guion_45_60s": f"{frases} Hay aspectos pendientes de verificación.",
        "copy_digital": f"{primera} Información pendiente de verificación.",
    }
    return redaccion
