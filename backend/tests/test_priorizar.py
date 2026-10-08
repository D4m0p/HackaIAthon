"""
Pruebas de la etapa 4 (Priorizar) con datos sintéticos.
"""

from pathlib import Path

import pytest

from nucleo import config
from nucleo.contextualizar import cargar_indicadores, cargar_sismos, contextualizar
from nucleo.organizar import cargar_noticias, organizar
from nucleo.priorizar import priorizar

DATOS = Path(__file__).parent.parent / "datos_ejemplo"
FECHA_CORTE = "2025-09-30T00:00:00Z"


@pytest.fixture(scope="module")
def eventos():
    eventos = organizar(cargar_noticias(DATOS / "noticias_ejemplo.csv"), usar_llm=False, usar_artefactos=False)
    contextualizar(eventos,
                   cargar_indicadores(DATOS / "indicadores_ejemplo.csv"),
                   cargar_sismos(DATOS / "eventos_ejemplo.geojson"))
    return priorizar(eventos, FECHA_CORTE)


def evento_de(eventos, id_noticia):
    return next(e for e in eventos if id_noticia in e["ids_noticias"])


def test_puntaje_es_la_suma_de_los_componentes(eventos):
    for e in eventos:
        p = e["prioridad"]
        suma = sum(config.PESOS[k] * c["valor"] for k, c in p["componentes"].items())
        assert abs(p["puntaje_formula"] - suma) < 0.2
        assert 0 <= p["puntaje"] <= 100
        # Si no hay ajuste explícito, el puntaje final es exactamente el de la fórmula
        if p["ajuste"] is None:
            assert p["puntaje"] == p["puntaje_formula"]


def test_niveles_sin_solapamiento(eventos):
    for e in eventos:
        p = e["prioridad"]["puntaje"]
        esperado = "alto" if p >= 70 else "medio" if p >= 40 else "bajo"
        assert e["prioridad"]["nivel"] == esperado


def test_orden_por_puntaje_y_desempate(eventos):
    clave = [(-e["prioridad"]["puntaje"], -e["prioridad"]["componentes"]["U"]["valor"], e["id_evento"])
             for e in eventos]
    assert clave == sorted(clave)
    assert [e["prioridad"]["posicion"] for e in eventos] == list(range(1, len(eventos) + 1))


def test_T08_prioridad_expone_regla_y_no_habilita_publicacion(eventos):
    p = eventos[0]["prioridad"]
    assert p["formula"] == "P = 30R + 25I + 20U + 15N + 10E"
    assert p["version_reglas"] == config.VERSION_REGLAS
    assert all(c["explicacion"] for c in p["componentes"].values())
    assert "no confirma" in p["aviso"] and "publicación" in p["aviso"]


def test_duplicar_no_aumenta_el_puntaje(eventos):
    # El evento del Canal tiene 3 noticias pero 2 fuentes: E se calcula con 2, no con 3
    canal = evento_de(eventos, "SIN-001")
    assert canal["n_noticias"] == 3
    assert "2 fuente(s)" in canal["prioridad"]["componentes"]["E"]["explicacion"]


def test_noticia_recirculada_no_es_novedad_ni_urgente(eventos):
    vieja = evento_de(eventos, "SIN-016")
    comp = vieja["prioridad"]["componentes"]
    assert comp["N"]["valor"] == 0 and "recirculada" in comp["N"]["explicacion"]
    assert comp["U"]["valor"] == 0
    # Regla explícita: nunca pasa de "bajo", y el ajuste queda explicado
    assert vieja["prioridad"]["nivel"] == "bajo"
    assert "recirculada" in vieja["prioridad"]["ajuste"]


def test_tema_otro_tiene_relevancia_cero(eventos):
    futbol = evento_de(eventos, "SIN-015")
    futbol["tema"] = "otro"  # sin LLM el respaldo lo clasifica mal; aquí se prueba la regla
    from nucleo.priorizar import relevancia
    assert relevancia(futbol)[0] == 0


def test_estado_de_evidencia_independiente_del_puntaje(eventos):
    assert evento_de(eventos, "SIN-006")["estado_evidencia"] == "suficiente para el borrador"
    assert evento_de(eventos, "SIN-010")["estado_evidencia"] == "insuficiente"
    # Desempleo: 2 fuentes y dato oficial, pero cifras contradictorias -> solo parcial
    desempleo = evento_de(eventos, "SIN-018")
    assert desempleo["estado_evidencia"] == "parcial"
    assert {c["cifra"] for c in desempleo["posibles_contradicciones"]} == {"9.5%", "7.4%"}


def test_aviso_solo_titular(eventos):
    assert all(e["aviso_alcance"] == "Basado únicamente en titular/metadatos." for e in eventos)


def test_titular_con_inyeccion_no_obtiene_prioridad_alta(eventos):
    # SIN-017 pide "prioridad 100": el puntaje sale solo de las reglas
    assert evento_de(eventos, "SIN-017")["prioridad"]["nivel"] == "bajo"
