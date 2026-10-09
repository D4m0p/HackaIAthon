"""T09 · Brief editorial.

Esperado: formato útil, citas pertinentes y distinción de hechos e inferencias.
"""

import re

import pytest
from .apoyo import REVISORA, caso_con

from interfaz import revision
from interfaz.puente import config, seguridad
from interfaz.texto import contar_palabras

TIPOS = {"hecho", "declaracion", "inferencia", "hipotesis"}


@pytest.fixture
def con_borrador(aplicacion):
    fila = caso_con(aplicacion, tiene_borrador=True, estado_evidencia="suficiente para el borrador")
    return aplicacion.caso(fila["id_evento"])


def test_el_paquete_editorial_trae_todas_sus_piezas_dentro_de_los_limites(con_borrador):
    borrador = con_borrador["revision"]["borrador"]

    for pieza in ("titulo_propuesto", "enfoque_interes_publico", "brief", "guion_45_60s", "copy_digital"):
        assert borrador[pieza].strip(), pieza
    assert contar_palabras(borrador["brief"]) <= config.LIMITE_PALABRAS_BRIEF
    assert contar_palabras(borrador["copy_digital"]) <= config.LIMITE_PALABRAS_COPY
    assert len(con_borrador["ficha"]["preguntas_investigacion"]) == 3
    assert con_borrador["ficha"]["que_falta_verificar"]


def test_cada_afirmacion_de_cada_ficha_cita_evidencia_que_existe(aplicacion):
    """Cobertura de citas: el 100 % de las afirmaciones enlaza un elemento y un campo reales."""
    total = 0
    for fila in aplicacion.bandeja():
        vista = aplicacion.caso(fila["id_evento"])
        for afirmacion in (vista["ficha"] or {}).get("afirmaciones", []):
            total += 1
            assert afirmacion["tipo"] in TIPOS
            assert afirmacion["citas"], afirmacion["texto"]
            for cita in afirmacion["citas"]:
                assert cita["campo"] in vista["evidencia"][cita["id_evidencia"]], cita
    assert total >= 10


def test_las_citas_escritas_en_el_borrador_apuntan_a_la_evidencia_del_caso(con_borrador):
    borrador, evidencia = con_borrador["revision"]["borrador"], con_borrador["evidencia"]

    for pieza in ("brief", "guion_45_60s", "copy_digital"):
        assert seguridad.citas_en_texto(borrador[pieza]), f"{pieza} no tiene citas"
        assert seguridad.citas_en_texto_invalidas(borrador[pieza], evidencia) == []
        assert seguridad.cifras_sin_respaldo_por_oracion(borrador[pieza], evidencia) == []
    assert con_borrador["revision"]["validacion"]["bloqueada"] is False


def test_el_brief_dice_que_solo_se_conoce_el_titular(con_borrador):
    assert con_borrador["revision"]["borrador"]["brief"].startswith("Basado únicamente en titular/metadatos.")
    assert "Basado únicamente en titular/metadatos." in con_borrador["avisos"]


def test_el_documento_para_notion_distingue_hechos_de_declaraciones(aplicacion, con_borrador):
    markdown = aplicacion.markdown(con_borrador["id_evento"])
    respaldo = markdown.split("## Qué está respaldado")[1].split("\n## ")[0]

    assert re.search(r"^- Hecho · .+\[.+:.+\]", respaldo, re.M)
    assert re.search(r"^- Declaración · .+\[.+:titulo\]", respaldo, re.M)
    for seccion in ("Puntaje desglosado", "Fuentes", "Qué falta verificar", "Preguntas de investigación",
                    "Borrador · paquete editorial", "Título propuesto", "Brief (", "Guion de 45 a 60 segundos",
                    "Copy digital (", "Validación automática", "Revisión humana"):
        assert seccion in markdown, seccion
    assert con_borrador["id_caso"] in markdown and "reglas-v1" in markdown


def test_un_caso_sin_evidencia_suficiente_no_tiene_borrador_y_lo_dice(aplicacion):
    fila = caso_con(aplicacion, estado_evidencia="insuficiente", tiene_ficha=True)
    vista = aplicacion.caso(fila["id_evento"])

    assert vista["revision"]["borrador"] is None
    assert len(vista["ficha"]["preguntas_investigacion"]) == 3
    assert "Sin borrador: la evidencia no alcanza para redactar" in aplicacion.markdown(fila["id_evento"])


def test_una_correccion_con_una_cifra_sin_respaldo_bloquea_la_aprobacion(aplicacion, con_borrador):
    id_evento = con_borrador["id_evento"]
    brief = con_borrador["revision"]["borrador"]["brief"]

    vista = aplicacion.corregir(id_evento, {"brief": brief + " Hubo 250 heridos."}, REVISORA, "Agrego un dato.")
    assert vista["revision"]["validacion"]["bloqueada"] is True
    assert any("250" in motivo for motivo in vista["revision"]["validacion"]["motivos_bloqueo"])
    with pytest.raises(revision.ReglaDeRevision, match="sin respaldo en la evidencia"):
        aplicacion.cambiar_estado(id_evento, revision.APROBADO, REVISORA, None)

    vista = aplicacion.corregir(id_evento, {"brief": brief}, REVISORA, "Retiro el dato sin fuente.")
    assert vista["revision"]["validacion"]["bloqueada"] is False
    assert aplicacion.cambiar_estado(id_evento, revision.APROBADO, REVISORA, None)["revision"]["estado"] == revision.APROBADO


def test_una_correccion_valida_queda_registrada_y_conserva_el_texto_original(aplicacion, con_borrador):
    id_evento = con_borrador["id_evento"]
    original = con_borrador["revision"]["borrador"]["titulo_propuesto"]

    vista = aplicacion.corregir(id_evento, {"titulo_propuesto": "Sismo en Chiriquí: lo que se sabe"}, REVISORA, None)

    assert vista["revision"]["borrador"]["titulo_propuesto"] == "Sismo en Chiriquí: lo que se sabe"
    assert vista["revision"]["campos_corregidos"] == ["titulo_propuesto"]
    assert vista["ficha"]["borrador"]["titulo_propuesto"] == original
    assert vista["revision"]["estado"] == revision.EN_REVISION
    registro = aplicacion.bitacora.registros(id_evento)[-1]
    assert registro["cambios"]["titulo_propuesto"] == {"antes": original, "despues": "Sismo en Chiriquí: lo que se sabe"}

    exportada = next(f for f in aplicacion.fichas_revisadas() if f["id_evento"] == id_evento)
    assert exportada["borrador"]["titulo_propuesto"] == "Sismo en Chiriquí: lo que se sabe"
    assert exportada["borrador_original"]["titulo_propuesto"] == original
    assert exportada["revision"]["persona_revisora"] == REVISORA
