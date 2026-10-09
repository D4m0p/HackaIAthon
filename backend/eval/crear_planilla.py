"""
Crea la planilla para etiquetar a mano y medir el núcleo con datos reales.

    cd backend && python -m eval.crear_planilla

Hojas (sección 9.1 del reto):
- Etiquetas:    100 titulares sorteados -> macro-F1 de temas (LLM vs. embeddings vs.
                palabras clave) y exactitud de la relación con Panamá.
- Agenda:       los 15 primeros eventos del ranking, mezclados -> Precision@5 y @10.
- Pares:        pares de noticias que el sistema juntó y pares parecidos que separó,
                mezclados -> precisión y recall de la agrupación.
- Afirmaciones: afirmaciones de las fichas y oraciones citadas de los borradores, con
                lo que citan -> validez de sustento (meta 90 %, mínimo 30 revisadas).

Reglas para que la medición valga:
- Etiquetas, Agenda y Pares NO muestran lo que decidió el sistema (a ciegas).
- Todo se sortea con semilla fija: se puede regenerar igual.
- Idealmente dos personas etiquetan por separado, cada una en su copia; así se mide
  también cuánto coinciden entre ellas.
Las respuestas se procesan con: python -m eval.metricas
"""

import json
import random
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from nucleo import config, seguridad
from nucleo.fichas import paquete_evidencia
from nucleo.organizar import embeber, filtrar_por_idioma
from nucleo.pipeline import cargar_desde_paquete

CARPETA = Path(__file__).parent
DATOS = CARPETA.parent.parent / "datos"
ARTEFACTOS = CARPETA.parent / config.CARPETA_ARTEFACTOS
SALIDA = CARPETA / "planilla_etiquetas.xlsx"
TAMANO_MUESTRA = 100
SEMILLA = 42
TOP_AGENDA = 15
PARES_JUNTOS = 20
PARES_SEPARADOS = 20
SIMILITUD_PAR_SEPARADO = 0.60  # pares que el sistema separó pero que se parecen: los dudosos
MAXIMO_AFIRMACIONES = 50

AMARILLO = PatternFill("solid", fgColor="FFF2CC")
SI_NO = ["si", "no"]


# ---------------------------------------------------------------------------
# Hoja genérica
# ---------------------------------------------------------------------------
def _hoja(libro, nombre, columnas, filas, menus):
    """columnas: [(título, ancho, la_completa_la_persona)]; filas: listas con los valores
    fijos (las columnas a completar quedan vacías); menus: {título_columna: opciones}."""
    hoja = libro.create_sheet(nombre)
    for col, (titulo, ancho, a_completar) in enumerate(columnas, start=1):
        celda = hoja.cell(row=1, column=col, value=titulo)
        celda.font = Font(bold=True)
        if a_completar:
            celda.fill = AMARILLO
        hoja.column_dimensions[celda.column_letter].width = ancho
    hoja.freeze_panes = "A2"

    for numero, valores in enumerate(filas, start=2):
        for col, valor in enumerate(valores, start=1):
            hoja.cell(row=numero, column=col, value=valor).alignment = Alignment(wrap_text=True, vertical="top")
        for col in range(len(valores) + 1, len(columnas) + 1):
            hoja.cell(row=numero, column=col).fill = AMARILLO

    ultima = len(filas) + 1
    for titulo, opciones in menus.items():
        letra = hoja.cell(row=1, column=[c[0] for c in columnas].index(titulo) + 1).column_letter
        menu = DataValidation(type="list", formula1='"' + ",".join(opciones) + '"', allow_blank=True,
                              showErrorMessage=True, errorTitle="Valor no válido",
                              error="Elija una opción del menú desplegable.")
        hoja.add_data_validation(menu)
        menu.add(f"{letra}2:{letra}{ultima}")
    return hoja


def _instrucciones(hoja):
    texto = [
        ("Planilla de etiquetado · núcleo de IA", True),
        ("", False),
        ("Para qué sirve: medir con datos reales si el sistema acierta. Sus respuestas son la referencia "
         "contra la que se compara. Complete las columnas amarillas con los menús desplegables. Si etiquetan "
         "dos personas, cada una usa su propia copia del archivo y no se consultan entre sí.", False),
        ("", False),
        ("Hoja Etiquetas (100 titulares)", True),
        ("Lea solo el titular (no busque la nota): el sistema tampoco ve más que eso. No consulte las "
         "respuestas del sistema. Si duda entre un tema y \"otro\", elija \"otro\" y explique en notas.", False),
        ("Columna tema:", True),
        *[(f"  {t}: {d}", False) for t, d in config.DEFINICION_TEMAS.items()],
        ("Columna relacion_panama:", True),
        *[(f"  {r}: {d}", False) for r, d in config.RELACIONES_PANAMA.items()],
        ("Columna en_agenda_tvn: \"si\" si un editor de TVN debería considerarla para la agenda del día; "
         "\"no\" si no merece revisión editorial hoy.", False),
        ("", False),
        ("Hoja Agenda (15 eventos)", True),
        ("Son los casos que el sistema puso arriba, en un orden mezclado a propósito. Para cada uno: "
         "¿un editor de TVN debería considerarlo para la agenda del día? (si / no).", False),
        ("", False),
        ("Hoja Pares (30 pares de titulares)", True),
        ("¿Los dos titulares hablan del MISMO hecho concreto (no solo del mismo tema)? Ejemplo: dos notas "
         "sobre el mismo sismo = si; una sobre un sismo y otra sobre otro sismo = no.", False),
        ("", False),
        ("Hoja Afirmaciones", True),
        ("Aquí sí se muestra lo que escribió el sistema, junto con lo que cita. Juzgue SOLO si lo citado "
         "respalda la afirmación: si = la respalda completa; parcial = respalda una parte o exagera; "
         "no = no la respalda o agrega algo que no está en lo citado.", False),
    ]
    for fila, (linea, negrita) in enumerate(texto, start=1):
        celda = hoja.cell(row=fila, column=1, value=linea)
        celda.font = Font(bold=negrita, size=12 if fila == 1 else 11)
        celda.alignment = Alignment(wrap_text=True, vertical="top")
    hoja.column_dimensions["A"].width = 120


# ---------------------------------------------------------------------------
# Contenido de cada hoja
# ---------------------------------------------------------------------------
def _filas_etiquetas(noticias, tamano, semilla):
    en_panel, _ = filtrar_por_idioma(noticias)
    en_panel.sort(key=lambda n: n["id_noticia"])  # orden fijo antes de sortear
    muestra = random.Random(semilla).sample(en_panel, min(tamano, len(en_panel)))
    return [[i, n["id_noticia"], n["titulo"], n["medio"], n.get("idioma") or ""]
            for i, n in enumerate(muestra, start=1)], len(en_panel)


def _filas_agenda(eventos, semilla):
    top = sorted(eventos, key=lambda e: e["prioridad"]["posicion"])[:TOP_AGENDA]
    random.Random(semilla).shuffle(top)  # mezclados: quien etiqueta no ve el orden del sistema
    return [[i, e["id_evento"], e["titulo_representativo"], ", ".join(e["medios"]), e["n_noticias"]]
            for i, e in enumerate(top, start=1)]


def _dias(a, b):
    from datetime import datetime
    if not a or not b:
        return float("inf")
    fa, fb = (datetime.fromisoformat(x.replace("Z", "+00:00")) for x in (a, b))
    return abs((fa - fb).total_seconds()) / 86400


def _filas_pares(eventos, semilla):
    azar = random.Random(semilla)
    noticias = [(n, e["id_evento"]) for e in eventos for n in e["noticias"]]

    # Pares que el sistema juntó: uno al azar de cada evento con 2 o más noticias
    juntos = []
    for e in eventos:
        if len(e["noticias"]) >= 2:
            juntos.append(tuple(azar.sample(e["noticias"], 2)))
    juntos = azar.sample(juntos, min(PARES_JUNTOS, len(juntos)))

    # Pares parecidos que el sistema separó (cercanos en fecha): los casos dudosos
    vectores = embeber(n["titulo"] for n, _ in noticias)
    sim = vectores @ vectores.T
    separados = []
    for i in range(len(noticias)):
        for j in range(i + 1, len(noticias)):
            (a, ev_a), (b, ev_b) = noticias[i], noticias[j]
            if ev_a != ev_b and sim[i, j] >= SIMILITUD_PAR_SEPARADO and \
                    _dias(a.get("fecha"), b.get("fecha")) <= config.VENTANA_DIAS:
                separados.append((a, b))
    separados = azar.sample(separados, min(PARES_SEPARADOS, len(separados)))

    pares = juntos + separados
    azar.shuffle(pares)
    return [[i, a["id_noticia"], a["titulo"], a["medio"], b["id_noticia"], b["titulo"], b["medio"]]
            for i, (a, b) in enumerate(pares, start=1)]


def _texto_citado(citas, paquete):
    partes = []
    for cita in citas:
        id_evidencia, _, campo = cita.rpartition(":") if cita not in paquete else (cita, "", "")
        elemento = paquete.get(id_evidencia) or {}
        valor = elemento.get(campo) if campo else elemento
        partes.append(f"[{cita}] {json.dumps(valor, ensure_ascii=False)}")
    return "\n".join(partes)


def _filas_afirmaciones(eventos, fichas, semilla):
    por_id = {e["id_evento"]: e for e in eventos}
    filas, vistas = [], set()
    for ficha in fichas:
        paquete, _ = paquete_evidencia(por_id[ficha["id_evento"]])
        for a in ficha.get("afirmaciones") or []:
            citas = [f"{c['id_evidencia']}:{c['campo']}" for c in a["citas"]]
            if a["texto"] not in vistas:
                vistas.add(a["texto"])
                filas.append([ficha["id_caso"], f"afirmación ({a['tipo']})", a["texto"], _texto_citado(citas, paquete)])
        for parte in ("brief", "guion_45_60s", "copy_digital"):
            texto = (ficha.get("borrador") or {}).get(parte) or ""
            for oracion in seguridad.oraciones(texto):
                citas = seguridad.citas_en_texto(oracion)
                if citas and oracion not in vistas:
                    vistas.add(oracion)
                    filas.append([ficha["id_caso"], parte, oracion, _texto_citado(citas, paquete)])
    if len(filas) > MAXIMO_AFIRMACIONES:
        filas = random.Random(semilla).sample(filas, MAXIMO_AFIRMACIONES)
    return [[i, *f] for i, f in enumerate(filas, start=1)]


# ---------------------------------------------------------------------------
def crear(tamano=TAMANO_MUESTRA, semilla=SEMILLA, salida=SALIDA):
    noticias, *_ = cargar_desde_paquete(DATOS)
    eventos = json.loads((ARTEFACTOS / "eventos.json").read_text(encoding="utf-8"))
    fichas = [json.loads(l) for l in (ARTEFACTOS / "fichas.jsonl").read_text(encoding="utf-8").splitlines()]

    libro = Workbook()
    libro.active.title = "Instrucciones"
    _instrucciones(libro.active)

    filas, en_panel = _filas_etiquetas(noticias, tamano, semilla)
    _hoja(libro, "Etiquetas",
          [("n", 5, False), ("id_noticia", 17, False), ("titulo", 70, False), ("medio", 22, False),
           ("idioma", 7, False), ("tema", 20, True), ("relacion_panama", 17, True),
           ("en_agenda_tvn", 15, True), ("notas", 40, True)],
          filas, {"tema": list(config.DEFINICION_TEMAS), "relacion_panama": list(config.RELACIONES_PANAMA),
                  "en_agenda_tvn": SI_NO})

    agenda = _filas_agenda(eventos, semilla)
    _hoja(libro, "Agenda",
          [("n", 5, False), ("id_evento", 20, False), ("titulo", 70, False), ("medios", 30, False),
           ("noticias", 9, False), ("en_agenda_tvn", 15, True), ("notas", 40, True)],
          agenda, {"en_agenda_tvn": SI_NO})

    pares = _filas_pares(eventos, semilla)
    _hoja(libro, "Pares",
          [("n", 5, False), ("id_a", 17, False), ("titulo_a", 55, False), ("medio_a", 18, False),
           ("id_b", 17, False), ("titulo_b", 55, False), ("medio_b", 18, False),
           ("mismo_evento", 14, True), ("notas", 30, True)],
          pares, {"mismo_evento": SI_NO})

    afirmaciones = _filas_afirmaciones(eventos, fichas, semilla)
    _hoja(libro, "Afirmaciones",
          [("n", 5, False), ("id_caso", 24, False), ("origen", 18, False), ("texto", 70, False),
           ("lo_que_cita", 60, False), ("respaldada", 13, True), ("notas", 30, True)],
          afirmaciones, {"respaldada": ["si", "parcial", "no"]})

    libro.save(salida)
    return {"salida": salida, "etiquetas": len(filas), "en_panel": en_panel, "agenda": len(agenda),
            "pares": len(pares), "afirmaciones": len(afirmaciones)}


if __name__ == "__main__":
    r = crear()
    print(f"Planilla creada: {r['salida']}")
    print(f"  Etiquetas: {r['etiquetas']} titulares (de {r['en_panel']} en el panel) · Agenda: {r['agenda']} eventos · "
          f"Pares: {r['pares']} · Afirmaciones: {r['afirmaciones']} (semilla {SEMILLA})")
