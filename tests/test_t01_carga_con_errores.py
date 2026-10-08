"""T01 · Archivo con fechas inválidas y nulos.

Esperado: validar, separar errores y conservar nulos; no bloquear toda la carga.
"""

from conftest import escribir_paquete, indicador, noticia, sismo

from ingesta import cargar_paquete
from ingesta.calidad import a_markdown


def paquete_defectuoso(directorio):
    noticias = [
        noticia(1),
        noticia(2, fecha_publicacion="31/02/2026"),          # fecha imposible y en otro formato
        noticia(3, fecha_publicacion=None),                   # nulo permitido: solo hay detección
        noticia(4, fecha_publicacion=None, fecha_deteccion=None),
        noticia(5, url="sin-esquema.com/nota"),
        noticia(6, titulo=None),
        noticia(1, titulo="Otro titular con el mismo ID"),    # ID repetido
        {},                                                   # fila completamente nula
        noticia(7, idioma=None, tema=None),                   # nulos en campos opcionales
        noticia(8, fecha_deteccion="2019-05-01T00:00:00Z", fecha_publicacion="2019-05-01T00:00:00Z"),
    ]
    indicadores = [
        indicador(anio=2022),
        indicador(anio=2023, valor=None),                     # observación faltante: se conserva
        indicador(anio=2024, valor="n/d"),                    # texto donde va un número
        indicador(pais="Panama", anio=2021),
        indicador(anio="dos mil"),
    ]
    sismos = [sismo("us0001"), sismo("us0002", time="ayer"), sismo("us0003", latitude=123)]
    return escribir_paquete(directorio, noticias, indicadores, sismos)


def test_las_filas_validas_se_cargan_aunque_otras_fallen(tmp_path):
    paquete = cargar_paquete(paquete_defectuoso(tmp_path))

    assert [fila["id_noticia"] for fila in paquete.noticias] == [
        "N-000000000001", "N-000000000003", "N-000000000007",
    ]
    assert [fila["anio"] for fila in paquete.indicadores] == [2022, 2023]
    assert [fila["id"] for fila in paquete.eventos] == ["us0001"]


def test_cada_fila_apartada_explica_su_motivo(tmp_path):
    paquete = cargar_paquete(paquete_defectuoso(tmp_path))
    motivos = {
        (rechazada["fila"], motivo.split(":")[0])
        for rechazada in paquete.rechazados["noticias"]
        for motivo in rechazada["motivos"]
    }

    assert (2, "fecha_publicacion inválida") in motivos
    assert (4, "sin fecha de publicación ni de detección") in motivos
    assert (5, "url inválida") in motivos
    assert (6, "falta titulo") in motivos
    assert (7, "id_noticia duplicado") in motivos
    assert (8, "fila vacía") in motivos
    assert (10, "fuera del intervalo") in motivos
    assert len(paquete.rechazados["noticias"]) == 7
    assert len(paquete.rechazados["indicadores"]) == 3
    assert len(paquete.rechazados["eventos"]) == 2


def test_los_nulos_se_conservan_y_no_se_vuelven_cero(tmp_path):
    paquete = cargar_paquete(paquete_defectuoso(tmp_path))
    por_id = {fila["id_noticia"]: fila for fila in paquete.noticias}
    por_anio = {fila["anio"]: fila for fila in paquete.indicadores}

    assert por_id["N-000000000003"]["fecha_publicacion"] is None
    assert por_id["N-000000000007"]["idioma"] is None
    assert por_id["N-000000000007"]["tema"] is None
    assert por_anio[2023]["valor"] is None
    assert por_anio[2022]["valor"] == 7.2


def test_el_reporte_de_calidad_cuenta_validas_y_apartadas(tmp_path):
    paquete = cargar_paquete(paquete_defectuoso(tmp_path))
    noticias = paquete.reporte["noticias"]

    assert (noticias["leidas"], noticias["validas"], noticias["rechazadas"]) == (10, 3, 7)
    assert noticias["motivos_de_rechazo"]["fecha_publicacion inválida"] == 1
    assert noticias["nulos_por_campo"]["fecha_publicacion"] == 1
    assert paquete.reporte["indicadores"]["sin_valor"] == 1
    assert "| noticias.csv | 10 | 3 | 7 |" in a_markdown(paquete.reporte)


def test_un_archivo_ilegible_no_impide_cargar_los_demas(tmp_path):
    directorio = paquete_defectuoso(tmp_path)
    (directorio / "processed/eventos.geojson").write_text("{esto no es json", encoding="utf-8")

    paquete = cargar_paquete(directorio)

    assert len(paquete.noticias) == 3
    assert paquete.eventos == []
    assert any("eventos.geojson" in incidencia for incidencia in paquete.incidencias)
