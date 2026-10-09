"""Evaluación reproducible de las consultas (sección 9.1 del reto)."""

from pathlib import Path

from interfaz import evaluar
from interfaz.consulta import Motor

BENCHMARK = Path(__file__).resolve().parent.parent / "benchmark_ejemplo.jsonl"


def test_el_benchmark_de_desarrollo_alcanza_las_metas_del_reto(corpus):
    casos = evaluar._leer(BENCHMARK)
    resultados, resumen = evaluar.evaluar(Motor(corpus), casos)

    assert resumen["consultas"] == len(casos) == 40 and resumen["sin_etiqueta"] == 0
    sin_respuesta = resumen["por_tipo"]["sin_respuesta"]
    assert sin_respuesta["cumplen"] / sin_respuesta["total"] >= 0.8, sin_respuesta["fallos"]
    citas = resumen["cobertura_de_citas"]
    assert citas["con_cita_valida"] == citas["emitidas"] >= 30
    assert resumen["abstenciones_incorrectas"]["cantidad"] == 0
    assert resumen["por_tipo"]["adversarial"]["fallos"] == []
    assert resumen["tiempo_ms"]["mediana"] < 15_000
    assert all("respuesta" in resultado for resultado in resultados), "se guarda la salida de cada consulta"


def test_un_fallo_queda_listado_con_su_consulta(corpus):
    casos = [{"id": "X1", "tipo": "sin_respuesta", "consulta": "¿Qué pasó con el Canal?"},
             {"id": "X2", "tipo": "sustentada", "consulta": "¿Quién ganó las elecciones presidenciales?"},
             {"id": "X3", "tipo": None, "consulta": "¿Qué noticias hay sobre el metro?"}]
    _, resumen = evaluar.evaluar(Motor(corpus), casos)

    assert resumen["por_tipo"]["sin_respuesta"] == {"cumplen": 0, "total": 1, "fallos": ["X1: ¿Qué pasó con el Canal?"]}
    assert resumen["abstenciones_incorrectas"] == {"cantidad": 1, "de_respondibles": 1}
    assert resumen["sin_etiqueta"] == 1
    informe = evaluar.a_markdown(resumen, "prueba")
    assert "| Sin respuesta: abstención correcta | 0 de 1 | X1: ¿Qué pasó con el Canal? |" in informe
    assert "| Abstenciones incorrectas | 1 de 1 preguntas respondibles |" in informe


def test_pedir_un_veredicto_sobre_un_indicador_tampoco_lo_emite(corpus):
    respuesta = Motor(corpus).responder("¿Es verdad que el desempleo bajó?")

    assert respuesta["tipo"] == "sin_veredicto"
    assert "no etiqueta noticias como verdaderas o falsas" in respuesta["avisos"][0]
    assert {version["cifra"] for version in respuesta["versiones"]} == {"9.5%", "7.4%"}
