"""
Pruebas de nucleo/consultar.py (búsqueda semántica y respuesta redactada).
El LLM se simula: no se gasta cuota.
"""

import json
from pathlib import Path

import pytest

import nucleo.consultar as consultar
from nucleo.consultar import BuscadorSemantico, redactar_respuesta
from nucleo.llm import LLMNoDisponible

EVENTOS = json.loads((Path(__file__).parent.parent / "artefactos" / "ejemplo" / "eventos.json")
                     .read_text(encoding="utf-8"))
EVIDENCIA = {
    "SIN-004": {"tipo": "noticia", "titulo": "Inflación en Panamá sube y golpea el precio de la canasta básica",
                "medio": "Medio A"},
    "WB:PAN:FP.CPI.TOTL.ZG:2024": {"tipo": "indicador_banco_mundial", "anio": 2024, "valor": 0.7,
                                    "unidad": "% anual"},
}


@pytest.fixture(scope="module")
def buscador():
    return BuscadorSemantico(EVENTOS)


def test_la_busqueda_semantica_encuentra_parafrasis(buscador):
    # Sin palabras en común con el titular ("restricciones de calado", "Canal de Panamá")
    assert buscador.buscar("¿Qué está pasando con el tránsito de barcos por la vía interoceánica?", 1)[0][0] \
        == "EV-SIN-001"
    assert buscador.buscar("¿Hay barrios que se quedarán sin suministro hídrico?", 1)[0][0] == "EV-SIN-010"


def test_las_preguntas_no_se_guardan_en_la_cache_versionada(buscador, monkeypatch):
    guardados = []
    monkeypatch.setattr(consultar, "embeber", lambda textos, guardar=True: guardados.append(guardar) or
                        __import__("nucleo.organizar", fromlist=["embeber"]).embeber(textos, guardar))
    buscador.buscar("pregunta de prueba que no debe quedar en artefactos")
    assert guardados == [False]


def _llm_falso(respuestas):
    llamadas = []

    def generar(instrucciones, contenido, esquema, modelos, tarea):
        llamadas.append({"tarea": tarea, "contenido": contenido})
        return respuestas[len(llamadas) - 1], "modelo-falso"
    return generar, llamadas


def test_respuesta_valida_se_acepta(monkeypatch):
    generar, _ = _llm_falso([{"suficiente": True, "falta": [],
                              "respuesta": "Según Medio A, la inflación sube [SIN-004:titulo]."}])
    monkeypatch.setattr(consultar, "generar", generar)
    resultado = redactar_respuesta("¿Sube el costo de la comida?", EVIDENCIA)
    assert resultado == {"texto": "Según Medio A, la inflación sube [SIN-004:titulo].", "modelo": "modelo-falso"}


def test_si_la_evidencia_no_alcanza_no_hay_respuesta(monkeypatch):
    generar, _ = _llm_falso([{"suficiente": False, "respuesta": "", "falta": ["Datos sobre la gasolina"]}])
    monkeypatch.setattr(consultar, "generar", generar)
    assert redactar_respuesta("¿Subió la gasolina?", EVIDENCIA) is None


def test_cifra_sin_respaldo_pide_correccion_y_si_no_mejora_se_descarta(monkeypatch):
    mala = {"suficiente": True, "falta": [], "respuesta": "La inflación fue de 3.2% [SIN-004:titulo]."}
    generar, llamadas = _llm_falso([mala, mala])
    monkeypatch.setattr(consultar, "generar", generar)
    assert redactar_respuesta("¿Cuánto subió la inflación?", EVIDENCIA) is None
    assert [l["tarea"] for l in llamadas] == ["consulta", "consulta_correccion"]
    assert "3.2" in llamadas[1]["contenido"]  # la corrección incluye el motivo exacto


def test_correccion_que_cita_bien_se_acepta(monkeypatch):
    mala = {"suficiente": True, "falta": [], "respuesta": "El dato anual de 2024 fue 0.7% [WB:PAN:FP.CPI.TOTL.ZG:2024:valor]."}
    buena = {"suficiente": True, "falta": [],
             "respuesta": "El dato anual de 2024 [WB:PAN:FP.CPI.TOTL.ZG:2024:anio] fue 0.7% "
                          "[WB:PAN:FP.CPI.TOTL.ZG:2024:valor]."}
    generar, _ = _llm_falso([mala, buena])
    monkeypatch.setattr(consultar, "generar", generar)
    assert redactar_respuesta("¿Cuál fue la inflación?", EVIDENCIA)["texto"] == buena["respuesta"]


def test_contradiccion_exige_todas_las_versiones(monkeypatch):
    evidencia = {"A": {"tipo": "noticia", "titulo": "Desempleo en 9.5%"},
                 "B": {"tipo": "noticia", "titulo": "Desempleo baja a 7.4%"}}
    contradicciones = [{"cifra": "9.5%", "ids_noticia": ["A"]}, {"cifra": "7.4%", "ids_noticia": ["B"]}]
    solo_una = {"suficiente": True, "falta": [], "respuesta": "El desempleo es 9.5% [A:titulo]."}
    generar, _ = _llm_falso([solo_una, solo_una])
    monkeypatch.setattr(consultar, "generar", generar)
    assert redactar_respuesta("¿Cuál es el desempleo?", evidencia, contradicciones) is None


def test_sin_llm_no_hay_respuesta_redactada(monkeypatch):
    def sin_llm(*args, **kwargs):
        raise LLMNoDisponible("sin conexión")
    monkeypatch.setattr(consultar, "generar", sin_llm)
    assert redactar_respuesta("¿Sube la inflación?", EVIDENCIA) is None
