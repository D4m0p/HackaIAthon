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
    eventos = organizar(cargar_noticias(DATOS / "noticias_ejemplo.csv"), usar_llm=False)
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
    ficha = generar_ficha(eventos["EV-SIN-001"], usar_llm=False)
    assert ficha["id_caso"] == "CASO-EV-SIN-001" and ficha["modalidad"] == "editorial_tvn"
    assert ficha["fuentes_independientes"] == 2
    assert "cuentan como 1 procedencia" in ficha["quien_lo_reporta"][0]
    assert ficha["borrador"] is None and ficha["afirmaciones"] == []
    assert "Basado únicamente en titular/metadatos." in ficha["avisos"]


def test_caso_insuficiente_requiere_evidencia(eventos):
    ficha = generar_ficha(eventos["EV-SIN-010"], usar_llm=False)
    assert ficha["estado_evidencia"] == "insuficiente"
    assert ficha["estado_revision"] == "requiere evidencia"


def test_T07_titular_con_inyeccion_no_llega_al_llm(eventos):
    ficha = generar_ficha(eventos["EV-SIN-017"])  # aunque se permita el LLM
    assert [s["id_noticia"] for s in ficha["contenido_sospechoso"]] == ["SIN-017"]
    assert "SIN-017" not in ficha["ids_fuente"]
    assert ficha["generado"]["metodo"] == "sin_evidencia_utilizable"
    assert ficha["borrador"] is None


# ---------------------------------------------------------------------------
# Con LLM
# ---------------------------------------------------------------------------
def test_T09_todas_las_afirmaciones_tienen_cita_valida(fichas_llm):
    for ficha in fichas_llm.values():
        assert ficha["afirmaciones"], ficha["id_caso"]
        assert ficha["alertas_validacion"]["afirmaciones_descartadas"] == [], ficha["id_caso"]
        assert ficha["alertas_validacion"]["citas_invalidas_borrador"] == [], ficha["id_caso"]


def test_T09_paquete_editorial_completo_y_dentro_de_limites(fichas_llm):
    ficha = fichas_llm["EV-SIN-004"]
    b = ficha["borrador"]
    assert all(b[k] for k in ["titulo_propuesto", "enfoque_interes_publico", "brief",
                              "guion_45_60s", "copy_digital"])
    assert len(ficha["preguntas_investigacion"]) == 3
    assert ficha["alertas_validacion"]["limites"] == []
    assert b["brief"].startswith("Basado únicamente en titular/metadatos.")
    assert ficha["alertas_validacion"]["cifras_no_respaldadas"] == []


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
