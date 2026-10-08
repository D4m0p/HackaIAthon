"""
Pruebas de la etapa 3 (Contextualizar) con datos sintéticos.

T04: una cifra anual del Banco Mundial mantiene país, año y unidad, y no se
     describe como cifra de hoy.
"""

from pathlib import Path

import pytest

from nucleo.contextualizar import cargar_indicadores, cargar_sismos, contextualizar
from nucleo.organizar import cargar_noticias, organizar

DATOS = Path(__file__).parent.parent / "datos_ejemplo"


@pytest.fixture(scope="module")
def eventos():
    eventos = organizar(cargar_noticias(DATOS / "noticias_ejemplo.csv"), usar_llm=False, usar_artefactos=False)
    contextualizar(eventos,
                   cargar_indicadores(DATOS / "indicadores_ejemplo.csv"),
                   cargar_sismos(DATOS / "eventos_ejemplo.geojson"))
    return eventos


def evento_de(eventos, id_noticia):
    return next(e for e in eventos if id_noticia in e["ids_noticias"])


def contexto_de(evento, tipo):
    return [c for c in evento["contexto"] if c["tipo"] == tipo]


def test_T04_dato_anual_con_pais_anio_unidad_y_advertencia(eventos):
    inflacion = contexto_de(evento_de(eventos, "SIN-004"), "indicador_banco_mundial")
    assert [c["indicador_id"] for c in inflacion] == ["FP.CPI.TOTL.ZG"]
    dato = inflacion[0]
    assert dato["pais"] == "PAN" and dato["anio"] == 2024 and dato["unidad"] == "% anual"
    assert dato["valor"] == 0.7
    assert "no es una medición actual" in dato["advertencia"].lower()
    assert dato["id_evidencia"] == "WB:PAN:FP.CPI.TOTL.ZG:2024"


def test_nulo_no_se_convierte_en_cero(eventos):
    # El desempleo de Panamá 2024 está vacío: se usa el último año con dato (2023)
    desempleo = contexto_de(evento_de(eventos, "SIN-018"), "indicador_banco_mundial")[0]
    assert desempleo["anio"] == 2023 and desempleo["valor"] == 7.4
    # En la serie, 2024 aparece como "sin dato", no como 0
    assert {"anio": 2024, "valor": "sin dato"} in desempleo["serie"]


def test_no_se_fuerza_relacion(eventos):
    turismo = evento_de(eventos, "SIN-008")
    assert turismo["contexto"] == []
    assert "no se fuerza" in turismo["sin_contexto_motivo"]


def test_sismo_vinculado_por_fecha_y_magnitud(eventos):
    sismos = contexto_de(evento_de(eventos, "SIN-006"), "sismo_usgs")
    assert [s["id_evidencia"] for s in sismos] == ["USGS:sin-us-0001"]
    assert "magnitud 4.8" in sismos[0]["motivo_vinculo"]


def test_inundacion_no_usa_datos_sismicos(eventos):
    # Hay un sismo sintético el mismo día de la inundación (SIN-013), pero USGS
    # solo sirve para hechos sísmicos
    assert contexto_de(evento_de(eventos, "SIN-013"), "sismo_usgs") == []


def test_sismos_en_formato_del_equipo_a(tmp_path):
    # El paquete de A trae las propiedades aplanadas: magnitude y time en ISO 8601
    from nucleo.contextualizar import sismos_desde_lista
    propiedades = {'id': 'us6000m2a6', 'magnitude': 4.6, 'time': '2024-01-07T01:02:08Z',
                   'longitude': -82.4658, 'latitude': 5.0822, 'depth': 10, 'place': 'south of Panama',
                   'status': 'reviewed', 'url': 'https://earthquake.usgs.gov/earthquakes/eventpage/us6000m2a6'}
    desde_lista = sismos_desde_lista([propiedades])[0]
    assert desde_lista['magnitud'] == 4.6 and desde_lista['fecha'].isoformat() == '2024-01-07T01:02:08+00:00'

    ruta = tmp_path / 'eventos.geojson'
    import json
    ruta.write_text(json.dumps({'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'id': 'us6000m2a6', 'geometry': {'type': 'Point', 'coordinates': [-82.4658, 5.0822, 10]},
         'properties': propiedades}]}), encoding='utf-8')
    desde_archivo = cargar_sismos(ruta)[0]
    assert desde_archivo == desde_lista
