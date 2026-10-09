"""Etapa 7 · Revisar: estados, bitácora y separación entre el ejemplo y el reto."""

import json

import pytest
from .apoyo import REVISORA, caso_con

from interfaz import fuentes, revision, rutas
from interfaz.aplicacion import Aplicacion, CasoInexistente


def test_los_estados_son_los_cinco_del_reto():
    assert revision.ESTADOS == ("nuevo", "en revisión", "requiere evidencia", "aprobado como borrador", "descartado")


def test_el_estado_inicial_lo_pone_el_sistema_y_no_hay_revisor(aplicacion):
    for fila in aplicacion.bandeja():
        esperado = "requiere evidencia" if fila["estado_evidencia"] == "insuficiente" else "nuevo"
        assert fila["estado_revision"] == esperado
        assert fila["revisor"] is None


def test_toda_decision_exige_el_nombre_de_una_persona(aplicacion):
    fila = caso_con(aplicacion, estado_revision="nuevo")
    for nombre in (None, "", "  ", "ab"):
        with pytest.raises(revision.ReglaDeRevision, match="persona responsable"):
            aplicacion.cambiar_estado(fila["id_evento"], revision.EN_REVISION, nombre, None)
    assert aplicacion.bitacora.registros() == []


def test_descartar_y_reabrir_exigen_una_nota(aplicacion):
    id_evento = caso_con(aplicacion, estado_revision="nuevo")["id_evento"]

    with pytest.raises(revision.ReglaDeRevision, match="por qué se descarta"):
        aplicacion.cambiar_estado(id_evento, revision.DESCARTADO, REVISORA, "no")
    aplicacion.cambiar_estado(id_evento, revision.DESCARTADO, REVISORA, "Duplica un caso ya cubierto ayer.")

    acciones = aplicacion.caso(id_evento)["revision"]["acciones"]
    assert [a["estado"] for a in acciones] == [revision.EN_REVISION] and acciones[0]["accion"] == "reabrir"
    with pytest.raises(revision.ReglaDeRevision, match="por qué se reabre"):
        aplicacion.cambiar_estado(id_evento, revision.EN_REVISION, REVISORA, None)
    with pytest.raises(revision.ReglaDeRevision, match="no puede pasar"):
        aplicacion.cambiar_estado(id_evento, revision.APROBADO, REVISORA, "Lo apruebo directamente.")


def test_aprobar_con_cifras_en_conflicto_exige_explicar_la_verificacion(aplicacion):
    id_evento = caso_con(aplicacion, contradiccion=True)["id_evento"]

    with pytest.raises(revision.ReglaDeRevision, match="cifras en conflicto"):
        aplicacion.cambiar_estado(id_evento, revision.APROBADO, REVISORA, None)
    vista = aplicacion.cambiar_estado(id_evento, revision.APROBADO, REVISORA,
                                      "Se confirmó con la fuente primaria que la cifra vigente es la segunda.")
    assert vista["revision"]["estado"] == revision.APROBADO
    assert vista["revision"]["nota"].startswith("Se confirmó")


def test_la_bitacora_solo_crece_y_sobrevive_a_un_reinicio(aplicacion, corpus):
    id_evento = caso_con(aplicacion, estado_revision="nuevo")["id_evento"]
    aplicacion.cambiar_estado(id_evento, revision.EN_REVISION, REVISORA, None)
    aplicacion.cambiar_estado(id_evento, revision.REQUIERE_EVIDENCIA, "Otra Persona", "Falta la fuente primaria.")

    lineas = aplicacion.bitacora.ruta.read_text(encoding="utf-8").splitlines()
    assert [json.loads(linea)["id_registro"] for linea in lineas] == [1, 2]
    assert [json.loads(linea)["estado_nuevo"] for linea in lineas] == [revision.EN_REVISION, revision.REQUIERE_EVIDENCIA]
    assert all(json.loads(linea)["fecha_utc"].endswith("Z") for linea in lineas)

    reabierta = Aplicacion(corpus)
    vista = reabierta.caso(id_evento)["revision"]
    assert vista["estado"] == revision.REQUIERE_EVIDENCIA and vista["revisor"] == "Otra Persona"
    assert len(vista["historial"]) == 2


def test_una_decision_sobre_una_ficha_que_luego_cambio_queda_marcada(aplicacion):
    fila = caso_con(aplicacion, tiene_borrador=True, estado_evidencia="suficiente para el borrador")
    id_evento = fila["id_evento"]
    aplicacion.cambiar_estado(id_evento, revision.APROBADO, REVISORA, None)
    assert aplicacion.caso(id_evento)["revision"]["desactualizada"] is False

    ficha = aplicacion.corpus.fichas[id_evento]
    original = ficha["borrador"]
    try:  # el núcleo vuelve a correr y redacta otro borrador
        ficha["borrador"] = {**original, "brief": original["brief"] + " Texto nuevo."}
        assert aplicacion.caso(id_evento)["revision"]["desactualizada"] is True
    finally:
        ficha["borrador"] = original


def test_las_decisiones_del_ejemplo_no_tocan_el_registro_del_reto(tmp_path, monkeypatch):
    monkeypatch.setattr(rutas, "ESTADO", tmp_path)
    ejemplo = Aplicacion(fuentes.cargar("ejemplo"))
    reto = Aplicacion(fuentes.cargar("real", rutas.ARTEFACTOS_EJEMPLO, rutas.DATOS_EJEMPLO))
    id_evento = caso_con(ejemplo, estado_revision="nuevo")["id_evento"]

    ejemplo.cambiar_estado(id_evento, revision.EN_REVISION, REVISORA, None)

    assert ejemplo.bitacora.ruta == tmp_path / "ejemplo" / "bitacora.jsonl"
    assert reto.bitacora.ruta == tmp_path / "real" / "bitacora.jsonl"
    assert not reto.bitacora.ruta.exists()
    assert Aplicacion(reto.corpus).caso(id_evento)["revision"]["estado"] == "nuevo"


def test_solo_el_registro_de_ejemplo_se_puede_reiniciar(tmp_path, monkeypatch):
    monkeypatch.setattr(rutas, "ESTADO", tmp_path)
    ejemplo = Aplicacion(fuentes.cargar("ejemplo"))
    reto = Aplicacion(fuentes.cargar("real", rutas.ARTEFACTOS_EJEMPLO, rutas.DATOS_EJEMPLO))
    id_evento = caso_con(ejemplo, estado_revision="nuevo")["id_evento"]
    ejemplo.cambiar_estado(id_evento, revision.EN_REVISION, REVISORA, None)

    ejemplo.reiniciar_ejemplo()
    assert ejemplo.bitacora.registros() == [] and not ejemplo.bitacora.ruta.exists()
    with pytest.raises(PermissionError):
        reto.reiniciar_ejemplo()


def test_las_fichas_revisadas_conservan_el_contrato_de_datos(aplicacion):
    id_evento = caso_con(aplicacion, tiene_borrador=True, estado_evidencia="suficiente para el borrador")["id_evento"]
    aplicacion.cambiar_estado(id_evento, revision.APROBADO, REVISORA, None)
    fichas = aplicacion.fichas_revisadas()

    contrato = {"id_caso", "modalidad", "ids_fuente", "afirmaciones", "citas", "puntaje", "componentes",
                "estado_evidencia", "borrador", "estado_revision"}
    assert len(fichas) == len(aplicacion.corpus.fichas) >= 5
    assert all(contrato <= set(ficha) for ficha in fichas)
    assert any(ficha["estado_evidencia"] == "insuficiente" for ficha in fichas), "incluye un caso sin evidencia suficiente"
    aprobada = next(ficha for ficha in fichas if ficha["id_evento"] == id_evento)
    assert aprobada["estado_revision"] == "aprobado como borrador"
    assert aprobada["revision"]["persona_revisora"] == REVISORA and aprobada["revision"]["historial"]


def test_un_evento_fuera_del_lote_se_explica_con_la_plantilla_y_sin_borrador(aplicacion):
    fila = caso_con(aplicacion, tiene_ficha=False, sin_evidencia_utilizable=False)
    vista = aplicacion.caso(fila["id_evento"])

    assert vista["ficha"] is None and vista["revision"]["borrador"] is None
    assert vista["vista_previa"]["afirmaciones"] and vista["vista_previa"]["que_falta_verificar"]
    aprobar = next(a for a in vista["revision"]["acciones"] if a["estado"] == revision.APROBADO)
    assert aprobar["permitido"] is False


def test_el_caso_con_un_titular_que_da_instrucciones_lo_muestra_como_no_confiable(aplicacion):
    fila = caso_con(aplicacion, no_confiable=True)
    vista = aplicacion.caso(fila["id_evento"])

    assert vista["titulo_no_confiable"] is True and vista["evidencia"] == {}
    assert vista["no_confiable"][0]["patrones"]
    assert fila["nivel"] == "bajo", "pedir «prioridad 100» en el titular no sube el puntaje"
    assert "[Titular no confiable" in aplicacion.markdown(fila["id_evento"])


def test_un_caso_que_no_existe_se_reporta(aplicacion):
    with pytest.raises(CasoInexistente):
        aplicacion.caso("EV-NO-EXISTE")


def test_el_registro_resume_estados_y_consultas(aplicacion):
    aplicacion.consultar("¿Qué pasó con el Canal?")
    aplicacion.consultar("¿Quién ganó las elecciones?")
    registro = aplicacion.registro()

    assert sum(registro["por_estado"].values()) == len(aplicacion.corpus.eventos)
    assert registro["consultas"]["total"] == 2 and registro["consultas"]["abstenciones"] == 1
    assert registro["consultas"]["descartadas"] == 0
    assert registro["consultas"]["mediana_ms"] is not None
