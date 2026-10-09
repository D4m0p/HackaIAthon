"""T08 · Caso de prioridad alta.

Esperado: exponer componentes y regla; la prioridad no habilita publicación.
"""

import pytest
from .apoyo import REVISORA, caso_con

from interfaz import revision
from interfaz.puente import config


def test_la_bandeja_expone_los_cinco_componentes_de_cada_puntaje(aplicacion):
    for fila in aplicacion.bandeja():
        assert set(fila["componentes"]) == set(config.PESOS)
        for clave, componente in fila["componentes"].items():
            assert componente["peso"] == config.PESOS[clave]
            assert 0 <= componente["valor"] <= 1
            assert componente["aporte"] == pytest.approx(componente["valor"] * componente["peso"], abs=0.06)
        if not fila["ajuste"]:
            assert fila["puntaje"] == pytest.approx(sum(c["aporte"] for c in fila["componentes"].values()), abs=0.2)


def test_la_bandeja_respeta_el_orden_y_los_niveles_sin_solapamiento(aplicacion):
    filas = aplicacion.bandeja()
    assert [fila["posicion"] for fila in filas] == list(range(1, len(filas) + 1))
    assert [fila["puntaje"] for fila in filas] == sorted((fila["puntaje"] for fila in filas), reverse=True)
    for fila in filas:
        esperado = "alto" if fila["puntaje"] >= 70 else "medio" if fila["puntaje"] >= 40 else "bajo"
        assert fila["nivel"] == esperado


def test_la_ficha_muestra_la_regla_su_version_y_el_porque_de_cada_componente(aplicacion):
    alto = caso_con(aplicacion, nivel="alto")
    prioridad = aplicacion.caso(alto["id_evento"])["prioridad"]

    assert prioridad["formula"] == "P = 30R + 25I + 20U + 15N + 10E"
    assert prioridad["version_reglas"] == config.VERSION_REGLAS
    assert all(componente["explicacion"] for componente in prioridad["componentes"].values())
    assert aplicacion.estado()["reglas"]["formula"] == prioridad["formula"]


def test_el_aviso_de_que_la_prioridad_no_habilita_publicar_esta_en_cada_caso(aplicacion):
    for fila in aplicacion.bandeja():
        avisos = " ".join(aplicacion.caso(fila["id_evento"])["avisos"])
        assert "no confirma la noticia ni habilita su publicación" in avisos


def test_prioridad_alta_con_evidencia_insuficiente_no_se_puede_aprobar(aplicacion):
    alto = caso_con(aplicacion, nivel="alto", estado_evidencia="insuficiente")
    aprobar = next(a for a in aplicacion.caso(alto["id_evento"])["revision"]["acciones"]
                   if a["estado"] == revision.APROBADO)

    assert aprobar["permitido"] is False
    assert "no habilita aprobar ni publicar" in aprobar["impedimento"]
    assert str(alto["puntaje"]) in aprobar["impedimento"]

    with pytest.raises(revision.ReglaDeRevision, match="evidencia es insuficiente"):
        aplicacion.cambiar_estado(alto["id_evento"], revision.APROBADO, REVISORA, "Lo apruebo porque es urgente.")
    assert aplicacion.caso(alto["id_evento"])["revision"]["estado"] == revision.REQUIERE_EVIDENCIA
    assert aplicacion.bitacora.registros() == []


def test_no_existe_un_estado_para_publicar(aplicacion):
    alto = caso_con(aplicacion, nivel="alto", estado_evidencia="suficiente para el borrador")

    assert "publicado" not in revision.ESTADOS
    assert not any("public" in estado for estado in aplicacion.estado()["estados_revision"])
    with pytest.raises(revision.ReglaDeRevision, match="No existe un estado para publicar"):
        aplicacion.cambiar_estado(alto["id_evento"], "publicado", REVISORA, None)


def test_aprobar_un_caso_alto_con_evidencia_suficiente_solo_lo_deja_como_borrador(aplicacion):
    alto = caso_con(aplicacion, nivel="alto", estado_evidencia="suficiente para el borrador")
    vista = aplicacion.cambiar_estado(alto["id_evento"], revision.APROBADO, REVISORA, None)

    assert vista["revision"]["estado"] == "aprobado como borrador"
    assert vista["revision"]["revisor"] == REVISORA
    assert "no es una publicación" in vista["revision"]["aviso_aprobacion"]
    registro = aplicacion.bitacora.registros()[-1]
    assert registro["puntaje"] == alto["puntaje"] and registro["nivel"] == "alto"
    assert registro["version_reglas"] == config.VERSION_REGLAS


def test_la_consulta_explica_la_regla_del_puntaje(aplicacion):
    respuesta = aplicacion.consultar("¿Cómo se calcula el puntaje de atención?")

    assert respuesta["tipo"] == "reglas"
    texto = respuesta["reglas"][0]["texto"] + " ".join(respuesta["reglas"][0]["puntos"])
    assert "30R + 25I + 20U + 15N + 10E" in texto
    assert "no es una probabilidad de verdad" in texto
    assert config.VERSION_REGLAS in texto
