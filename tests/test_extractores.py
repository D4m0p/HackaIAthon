"""Los extractores convierten cada fuente al contrato sin inventar datos."""

import json
from datetime import datetime, timezone

from ingesta import banco_mundial, gdelt, tvn, usgs
from ingesta.comun import a_hora_panama, normalizar_url
from ingesta.snapshot import _fusionar

EXTRACCION = "2026-10-08T18:00:00Z"

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel><title>TVN</title><language>es</language>
<item>
  <title>Canal de Panamá ajusta el calado</title>
  <link>https://www.tvn-2.com/nacionales/canal-ajusta-calado_1_100.html?utm_source=rss</link>
  <description>Texto que no debe copiarse al paquete.</description>
  <pubDate>Thu, 08 Oct 2026 13:23:50 +0000</pubDate>
  <media:keywords>Canal de Panamá,logística</media:keywords>
</item>
<item><title>Nota sin fecha</title><link>https://www.tvn-2.com/mundo/nota_1_101.html</link></item>
</channel></rss>""".encode("utf-8")


def test_tvn_conserva_metadatos_y_descarta_la_descripcion():
    primera, segunda = tvn.interpretar(RSS, EXTRACCION)

    assert primera["titulo"] == "Canal de Panamá ajusta el calado"
    assert primera["url"] == "https://www.tvn-2.com/nacionales/canal-ajusta-calado_1_100.html"
    assert primera["fecha_publicacion"] == "2026-10-08T13:23:50Z"
    assert primera["medio"] == "TVN" and primera["origen"] == "tvn_rss"
    assert primera["alcance_texto"] == "titular_y_metadatos"
    assert primera["palabras_clave"] == "Canal de Panamá,logística"
    assert primera["seccion"] == "nacionales"
    assert "descripcion" not in primera
    assert "no debe copiarse" not in json.dumps(primera, ensure_ascii=False)
    assert segunda["fecha_publicacion"] is None


def test_gdelt_guarda_seendate_como_deteccion_y_no_como_publicacion():
    respuesta = json.dumps({"articles": [
        {"url": "https://www.prensa.com/economia/nota/", "title": "Inflación : sube 2 % en Panamá",
         "seendate": "20261001T233000Z", "domain": "prensa.com", "language": "Spanish",
         "sourcecountry": "Panama"},
        {"url": "https://www.tvn-2.com/nacionales/2026/09/30/nota.html", "title": "Otra nota",
         "seendate": "20261001T120000Z", "domain": "tvn-2.com", "language": "Greek", "sourcecountry": ""},
    ]}).encode("utf-8")

    primera, segunda = gdelt.interpretar(respuesta, "economia", EXTRACCION)

    assert primera["fecha_deteccion"] == "2026-10-01T23:30:00Z"
    assert primera["fecha_publicacion"] is None
    assert primera["titulo"] == "Inflación: sube 2% en Panamá"
    assert primera["url"] == "https://www.prensa.com/economia/nota"
    assert (primera["medio"], primera["idioma"], primera["tema"]) == ("prensa.com", "es", "economia")
    assert segunda["medio"] == "TVN" and segunda["idioma"] == "el"
    assert segunda["fecha_publicacion"] == "2026-09-30T00:00:00Z"
    assert segunda["pais_medio"] is None


def test_gdelt_respuesta_vacia_no_falla():
    assert gdelt.interpretar(b"{}", "turismo", EXTRACCION) == []
    assert gdelt.interpretar(b"", "turismo", EXTRACCION) == []


def test_gdelt_divide_el_periodo_en_ventanas():
    plan = gdelt.planificar(datetime(2026, 10, 8, tzinfo=timezone.utc), dias=30, dias_por_ventana=10)

    assert len(plan) == 3 * len(gdelt.CONSULTAS)
    assert plan[0]["inicio"] == "2026-09-08T00:00:00Z" and plan[2]["fin"] == "2026-10-08T00:00:00Z"
    assert all("maxrecords=250" in consulta["url"] for consulta in plan)


def test_la_fusion_deja_una_noticia_por_url_y_la_deteccion_mas_antigua():
    del_rss = tvn.interpretar(RSS, EXTRACCION)[0]
    de_gdelt = gdelt.interpretar(json.dumps({"articles": [{
        "url": "https://www.tvn-2.com/nacionales/canal-ajusta-calado_1_100.html",
        "title": "Canal de Panamá ajusta el calado", "seendate": "20261008T140000Z",
        "domain": "tvn-2.com", "language": "Spanish", "sourcecountry": "Panama",
    }]}).encode("utf-8"), "logistica", EXTRACCION)[0]

    unicas, duplicados = _fusionar([del_rss, de_gdelt])

    assert duplicados == 1 and len(unicas) == 1
    assert unicas[0]["origen"] == "tvn_rss"
    assert unicas[0]["fecha_deteccion"] == "2026-10-08T14:00:00Z"
    assert unicas[0]["fecha_publicacion"] == "2026-10-08T13:23:50Z"
    assert unicas[0]["tema"] == "logistica"


def test_banco_mundial_completa_la_cuadricula_con_nulos():
    respuesta = json.dumps([
        {"lastupdated": "2026-10-08"},
        [
            {"countryiso3code": "PAN", "date": "2023", "value": 7.2},
            {"countryiso3code": "PAN", "date": "2024", "value": None},
            {"countryiso3code": "CRI", "date": "2023", "value": 0},
        ],
    ]).encode("utf-8")

    filas = banco_mundial.interpretar(respuesta, "NY.GDP.MKTP.KD.ZG", EXTRACCION)
    valores = {(fila["pais_iso3"], fila["anio"]): fila["valor"] for fila in filas}

    assert len(filas) == 6 * 15
    assert valores[("PAN", 2023)] == 7.2
    assert valores[("PAN", 2024)] is None      # la API lo entrega sin valor
    assert valores[("MEX", 2015)] is None      # la API no lo entrega
    assert valores[("CRI", 2023)] == 0         # un cero real se conserva como cero
    assert filas[0]["unidad"] == "% anual" and filas[0]["licencia"] == "CC BY 4.0"
    assert filas[0]["fuente_url"].endswith("NY.GDP.MKTP.KD.ZG?locations=PA")


def test_usgs_convierte_tiempos_y_separa_coordenadas():
    respuesta = json.dumps({"features": [{
        "id": "us6000m2a6",
        "geometry": {"type": "Point", "coordinates": [-82.4658, 5.0822, 10]},
        "properties": {"mag": 4.6, "time": 1704589328000, "updated": 1710020391000,
                       "place": "south of Panama", "status": "reviewed",
                       "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us6000m2a6"},
    }]}).encode("utf-8")

    coleccion = usgs.interpretar(respuesta, EXTRACCION)
    propiedades = coleccion["features"][0]["properties"]

    assert propiedades["time"] == "2024-01-07T01:02:08Z"
    assert (propiedades["longitude"], propiedades["latitude"], propiedades["depth"]) == (-82.4658, 5.0822, 10)
    assert propiedades["magnitude"] == 4.6
    assert "no es evidencia de inundaciones" in coleccion["metadata"]["advertencia"]


def test_utilidades_de_url_y_hora():
    assert normalizar_url("HTTPS://Medio.com/Nota/?utm_source=x&id=5#seccion") == "https://medio.com/Nota?id=5"
    assert a_hora_panama("2026-10-08T18:00:00Z") == "2026-10-08 13:00 (hora de Panamá)"
    assert a_hora_panama("no es fecha") is None
