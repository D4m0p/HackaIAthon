"""
Pruebas de las etapas 5 y 6 (fichas y borradores).

Las pruebas "sin_llm" revisan lo que arma el código y corren sin internet.
Las pruebas "con_llm" llaman a Gemini (o usan la caché) y se saltan si no hay clave.
"""

import os
import re
from pathlib import Path

import pytest

from nucleo.contextualizar import cargar_indicadores, cargar_sismos, contextualizar
from nucleo.fichas import generar_ficha
from nucleo.organizar import cargar_noticias, organizar
from nucleo.priorizar import priorizar

DATOS = Path(__file__).parent.parent / "datos_ejemplo"


@pytest.fixture(scope="module")
def eventos():
    eventos = organizar(cargar_noticias(DATOS / "noticias_ejemplo.csv"), usar_llm=False, usar_artefactos=False)
    contextualizar(eventos,
                   cargar_indicadores(DATOS / "indicadores_ejemplo.csv"),
                   cargar_sismos(DATOS / "eventos_ejemplo.geojson"))
    return {e["id_evento"]: e for e in priorizar(eventos, "2025-09-30T00:00:00Z")}


@pytest.fixture(scope="module")
def fichas_llm(eventos):
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("sin GEMINI_API_KEY")
    fichas = {i: generar_ficha(eventos[i]) for i in ["EV-SIN-004", "EV-SIN-018", "EV-SIN-010"]}
    if any(f["generado"]["metodo"] != "llm" for f in fichas.values()):
        pytest.skip("Gemini no respondió (sin conexión o saturado)")
    return fichas


# ---------------------------------------------------------------------------
# Sin LLM
# ---------------------------------------------------------------------------
def test_ficha_sin_llm_tiene_datos_verificables(eventos):
    ficha = generar_ficha(eventos["EV-SIN-001"], usar_llm=False, usar_artefactos=False)
    assert ficha["id_caso"] == "CASO-EV-SIN-001" and ficha["modalidad"] == "editorial_tvn"
    assert ficha["fuentes_independientes"] == 2
    assert "cuentan como 1 procedencia" in ficha["quien_lo_reporta"][0]
    assert "Basado únicamente en titular/metadatos." in ficha["avisos"]


def test_sin_llm_la_ficha_se_arma_por_plantilla_sin_inventar(eventos):
    for id_evento in ["EV-SIN-001", "EV-SIN-004", "EV-SIN-006", "EV-SIN-018"]:
        ficha = generar_ficha(eventos[id_evento], usar_llm=False, usar_artefactos=False)
        assert ficha["generado"]["metodo"] == "plantilla", id_evento
        assert ficha["borrador"] is not None, id_evento
        assert ficha["borrador"]["brief"].startswith("Basado únicamente en titular/metadatos."), id_evento
        # La plantilla solo repite lo citable: nunca debe quedar bloqueada
        assert ficha["validacion"]["bloqueada"] is False, (id_evento, ficha["validacion"]["motivos_bloqueo"])
        assert ficha["validacion"]["afirmaciones_descartadas"] == [], id_evento
        assert len(ficha["preguntas_investigacion"]) == 3


def test_plantilla_con_contradiccion_muestra_ambas_cifras(eventos):
    brief = generar_ficha(eventos["EV-SIN-018"], usar_llm=False, usar_artefactos=False)["borrador"]["brief"]
    assert "9.5%" in brief and "7.4%" in brief


def test_caso_insuficiente_requiere_evidencia(eventos):
    ficha = generar_ficha(eventos["EV-SIN-010"], usar_llm=False, usar_artefactos=False)
    assert ficha["estado_evidencia"] == "insuficiente"
    assert ficha["estado_revision"] == "requiere evidencia"
    assert ficha["borrador"] is None and len(ficha["preguntas_investigacion"]) == 3


def test_T07_titular_con_inyeccion_no_llega_al_llm(eventos):
    ficha = generar_ficha(eventos["EV-SIN-017"])  # aunque se permita el LLM
    assert [s["id_noticia"] for s in ficha["contenido_sospechoso"]] == ["SIN-017"]
    assert "SIN-017" not in ficha["ids_fuente"]
    assert ficha["generado"]["metodo"] == "sin_evidencia_utilizable"
    assert ficha["borrador"] is None


# ---------------------------------------------------------------------------
# Con LLM
# ---------------------------------------------------------------------------
def test_T09_afirmaciones_citadas_y_bloqueo_si_falta_respaldo(fichas_llm):
    for ficha in fichas_llm.values():
        assert ficha["afirmaciones"], ficha["id_caso"]
        # Las afirmaciones que quedan en la ficha tienen todas una cita válida
        assert all(a["citas"] for a in ficha["afirmaciones"]), ficha["id_caso"]
        # Garantía del sistema: si el validador encuentra algo sin respaldo, la ficha NO
        # puede quedar como "nuevo"; pasa a "requiere evidencia" con sus motivos
        if ficha["validacion"]["bloqueada"]:
            assert ficha["estado_revision"] == "requiere evidencia", ficha["id_caso"]
            assert ficha["validacion"]["motivos_bloqueo"], ficha["id_caso"]


def test_T09_paquete_editorial_completo_y_dentro_de_limites(fichas_llm):
    ficha = fichas_llm["EV-SIN-004"]
    b = ficha["borrador"]
    assert all(b[k] for k in ["titulo_propuesto", "enfoque_interes_publico", "brief",
                              "guion_45_60s", "copy_digital"])
    assert len(ficha["preguntas_investigacion"]) == 3
    assert not any("palabras" in a for a in ficha["validacion"]["advertencias"])
    assert b["brief"].startswith("Basado únicamente en titular/metadatos.")


def test_T05_contradiccion_muestra_ambas_versiones(fichas_llm):
    brief = fichas_llm["EV-SIN-018"]["borrador"]["brief"]
    assert "9.5" in brief and "7.4" in brief


def test_insuficiente_no_genera_borrador(fichas_llm):
    ficha = fichas_llm["EV-SIN-010"]
    assert ficha["borrador"] is None
    assert len(ficha["preguntas_investigacion"]) == 3


def test_no_inventa_acciones_de_la_redaccion(fichas_llm):
    for ficha in fichas_llm.values():
        if ficha["borrador"]:
            texto = " ".join(ficha["borrador"][k] for k in ("brief", "guion_45_60s", "copy_digital"))
            assert not re.search(r"\bestamos (investigando|verificando|consultando)\b", texto.lower())
