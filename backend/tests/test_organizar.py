"""
Pruebas de la etapa 2 (Organizar) con los datos sintéticos de datos_ejemplo/.

T02: tres registros del mismo evento -> un solo evento, sin perder fuentes
     y sin triplicar la corroboración.
"""

import os
from pathlib import Path

import pytest

from nucleo import llm
from nucleo.organizar import asignar_temas, cargar_noticias, embeber, organizar

RUTA = Path(__file__).parent.parent / "datos_ejemplo" / "noticias_ejemplo.csv"

# Las pruebas de agrupación no usan el LLM: son deterministas y corren sin internet.
@pytest.fixture(scope="module")
def eventos():
    return {e["id_evento"]: e for e in organizar(cargar_noticias(RUTA), usar_llm=False)}


@pytest.fixture(scope="module")
def temas_llm():
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("sin GEMINI_API_KEY")
    noticias = cargar_noticias(RUTA)
    asignar_temas(noticias, embeber(n["titulo"] for n in noticias), usar_llm=True)
    return {n["id_noticia"]: n for n in noticias}


def evento_de(eventos, id_noticia):
    return next(e for e in eventos.values() if id_noticia in e["ids_noticias"])


def test_T02_tres_registros_un_evento(eventos):
    canal = evento_de(eventos, "SIN-001")
    # Las tres noticias quedan juntas: no se pierde ninguna fuente
    assert {"SIN-001", "SIN-002", "SIN-003"} <= set(canal["ids_noticias"])
    # SIN-001 y SIN-002 son el mismo titular (réplica) -> cuentan como una procedencia.
    # SIN-003 es una redacción distinta -> segunda procedencia. Total: 2, no 3.
    assert canal["n_fuentes_independientes"] == 2


def test_noticia_vieja_no_se_mezcla_con_evento_nuevo(eventos):
    # SIN-016 es el mismo titular pero publicado en 2024: no es el mismo evento
    assert "SIN-016" not in evento_de(eventos, "SIN-001")["ids_noticias"]


def test_no_se_mezclan_eventos_distintos(eventos):
    # Hoteles, metro y fútbol: fechas cercanas y "Panamá" en común, pero son eventos distintos
    assert evento_de(eventos, "SIN-009")["ids_noticias"] == ["SIN-009"]
    assert evento_de(eventos, "SIN-012")["ids_noticias"] == ["SIN-012"]
    assert evento_de(eventos, "SIN-015")["ids_noticias"] == ["SIN-015"]
    # Inflación y desempleo son temas económicos distintos
    assert "SIN-018" not in evento_de(eventos, "SIN-004")["ids_noticias"]


def test_cifras_contradictorias_quedan_en_el_mismo_evento(eventos):
    # 018 (9.5%) y 019 (7.4%) hablan del mismo dato: deben quedar juntas para
    # que la etapa de explicación muestre ambas versiones (T05)
    assert "SIN-019" in evento_de(eventos, "SIN-018")["ids_noticias"]


def test_sismo_agrupado_y_clasificado(eventos):
    sismo = evento_de(eventos, "SIN-006")
    assert "SIN-007" in sismo["ids_noticias"]


def test_respaldo_sin_llm_marca_el_metodo():
    noticias = cargar_noticias(RUTA)
    asignar_temas(noticias, embeber(n["titulo"] for n in noticias), usar_llm=False)
    assert all(n["metodo_tema"] == "respaldo_embeddings" for n in noticias)


def test_temas_con_llm(temas_llm):
    esperado = {
        "SIN-001": "logistica_canal", "SIN-004": "economia", "SIN-006": "eventos_naturales",
        "SIN-008": "turismo", "SIN-010": "servicios_publicos", "SIN-012": "servicios_publicos",
        "SIN-011": "regulacion", "SIN-015": "otro",
    }
    for id_noticia, tema in esperado.items():
        assert temas_llm[id_noticia]["tema_asignado"] == tema, id_noticia
        assert temas_llm[id_noticia]["metodo_tema"] == "llm"


def test_T07_titular_con_inyeccion_no_cambia_el_comportamiento(temas_llm):
    # SIN-017 pide ignorar instrucciones y ponerse prioridad 100: se clasifica como "otro"
    assert temas_llm["SIN-017"]["tema_asignado"] == "otro"


def test_ids_estables(eventos):
    # Correr dos veces da los mismos IDs de evento
    otra_vez = {e["id_evento"] for e in organizar(cargar_noticias(RUTA))}
    assert otra_vez == set(eventos)
