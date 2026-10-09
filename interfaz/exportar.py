"""La ficha de un caso como documento para Notion.

Se arma una sola vez como lista de nodos y de ahí salen las dos formas de entrega:
Markdown para pegar a mano y bloques para la API. Así el registro manual y el
automático dicen exactamente lo mismo.
"""

from __future__ import annotations

from .consulta import COMPONENTES, formatear_valor
from .fuentes import PAISES, hora_panama
from .puente import config
from .texto import NOMBRE_TEMA, contar_palabras

AVISO_BORRADOR = "Borrador para revisión humana. No es una publicación."
TIPO_AFIRMACION = {"hecho": "Hecho", "declaracion": "Declaración", "inferencia": "Inferencia", "hipotesis": "Hipótesis"}
TIPO_FECHA = {"publicacion": "publicada", "deteccion": "detectada", "primera_aparicion": "primera aparición"}
MODALIDAD = {"editorial_tvn": "Editorial · TVN Media"}
LIMITE_TEXTO_NOTION = 1900


def _fecha_noticia(noticia: dict) -> str:
    if not noticia.get("fecha"):
        return "sin fecha conocida"
    tipo = TIPO_FECHA.get(noticia.get("tipo_fecha"), "fecha")
    marca = " · contenido antiguo" if noticia.get("antiguedad") else ""
    return f"{tipo} {hora_panama(noticia['fecha'])}{marca}"


def _cita_al_final(afirmacion: dict) -> str:
    """El texto con sus citas visibles, aunque quien redactó no las haya puesto entre corchetes."""
    texto = afirmacion["texto"]
    faltan = [f"[{c['id_evidencia']}:{c['campo']}]" for c in afirmacion["citas"]
              if f"[{c['id_evidencia']}:{c['campo']}]" not in texto]
    return f"{texto} {' '.join(faltan)}".strip()


def _fuentes(vista: dict) -> list[list[str]]:
    filas = []
    for noticia in vista["noticias"]:
        if noticia["no_confiable"]:
            filas.append([noticia["id_noticia"], "Noticia · contenido no confiable", noticia["medio"],
                          "Titular excluido: intenta dar instrucciones al sistema", _fecha_noticia(noticia), noticia["url"]])
        else:
            filas.append([noticia["id_noticia"], "Noticia · titular y metadatos", noticia["medio"],
                          f"«{noticia['titulo']}»", _fecha_noticia(noticia), noticia["url"]])
    for contexto in vista["contexto"]:
        if contexto["tipo"] == "indicador_banco_mundial":
            contenido = (f"{contexto['nombre']}, {PAISES.get(contexto['pais'], contexto['pais'])}: "
                         f"{formatear_valor(contexto['valor'], contexto['unidad'])} ({contexto['unidad']})")
            filas.append([contexto["id_evidencia"], "Indicador oficial", f"Banco Mundial · {contexto['licencia']}",
                          contenido, f"dato anual {contexto['anio']}", contexto["fuente_url"]])
        else:
            filas.append([contexto["id_evidencia"], "Sismo oficial", "USGS",
                          f"Magnitud {contexto['magnitud']} · {contexto['lugar']}",
                          hora_panama(contexto["fecha_utc"]) or "", contexto["fuente_url"]])
    return filas


def documento(vista: dict) -> list[tuple]:
    """Nodos del documento: ("h1" | "h2" | "h3" | "p" | "cita", texto), ("lista" | "tareas", [textos]),
    ("tabla", encabezados, filas)."""
    prioridad, ficha, revision = vista["prioridad"], vista["ficha"], vista["revision"]
    contenido = ficha or vista["vista_previa"] or {}
    titulo = "[Titular no confiable: no se reproduce]" if vista["titulo_no_confiable"] else vista["titulo"]
    nodos: list[tuple] = [("h1", titulo), ("cita", f"{AVISO_BORRADOR} {prioridad['aviso']}")]

    revisor = "sin decisión registrada"
    if revision["revisor"]:
        revisor = f"{revision['revisor']} · {hora_panama(revision['fecha_utc'])}"
    generado = "sin ficha del núcleo (vista por plantilla)"
    if ficha:
        origen = ficha["generado"]
        generado = f"{origen['metodo']}" + (f" · {origen['modelo']}" if origen.get("modelo") else "")
        generado += f" · {hora_panama(origen['fecha_utc'])}"
    nodos.append(("tabla", ["Campo", "Valor"], [
        ["ID de caso", vista["id_caso"]],
        ["Modalidad", MODALIDAD.get(vista["modalidad"], vista["modalidad"])],
        ["Tema", NOMBRE_TEMA.get(vista["tema"], vista["tema"])
         + (" (asignado por el clasificador de respaldo: confirmar)" if vista["tema_por_respaldo"] else "")],
        ["Puntaje de atención", f"{prioridad['puntaje']} · nivel {prioridad['nivel']} · posición {prioridad['posicion']}"],
        ["Estado de evidencia", f"{vista['estado_evidencia']} — {vista['motivo_estado_evidencia']}"],
        ["Estado de revisión", revision["estado"]],
        ["Persona revisora", revisor],
        ["Fuentes independientes", f"{vista['fuentes_independientes']} (de {vista['n_noticias']} nota(s))"],
        ["Reglas", f"{prioridad.get('version_reglas', config.VERSION_REGLAS)} · {prioridad.get('formula', '')}"],
        ["Generación", generado],
    ]))

    nodos.append(("h2", "Puntaje desglosado"))
    nodos.append(("tabla", ["Componente", "Valor (0 a 1)", "Peso", "Aporte", "Explicación"], [
        [f"{clave} · {COMPONENTES[clave][0]}", str(c["valor"]), str(c["peso"]), str(c["aporte"]), c["explicacion"]]
        for clave, c in prioridad["componentes"].items()]))
    if prioridad.get("ajuste"):
        nodos.append(("p", f"Ajuste: {prioridad['ajuste']}"))

    nodos.append(("h2", "Fuentes"))
    nodos.append(("tabla", ["ID", "Tipo", "Fuente", "Contenido citable", "Fecha (hora de Panamá)", "Enlace"], _fuentes(vista)))

    if contenido.get("que_se_reporta"):
        nodos += [("h2", "Qué se reporta"), ("p", contenido["que_se_reporta"])]
    if ficha and ficha.get("quien_lo_reporta"):
        nodos += [("h2", "Quién lo reporta"), ("lista", ficha["quien_lo_reporta"])]

    afirmaciones = contenido.get("afirmaciones") or []
    nodos.append(("h2", "Qué está respaldado"))
    if afirmaciones:
        nodos.append(("lista", [f"{TIPO_AFIRMACION.get(a['tipo'], a['tipo'])} · {_cita_al_final(a)}" for a in afirmaciones]))
    else:
        nodos.append(("p", "Ninguna afirmación tiene respaldo utilizable en el corpus."))

    if vista["contradicciones"]:
        nodos.append(("h2", "Cifras en conflicto"))
        nodos.append(("lista", [
            f"{version['cifra']} — " + "; ".join(f"{f['medio']} [{f['id_noticia']}:titulo]" for f in version["fuentes"])
            for version in vista["contradicciones"]]))
        nodos.append(("p", "Se muestran todas las versiones. Falta verificar cuál corresponde; el sistema no elige."))

    if vista["contexto"]:
        nodos.append(("h2", "Contexto oficial"))
        nodos.append(("lista", [f"{c['id_evidencia']} — {c['advertencia']} Vínculo: {c.get('motivo_vinculo', '')}"
                                for c in vista["contexto"]]))
    elif vista.get("sin_contexto_motivo"):
        nodos += [("h2", "Contexto oficial"), ("p", vista["sin_contexto_motivo"])]

    if contenido.get("que_falta_verificar"):
        nodos += [("h2", "Qué falta verificar"), ("tareas", contenido["que_falta_verificar"])]
    if contenido.get("accion_recomendada"):
        nodos += [("h2", "Acción recomendada"), ("p", contenido["accion_recomendada"])]
    if contenido.get("preguntas_investigacion"):
        nodos += [("h2", "Preguntas de investigación"), ("lista", contenido["preguntas_investigacion"])]

    nodos.append(("h2", "Borrador · paquete editorial"))
    borrador = revision["borrador"]
    if borrador:
        if revision["borrador_corregido"]:
            nodos.append(("p", "Texto corregido por la persona revisora en: " + ", ".join(revision["campos_corregidos"]) + "."))
        nodos += [("h3", "Título propuesto"), ("p", borrador["titulo_propuesto"]),
                  ("h3", "Enfoque de interés público"), ("p", borrador["enfoque_interes_publico"]),
                  ("h3", f"Brief ({contar_palabras(borrador['brief'])} palabras; máximo {config.LIMITE_PALABRAS_BRIEF})"),
                  ("p", borrador["brief"]),
                  ("h3", f"Guion de 45 a 60 segundos ({contar_palabras(borrador['guion_45_60s'])} palabras)"),
                  ("p", borrador["guion_45_60s"]),
                  ("h3", f"Copy digital ({contar_palabras(borrador['copy_digital'])} palabras; máximo {config.LIMITE_PALABRAS_COPY})"),
                  ("p", borrador["copy_digital"])]
        if borrador.get("verificaciones_pendientes"):
            nodos += [("h3", "Verificaciones pendientes"), ("tareas", borrador["verificaciones_pendientes"])]
    else:
        nodos.append(("p", "Sin borrador: la evidencia no alcanza para redactar. El caso requiere investigación."))

    validacion = revision["validacion"]
    observaciones = [f"Bloqueo: {m}" for m in validacion["motivos_bloqueo"]] + [f"Advertencia: {a}" for a in validacion["advertencias"]]
    nodos.append(("h2", "Validación automática"))
    nodos.append(("lista", observaciones) if observaciones else ("p", "Sin observaciones: cada cifra y cada cita del borrador están en la evidencia."))

    nodos += [("h2", "Avisos"), ("lista", vista["avisos"])]

    nodos.append(("h2", "Revisión humana"))
    if revision["historial"]:
        nodos.append(("tabla", ["Fecha (hora de Panamá)", "Acción", "Estado", "Persona", "Nota"], [
            [hora_panama(r["fecha_utc"]) or "", r["accion"],
             f"{r['estado_anterior']} → {r['estado_nuevo']}" if r.get("estado_nuevo") else "sin cambio de estado",
             r["revisor"], r.get("nota") or ""] for r in revision["historial"]]))
    else:
        nodos.append(("p", f"Sin decisiones registradas. Estado asignado por el sistema: {revision['estado']}."))
    if revision["aviso_aprobacion"]:
        nodos.append(("cita", revision["aviso_aprobacion"]))
    if revision["desactualizada"]:
        nodos.append(("cita", "La ficha cambió después de la última decisión: hay que revisarla de nuevo."))
    return nodos


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------
def _celda(texto) -> str:
    return str(texto if texto is not None else "").replace("|", "\\|").replace("\n", " ")


def a_markdown(nodos: list[tuple]) -> str:
    lineas: list[str] = []
    for nodo in nodos:
        tipo = nodo[0]
        if tipo in ("h1", "h2", "h3"):
            lineas += [f"{'#' * int(tipo[1])} {nodo[1]}", ""]
        elif tipo == "p":
            lineas += [nodo[1], ""]
        elif tipo == "cita":
            lineas += [f"> {nodo[1]}", ""]
        elif tipo == "lista":
            lineas += [f"- {item}" for item in nodo[1]] + [""]
        elif tipo == "tareas":
            lineas += [f"- [ ] {item}" for item in nodo[1]] + [""]
        elif tipo == "tabla":
            encabezados, filas = nodo[1], nodo[2]
            lineas.append("| " + " | ".join(_celda(e) for e in encabezados) + " |")
            lineas.append("|" + "---|" * len(encabezados))
            lineas += ["| " + " | ".join(_celda(c) for c in fila) + " |" for fila in filas]
            lineas.append("")
    return "\n".join(lineas).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Notion
# ---------------------------------------------------------------------------
def _texto_notion(texto) -> list[dict]:
    texto = str(texto if texto is not None else "")
    trozos = [texto[i:i + LIMITE_TEXTO_NOTION] for i in range(0, len(texto), LIMITE_TEXTO_NOTION)] or [""]
    return [{"type": "text", "text": {"content": trozo}} for trozo in trozos]


def _bloque(tipo: str, texto, **extra) -> dict:
    return {"object": "block", "type": tipo, tipo: {"rich_text": _texto_notion(texto), **extra}}


def a_bloques_notion(nodos: list[tuple]) -> list[dict]:
    equivalencia = {"h1": "heading_1", "h2": "heading_2", "h3": "heading_3", "p": "paragraph", "cita": "quote"}
    bloques: list[dict] = []
    for nodo in nodos:
        tipo = nodo[0]
        if tipo in equivalencia:
            bloques.append(_bloque(equivalencia[tipo], nodo[1]))
        elif tipo == "lista":
            bloques += [_bloque("bulleted_list_item", item) for item in nodo[1]]
        elif tipo == "tareas":
            bloques += [_bloque("to_do", item, checked=False) for item in nodo[1]]
        elif tipo == "tabla":
            encabezados, filas = nodo[1], nodo[2]
            bloques.append({"object": "block", "type": "table", "table": {
                "table_width": len(encabezados), "has_column_header": True, "has_row_header": False,
                "children": [{"object": "block", "type": "table_row",
                              "table_row": {"cells": [_texto_notion(celda) for celda in fila]}}
                             for fila in [encabezados] + filas],
            }})
    return bloques


def propiedades(vista: dict) -> dict:
    """Valores del caso para las columnas de la base «Casos y evidencias»."""
    prioridad, revision = vista["prioridad"], vista["revision"]
    return {
        "titulo": "[Titular no confiable]" if vista["titulo_no_confiable"] else vista["titulo"],
        "ID de caso": vista["id_caso"],
        "Tema": NOMBRE_TEMA.get(vista["tema"], vista["tema"]),
        "Puntaje": prioridad["puntaje"],
        "Nivel": prioridad["nivel"],
        "Posición": prioridad["posicion"],
        "Estado de evidencia": vista["estado_evidencia"],
        "Estado de revisión": revision["estado"],
        "Persona revisora": revision["revisor"] or "",
        "Fuentes independientes": vista["fuentes_independientes"],
        "Versión de reglas": prioridad.get("version_reglas", config.VERSION_REGLAS),
    }
