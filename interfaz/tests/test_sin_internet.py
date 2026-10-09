"""T10 desde la interfaz · Sin internet durante la demo.

Esperado: toda la interfaz funciona con el snapshot, sin abrir ninguna conexión.
"""

from .apoyo import REVISORA

from interfaz import fuentes, revision, rutas
from interfaz.aplicacion import Aplicacion


def test_el_recorrido_completo_funciona_sin_red(sin_internet, tmp_path, monkeypatch):
    monkeypatch.setattr(rutas, "ESTADO", tmp_path)
    aplicacion = Aplicacion(fuentes.cargar("ejemplo"))

    bandeja = aplicacion.bandeja()
    assert len(bandeja) >= 5 and aplicacion.estado()["modo"] == "ejemplo"

    con_borrador = next(f for f in bandeja if f["tiene_borrador"] and f["estado_evidencia"] == "suficiente para el borrador")
    assert aplicacion.caso(con_borrador["id_evento"])["revision"]["borrador"]
    assert aplicacion.consultar("¿Qué cinco temas merecen revisión para la agenda de Panamá y por qué?")["casos"]
    assert aplicacion.consultar("¿Cuál fue la inflación de Panamá en 2023?")["afirmaciones"]
    assert aplicacion.consultar("¿Quién ganó las elecciones?")["abstencion"] is True

    vista = aplicacion.cambiar_estado(con_borrador["id_evento"], revision.APROBADO, REVISORA, None)
    assert vista["revision"]["estado"] == revision.APROBADO
    assert aplicacion.markdown(con_borrador["id_evento"]).startswith("# ")
    assert aplicacion.fichas_revisadas() and aplicacion.registro()["decisiones"]


def test_el_paquete_real_se_verifica_sin_red(sin_internet, aplicacion):
    datos = aplicacion.datos()
    if not datos["disponible"]:
        return
    assert datos["integro"], datos["incidencias"]
    assert len(datos["archivos"]) == 3 and all(len(a["sha256"]) == 64 for a in datos["archivos"])
    assert datos["reporte"]["noticias"]["validas"] >= 100


def test_sin_la_corrida_real_se_usa_el_ejemplo_y_se_avisa():
    corpus = fuentes.cargar("auto")
    if fuentes.hay_corrida_real():
        assert corpus.modo == "real" and corpus.avisos == []
    else:
        assert corpus.modo == "ejemplo"
        assert "datos de ejemplo" in corpus.avisos[0]
