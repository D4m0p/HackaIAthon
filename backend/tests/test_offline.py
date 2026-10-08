"""
T10 · Sin internet durante la demo.

Corre el pipeline con --offline (sin clave de Gemini y sin acceso a Hugging Face)
y comprueba que el resultado es el mismo que con conexión, gracias a los
artefactos versionados en artefactos/.
"""

import json
from pathlib import Path

import pytest

from nucleo.pipeline import DATOS_EJEMPLO, correr

ARTEFACTOS = Path(__file__).parent.parent / "artefactos"
FECHA_CORTE = "2025-09-30T00:00:00Z"


@pytest.fixture
def sin_internet(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")


@pytest.fixture
def corrida_offline(sin_internet, tmp_path):
    return correr(DATOS_EJEMPLO / "noticias_ejemplo.csv", DATOS_EJEMPLO / "indicadores_ejemplo.csv",
                  DATOS_EJEMPLO / "eventos_ejemplo.geojson", FECHA_CORTE, offline=True, carpeta_salida=tmp_path)


def test_T10_ranking_offline_identico_al_de_referencia(corrida_offline):
    eventos, _ = corrida_offline
    referencia = json.loads((ARTEFACTOS / "eventos.json").read_text(encoding="utf-8"))
    def ranking(evs):
        return [(e["id_evento"], e["prioridad"]["puntaje"], e["tema"]) for e in evs]
    assert ranking(eventos) == ranking(referencia)


def test_T10_temas_y_fichas_salen_de_artefactos(corrida_offline):
    eventos, fichas = corrida_offline
    assert all(n["metodo_tema"] == "llm" for e in eventos for n in e["noticias"])
    # Ninguna ficha con evidencia utilizable queda sin redacción
    for f in fichas:
        assert f["generado"]["metodo"] in ("llm", "sin_evidencia_utilizable"), f["id_caso"]


def test_titular_nuevo_sin_conexion_usa_respaldo_sin_afectar_a_los_demas(sin_internet):
    from nucleo.organizar import cargar_noticias, organizar
    noticias = cargar_noticias(DATOS_EJEMPLO / "noticias_ejemplo.csv")
    nueva = dict(noticias[0], id_noticia="SIN-NUEVA", titulo="Aumenta la tarifa del pasaje del metro en Panamá")
    eventos = organizar(noticias + [nueva], usar_llm=False)

    todas = {n["id_noticia"]: n for e in eventos for n in e["noticias"]}
    assert todas["SIN-NUEVA"]["metodo_tema"] == "respaldo_embeddings"
    # Los demás titulares siguen usando su tema guardado (la caché es por titular, no por lote)
    assert all(n["metodo_tema"] == "llm" for i, n in todas.items() if i != "SIN-NUEVA")
    evento_nuevo = next(e for e in eventos if "SIN-NUEVA" in e["ids_noticias"])
    assert evento_nuevo["tema_por_respaldo"] is True
