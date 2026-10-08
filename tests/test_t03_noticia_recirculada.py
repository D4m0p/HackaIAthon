"""T03 · Noticia antigua recirculada.

Esperado: mostrar la fecha original; no presentarla como un evento nuevo.
"""

from conftest import escribir_paquete, noticia

from ingesta import cargar_paquete, fecha_para_mostrar
from ingesta.gdelt import fecha_en_url
from ingesta.recirculacion import marcar_recirculadas


def test_publicacion_antigua_detectada_hoy_se_marca_y_conserva_su_fecha():
    antigua = noticia(
        1, fecha_publicacion="2024-06-10T00:00:00Z", fecha_deteccion="2026-10-06T15:00:00Z",
    )
    reciente = noticia(2)

    marcar_recirculadas([antigua, reciente])

    assert antigua["recirculada"] is True
    assert antigua["fecha_original"] == "2024-06-10T00:00:00Z"
    assert fecha_para_mostrar(antigua) == "2024-06-10T00:00:00Z"
    assert reciente["recirculada"] is False
    assert fecha_para_mostrar(reciente) == "2026-10-05T12:00:00Z"


def test_mismo_titular_que_reaparece_hereda_la_fecha_de_la_primera_vez():
    primera = noticia(
        1, titulo="Canal de Panamá anuncia restricción de calado",
        fecha_publicacion=None, fecha_deteccion="2026-09-10T09:00:00Z",
    )
    replica = noticia(
        2, titulo="Canal de Panama anuncia restricción de calado.", medio="otro.com",
        fecha_publicacion=None, fecha_deteccion="2026-10-06T09:00:00Z",
    )

    marcar_recirculadas([replica, primera])

    assert replica["recirculada"] is True
    assert replica["fecha_original"] == "2026-09-10T09:00:00Z"
    assert primera["recirculada"] is False


def test_replica_del_mismo_dia_no_es_recirculacion():
    una = noticia(1, titulo="Lluvias afectan Colón", fecha_publicacion=None,
                  fecha_deteccion="2026-10-06T09:00:00Z")
    otra = noticia(2, titulo="Lluvias afectan Colón", fecha_publicacion=None,
                   fecha_deteccion="2026-10-07T09:00:00Z")

    marcar_recirculadas([una, otra])

    assert not una["recirculada"] and not otra["recirculada"]


def test_la_fecha_de_deteccion_no_se_copia_como_publicacion():
    assert fecha_en_url("https://medio.com/economia/nota-sin-fecha") is None
    assert fecha_en_url("https://medio.com/2024/06/10/nota") == "2024-06-10T00:00:00Z"
    assert fecha_en_url("https://medio.com/2024/13/45/nota") is None


def test_la_marca_sobrevive_al_guardar_y_cargar_el_paquete(tmp_path):
    noticias = marcar_recirculadas([
        noticia(1, fecha_publicacion="2024-06-10T00:00:00Z", fecha_deteccion="2026-10-06T15:00:00Z"),
        noticia(2),
    ])
    paquete = cargar_paquete(escribir_paquete(tmp_path, noticias, [], []))
    por_id = {fila["id_noticia"]: fila for fila in paquete.noticias}

    assert por_id["N-000000000001"]["recirculada"] is True
    assert por_id["N-000000000001"]["fecha_original"] == "2024-06-10T00:00:00Z"
    assert por_id["N-000000000002"]["recirculada"] is False
    assert paquete.reporte["noticias"]["recirculadas"] == 1
