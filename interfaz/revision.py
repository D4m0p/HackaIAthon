"""Etapa 7 · Revisar: decisión humana sobre cada caso y su registro.

- Los estados son los cinco del reto. Ninguno significa "publicado".
- Cada acción la firma una persona y queda en una bitácora que solo crece.
- La prioridad no habilita nada: un caso con evidencia insuficiente o con un borrador
  bloqueado por el validador no se puede aprobar, por alto que sea su puntaje.
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

from .puente import config, seguridad
from .texto import contar_palabras

from ingesta.comun import a_iso_utc, ahora_utc  # noqa: E402

NUEVO = "nuevo"
EN_REVISION = "en revisión"
REQUIERE_EVIDENCIA = "requiere evidencia"
APROBADO = "aprobado como borrador"
DESCARTADO = "descartado"
ESTADOS = (NUEVO, EN_REVISION, REQUIERE_EVIDENCIA, APROBADO, DESCARTADO)

TRANSICIONES = {
    NUEVO: (EN_REVISION, REQUIERE_EVIDENCIA, APROBADO, DESCARTADO),
    EN_REVISION: (REQUIERE_EVIDENCIA, APROBADO, DESCARTADO),
    REQUIERE_EVIDENCIA: (EN_REVISION, APROBADO, DESCARTADO),
    APROBADO: (EN_REVISION,),
    DESCARTADO: (EN_REVISION,),
}
ACCION = {
    EN_REVISION: "tomar para revisión",
    REQUIERE_EVIDENCIA: "pedir evidencia",
    APROBADO: "aprobar como borrador",
    DESCARTADO: "descartar",
}
AVISO_APROBACION = "Aprobado como borrador: no es una publicación ni confirma la noticia."
CAMPOS_BORRADOR = ("titulo_propuesto", "enfoque_interes_publico", "brief", "guion_45_60s", "copy_digital")
MINIMO_NOMBRE = 3


class ReglaDeRevision(Exception):
    """La acción pedida no está permitida; el mensaje explica por qué."""


def estado_inicial(evento: dict, ficha: dict | None) -> str:
    if ficha:
        return ficha["estado_revision"]
    return REQUIERE_EVIDENCIA if evento["estado_evidencia"] == "insuficiente" else NUEVO


def huella_de_ficha(ficha: dict | None) -> str | None:
    """Cambia si el núcleo regenera la ficha: una decisión tomada sobre otro texto se nota."""
    if not ficha:
        return None
    contenido = [ficha.get("afirmaciones"), ficha.get("borrador"), ficha.get("puntaje"),
                 ficha.get("estado_evidencia"), ficha.get("ids_fuente")]
    texto = json.dumps(contenido, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Bitácora
# ---------------------------------------------------------------------------
class Bitacora:
    """Registro de decisiones en un JSONL al que solo se le agregan líneas."""

    def __init__(self, carpeta: Path):
        self.ruta = Path(carpeta) / "bitacora.jsonl"
        self._candado = threading.Lock()
        self._registros: list[dict] = []
        if self.ruta.exists():
            for linea in self.ruta.read_text(encoding="utf-8").splitlines():
                if linea.strip():
                    self._registros.append(json.loads(linea))

    def registros(self, id_evento: str | None = None) -> list[dict]:
        with self._candado:
            return [r for r in self._registros if id_evento is None or r["id_evento"] == id_evento]

    def agregar(self, registro: dict) -> dict:
        with self._candado:
            registro = {"id_registro": len(self._registros) + 1, "fecha_utc": a_iso_utc(ahora_utc()), **registro}
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            with open(self.ruta, "a", encoding="utf-8") as archivo:
                archivo.write(json.dumps(registro, ensure_ascii=False) + "\n")
            self._registros.append(registro)
            return registro

    def vaciar(self) -> None:
        with self._candado:
            self._registros = []
            if self.ruta.exists():
                self.ruta.unlink()

    def estado(self, id_evento: str, inicial: str) -> str:
        cambios = [r for r in self.registros(id_evento) if r.get("estado_nuevo")]
        return cambios[-1]["estado_nuevo"] if cambios else inicial

    def borrador_vigente(self, id_evento: str, original: dict | None) -> dict | None:
        """El borrador del núcleo con las correcciones de la persona revisora encima."""
        if not original:
            return None
        vigente = dict(original)
        for registro in self.registros(id_evento):
            for campo, cambio in (registro.get("cambios") or {}).items():
                vigente[campo] = cambio["despues"]
        return vigente


# ---------------------------------------------------------------------------
# Validación del borrador que se va a aprobar
# ---------------------------------------------------------------------------
def validar_borrador(borrador: dict | None, evidencia: dict, contradicciones: list[dict]) -> dict:
    """Los mismos controles que el núcleo aplica a lo que redacta el LLM, sobre el
    texto vigente (que puede traer correcciones humanas)."""
    motivos, advertencias = [], []
    if not borrador:
        return {"bloqueada": False, "motivos_bloqueo": motivos, "advertencias": advertencias, "palabras": {}}

    titulo = borrador.get("titulo_propuesto") or ""
    cifras = seguridad.cifras_fuera_de_evidencia(titulo, evidencia)
    if cifras:
        motivos.append(f"Título: cifras que no están en la evidencia ({', '.join(cifras)})")
    siglas = seguridad.siglas_fuera_de_evidencia(titulo, evidencia)
    if siglas:
        motivos.append(f"Título: siglas que no están en la evidencia ({', '.join(siglas)})")

    nombres = {"brief": "Brief", "guion_45_60s": "Guion", "copy_digital": "Copy"}
    for campo, nombre in nombres.items():
        texto = borrador.get(campo) or ""
        motivos += [f"{nombre}: cita inválida [{cita}]" for cita in seguridad.citas_en_texto_invalidas(texto, evidencia)]
        motivos += [f"{nombre}: {problema}" for problema in seguridad.cifras_sin_respaldo_por_oracion(texto, evidencia)]
        siglas = seguridad.siglas_fuera_de_evidencia(texto, evidencia)
        if siglas:
            motivos.append(f"{nombre}: siglas que no están en la evidencia ({', '.join(siglas)})")
        faltan = seguridad.faltan_versiones(texto, contradicciones)
        if faltan:
            motivos.append(f"{nombre}: no muestra todas las cifras en conflicto (falta {', '.join(faltan)})")

    palabras = {campo: contar_palabras(borrador.get(campo)) for campo in nombres}
    minimo, maximo = config.RANGO_PALABRAS_GUION
    if palabras["brief"] > config.LIMITE_PALABRAS_BRIEF:
        advertencias.append(f"El brief tiene {palabras['brief']} palabras (máximo {config.LIMITE_PALABRAS_BRIEF}).")
    if palabras["copy_digital"] > config.LIMITE_PALABRAS_COPY:
        advertencias.append(f"El copy tiene {palabras['copy_digital']} palabras (máximo {config.LIMITE_PALABRAS_COPY}).")
    if not minimo <= palabras["guion_45_60s"] <= maximo:
        advertencias.append(f"El guion tiene {palabras['guion_45_60s']} palabras (debe tener entre {minimo} y {maximo}).")
    return {"bloqueada": bool(motivos), "motivos_bloqueo": motivos, "advertencias": advertencias,
            "palabras": palabras}


# ---------------------------------------------------------------------------
# Reglas
# ---------------------------------------------------------------------------
def _impedimento_para_aprobar(evento: dict, ficha: dict | None, borrador: dict | None, validacion: dict) -> str | None:
    prioridad = evento["prioridad"]
    if evento["estado_evidencia"] == "insuficiente":
        return (f"La evidencia es insuficiente ({evento['motivo_estado_evidencia']}). "
                f"El puntaje de {prioridad['puntaje']} (nivel {prioridad['nivel']}) ordena la revisión, "
                "pero no habilita aprobar ni publicar: primero hay que investigar.")
    if not ficha:
        return "Este caso todavía no tiene ficha: no hay nada que aprobar."
    if not borrador:
        return "La ficha no tiene borrador: no hay nada que aprobar."
    if validacion["bloqueada"]:
        return ("El borrador tiene contenido sin respaldo en la evidencia; hay que corregirlo antes: "
                + "; ".join(validacion["motivos_bloqueo"][:3]))
    return None


def _exige_nota(evento: dict, estado_nuevo: str, estado_actual: str) -> str | None:
    """Motivo por el que la persona revisora debe dejar una nota, o None."""
    if estado_nuevo == DESCARTADO:
        return "Indique por qué se descarta."
    if estado_actual in (APROBADO, DESCARTADO):
        return "Indique por qué se reabre el caso."
    if estado_nuevo == APROBADO and evento["posibles_contradicciones"]:
        return "Hay cifras en conflicto: indique cómo se verificó cuál corresponde."
    if estado_nuevo == APROBADO and evento["estado_evidencia"] != "suficiente para el borrador":
        return "La evidencia es parcial: indique qué se verificó antes de aprobar."
    return None


def acciones(evento: dict, ficha: dict | None, estado_actual: str, borrador: dict | None, validacion: dict) -> list[dict]:
    """Los estados a los que se puede pasar, con el motivo cuando uno está cerrado."""
    posibles = []
    for destino in TRANSICIONES[estado_actual]:
        impedimento = _impedimento_para_aprobar(evento, ficha, borrador, validacion) if destino == APROBADO else None
        posibles.append({
            "estado": destino,
            "accion": "reabrir" if estado_actual in (APROBADO, DESCARTADO) else ACCION[destino],
            "permitido": impedimento is None,
            "impedimento": impedimento,
            "nota_obligatoria": _exige_nota(evento, destino, estado_actual),
        })
    return posibles


def _revisor(nombre: str | None) -> str:
    nombre = " ".join((nombre or "").split())
    if len(nombre) < MINIMO_NOMBRE:
        raise ReglaDeRevision("Falta el nombre de la persona responsable de la revisión.")
    return nombre[:80]


def _foto(evento: dict, ficha: dict | None) -> dict:
    prioridad = evento["prioridad"]
    return {
        "id_caso": f"CASO-{evento['id_evento']}",
        "id_evento": evento["id_evento"],
        "puntaje": prioridad["puntaje"],
        "nivel": prioridad["nivel"],
        "estado_evidencia": evento["estado_evidencia"],
        "version_reglas": prioridad.get("version_reglas", config.VERSION_REGLAS),
        "huella_ficha": huella_de_ficha(ficha),
    }


def cambiar_estado(bitacora: Bitacora, evento: dict, ficha: dict | None, evidencia: dict,
                   estado_nuevo: str, revisor: str | None, nota: str | None = None) -> dict:
    revisor = _revisor(revisor)
    nota = (nota or "").strip()
    actual = bitacora.estado(evento["id_evento"], estado_inicial(evento, ficha))
    if estado_nuevo not in ESTADOS:
        raise ReglaDeRevision(f"«{estado_nuevo}» no es un estado de revisión. No existe un estado para publicar.")
    if estado_nuevo not in TRANSICIONES[actual]:
        raise ReglaDeRevision(f"Un caso «{actual}» no puede pasar a «{estado_nuevo}».")

    borrador = bitacora.borrador_vigente(evento["id_evento"], (ficha or {}).get("borrador"))
    validacion = validar_borrador(borrador, evidencia, evento["posibles_contradicciones"])
    if estado_nuevo == APROBADO:
        impedimento = _impedimento_para_aprobar(evento, ficha, borrador, validacion)
        if impedimento:
            raise ReglaDeRevision(impedimento)
    exigencia = _exige_nota(evento, estado_nuevo, actual)
    if exigencia and len(nota) < 10:
        raise ReglaDeRevision(f"Falta la nota de la persona revisora. {exigencia}")

    registro = {
        **_foto(evento, ficha),
        "accion": "reabrir" if actual in (APROBADO, DESCARTADO) else ACCION[estado_nuevo],
        "estado_anterior": actual,
        "estado_nuevo": estado_nuevo,
        "revisor": revisor,
        "nota": nota or None,
    }
    if estado_nuevo == APROBADO:
        registro["aviso"] = AVISO_APROBACION
    return bitacora.agregar(registro)


def corregir_borrador(bitacora: Bitacora, evento: dict, ficha: dict | None, evidencia: dict,
                      cambios: dict, revisor: str | None, nota: str | None = None) -> dict:
    """Guarda la corrección humana del borrador. Un caso nuevo pasa a «en revisión»;
    uno ya aprobado vuelve a revisión, porque lo aprobado era otro texto."""
    revisor = _revisor(revisor)
    if not ficha or not ficha.get("borrador"):
        raise ReglaDeRevision("Este caso no tiene un borrador que corregir.")
    vigente = bitacora.borrador_vigente(evento["id_evento"], ficha["borrador"])
    diferencias = {}
    for campo, texto in (cambios or {}).items():
        if campo not in CAMPOS_BORRADOR:
            raise ReglaDeRevision(f"«{campo}» no es una parte editable del borrador.")
        texto = (texto or "").strip()
        if texto != (vigente.get(campo) or "").strip():
            diferencias[campo] = {"antes": vigente.get(campo), "despues": texto}
    if not diferencias:
        raise ReglaDeRevision("El texto es igual al vigente: no hay nada que guardar.")

    actual = bitacora.estado(evento["id_evento"], estado_inicial(evento, ficha))
    nuevo = EN_REVISION if actual in (NUEVO, APROBADO) else actual
    corregido = {**vigente, **{campo: cambio["despues"] for campo, cambio in diferencias.items()}}
    registro = {
        **_foto(evento, ficha),
        "accion": "corregir borrador",
        "estado_anterior": actual,
        "estado_nuevo": nuevo if nuevo != actual else None,
        "revisor": revisor,
        "nota": (nota or "").strip() or None,
        "cambios": diferencias,
        "validacion": validar_borrador(corregido, evidencia, evento["posibles_contradicciones"]),
    }
    return bitacora.agregar(registro)


def anotar(bitacora: Bitacora, evento: dict, ficha: dict | None, accion: str,
           revisor: str | None, detalle: dict | None = None) -> dict:
    """Deja constancia de algo que no cambia el estado (por ejemplo, el envío a Notion)."""
    return bitacora.agregar({**_foto(evento, ficha), "accion": accion, "estado_anterior": None,
                             "estado_nuevo": None, "revisor": _revisor(revisor), "nota": None, **(detalle or {})})


# ---------------------------------------------------------------------------
# Vista de la revisión de un caso
# ---------------------------------------------------------------------------
def resumen(bitacora: Bitacora, evento: dict, ficha: dict | None, evidencia: dict) -> dict:
    id_evento = evento["id_evento"]
    historial = bitacora.registros(id_evento)
    estado = bitacora.estado(id_evento, estado_inicial(evento, ficha))
    original = (ficha or {}).get("borrador")
    borrador = bitacora.borrador_vigente(id_evento, original)
    validacion = validar_borrador(borrador, evidencia, evento["posibles_contradicciones"])
    decisiones = [r for r in historial if r.get("estado_nuevo")]
    ultima = decisiones[-1] if decisiones else None
    huella = huella_de_ficha(ficha)
    return {
        "estado": estado,
        "estado_inicial": estado_inicial(evento, ficha),
        "revisor": ultima["revisor"] if ultima else None,
        "fecha_utc": ultima["fecha_utc"] if ultima else None,
        "nota": ultima["nota"] if ultima else None,
        "historial": historial,
        "acciones": acciones(evento, ficha, estado, borrador, validacion),
        "borrador": borrador,
        "borrador_corregido": bool(original) and borrador != original,
        "campos_corregidos": [c for c in CAMPOS_BORRADOR if original and borrador.get(c) != original.get(c)],
        "validacion": validacion,
        # La decisión se tomó sobre una versión de la ficha que el núcleo ya reemplazó
        "desactualizada": bool(ultima and huella and ultima.get("huella_ficha") not in (None, huella)),
        "aviso_aprobacion": AVISO_APROBACION if estado == APROBADO else None,
    }


def ficha_revisada(bitacora: Bitacora, evento: dict, ficha: dict, evidencia: dict) -> dict:
    """La ficha en el formato del contrato de datos, con la decisión humana incorporada."""
    vista = resumen(bitacora, evento, ficha, evidencia)
    salida = dict(ficha)
    salida["estado_revision"] = vista["estado"]
    if vista["borrador_corregido"]:
        salida["borrador_original"] = ficha["borrador"]
        salida["borrador"] = vista["borrador"]
    salida["revision"] = {
        "persona_revisora": vista["revisor"],
        "fecha_utc": vista["fecha_utc"],
        "nota": vista["nota"],
        "desactualizada": vista["desactualizada"],
        "validacion_borrador": {k: vista["validacion"][k] for k in ("bloqueada", "motivos_bloqueo", "advertencias")},
        "historial": [{k: r.get(k) for k in ("fecha_utc", "accion", "estado_anterior", "estado_nuevo",
                                             "revisor", "nota")} for r in vista["historial"]],
    }
    return salida
