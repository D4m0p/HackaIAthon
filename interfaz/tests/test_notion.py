"""Registro en Notion: el documento de la ficha y el envío por la API (con un Notion simulado)."""

import pytest
from .apoyo import REVISORA, caso_con

from interfaz import exportar, notion, revision

ESQUEMA = {
    "Caso": {"type": "title", "title": {}},
    "ID de caso": {"type": "rich_text", "rich_text": {}},
    "Puntaje": {"type": "number", "number": {}},
    "Nivel": {"type": "select", "select": {"options": []}},
    "Estado de revisión": {"type": "status", "status": {"options": [{"name": "Nuevo"}, {"name": "Aprobado como borrador"}]}},
    "Persona revisora": {"type": "people", "people": {}},
}
CONFIG = {"token": "secret_de_prueba", "base": "base-123"}


class NotionSimulado:
    def __init__(self):
        self.llamadas = []

    def __call__(self, metodo, ruta, token, cuerpo=None):
        assert token == CONFIG["token"]
        self.llamadas.append((metodo, ruta, cuerpo))
        if ruta.startswith("/databases/"):
            return {"properties": ESQUEMA}
        if ruta == "/pages":
            return {"id": "pagina-1", "url": "https://www.notion.so/pagina-1"}
        if ruta.startswith("/pages/"):
            return {"id": ruta.split("/")[-1], "url": "https://www.notion.so/pagina-1"}
        return {}


@pytest.fixture
def vista(aplicacion):
    fila = caso_con(aplicacion, tiene_borrador=True, estado_evidencia="suficiente para el borrador")
    aplicacion.cambiar_estado(fila["id_evento"], revision.APROBADO, REVISORA, None)
    return aplicacion.caso(fila["id_evento"])


def test_el_documento_tiene_lo_que_pide_la_pagina_casos_y_evidencias(vista):
    """IDs, fuentes, puntaje desglosado, estado de evidencia, borrador y persona revisora."""
    markdown = exportar.a_markdown(exportar.documento(vista))

    assert markdown.startswith(f"# {vista['titulo']}\n")
    assert f"| ID de caso | {vista['id_caso']} |" in markdown
    assert "| Estado de revisión | aprobado como borrador |" in markdown
    assert f"| Persona revisora | {REVISORA} · " in markdown and "(hora de Panamá)" in markdown
    assert "| R · Relevancia |" in markdown and "| E · Evidencia disponible |" in markdown
    for id_fuente in vista["evidencia"]:
        assert f"| {id_fuente} |" in markdown
    assert "Aprobado como borrador: no es una publicación" in markdown
    assert "- [ ] " in markdown, "los pendientes salen como casillas"


def test_las_tablas_del_markdown_escapan_las_barras():
    markdown = exportar.a_markdown([("tabla", ["A", "B"], [["uno | dos", "línea\nrota"]])])
    assert "| uno \\| dos | línea rota |" in markdown


def test_los_bloques_para_la_api_respetan_los_limites_de_notion(vista):
    bloques = exportar.a_bloques_notion(exportar.documento(vista) + [("p", "x" * 5000)])

    tipos = {bloque["type"] for bloque in bloques}
    assert {"heading_1", "heading_2", "paragraph", "quote", "table", "bulleted_list_item", "to_do"} <= tipos
    for bloque in bloques:
        contenido = bloque[bloque["type"]]
        for trozo in contenido.get("rich_text", []):
            assert len(trozo["text"]["content"]) <= 2000
        if bloque["type"] == "table":
            assert all(len(fila["table_row"]["cells"]) == contenido["table_width"] for fila in contenido["children"])


def test_solo_se_llenan_las_columnas_que_la_base_tiene_y_del_tipo_correcto(vista):
    propiedades = notion.propiedades_notion(exportar.propiedades(vista), ESQUEMA)

    assert propiedades["Caso"]["title"][0]["text"]["content"] == vista["titulo"]
    assert propiedades["ID de caso"]["rich_text"][0]["text"]["content"] == vista["id_caso"]
    assert propiedades["Puntaje"] == {"number": vista["prioridad"]["puntaje"]}
    assert propiedades["Nivel"] == {"select": {"name": vista["prioridad"]["nivel"]}}
    assert propiedades["Estado de revisión"] == {"status": {"name": "Aprobado como borrador"}}
    assert "Persona revisora" not in propiedades, "una columna de tipo persona no se puede llenar con un nombre"
    assert "Tema" not in propiedades, "la base no tiene esa columna"


def test_crea_la_pagina_y_luego_la_actualiza_sin_reescribirla(vista):
    simulado = NotionSimulado()
    nodos = exportar.documento(vista)

    creada = notion.sincronizar(exportar.propiedades(vista), nodos, None, enviar=simulado, config=CONFIG)
    assert creada == {"id": "pagina-1", "url": "https://www.notion.so/pagina-1", "accion": "creada"}
    metodo, ruta, cuerpo = simulado.llamadas[1]
    assert (metodo, ruta) == ("POST", "/pages") and cuerpo["parent"] == {"database_id": "base-123"}
    assert 0 < len(cuerpo["children"]) <= 90

    simulado.llamadas.clear()
    actualizada = notion.sincronizar(exportar.propiedades(vista), nodos, "pagina-1", enviar=simulado, config=CONFIG)
    assert actualizada["accion"] == "actualizada"
    assert [(m, r) for m, r, _ in simulado.llamadas] == [
        ("GET", "/databases/base-123"), ("PATCH", "/pages/pagina-1"), ("PATCH", "/blocks/pagina-1/children")]
    agregados = simulado.llamadas[2][2]["children"]
    assert agregados[0]["type"] == "divider" and "Actualización" in agregados[1]["heading_2"]["rich_text"][0]["text"]["content"]


def test_un_documento_largo_se_envia_en_varias_llamadas(vista):
    simulado = NotionSimulado()
    nodos = exportar.documento(vista) + [("lista", [f"punto {i}" for i in range(200)])]

    notion.sincronizar(exportar.propiedades(vista), nodos, None, enviar=simulado, config=CONFIG)

    tandas = [cuerpo["children"] for _, ruta, cuerpo in simulado.llamadas if ruta in ("/pages", "/blocks/pagina-1/children")]
    assert len(tandas) >= 3 and all(len(tanda) <= 90 for tanda in tandas)


def test_enviar_a_notion_queda_en_la_bitacora(aplicacion, vista, monkeypatch):
    simulado = NotionSimulado()
    monkeypatch.setattr(notion, "configuracion", lambda: CONFIG)
    monkeypatch.setattr(notion, "_enviar", simulado)

    resultado = aplicacion.enviar_a_notion(vista["id_evento"], REVISORA)
    assert resultado["notion"]["accion"] == "creada"
    registro = aplicacion.bitacora.registros(vista["id_evento"])[-1]
    assert registro["accion"] == "enviar a Notion" and registro["notion_pagina"] == "pagina-1"
    assert registro["estado_nuevo"] is None, "enviar a Notion no cambia el estado de revisión"

    assert aplicacion.enviar_a_notion(vista["id_evento"], REVISORA)["notion"]["accion"] == "actualizada"


def test_sin_configuracion_no_se_intenta_nada(vista, monkeypatch):
    monkeypatch.setattr(notion, "configuracion", lambda: None)
    with pytest.raises(notion.ErrorNotion, match="no está configurado"):
        notion.sincronizar(exportar.propiedades(vista), exportar.documento(vista))


def test_la_configuracion_se_lee_de_un_archivo_env(tmp_path, monkeypatch):
    archivo = tmp_path / ".env"
    archivo.write_text("# comentario\nNOTION_TOKEN = 'secret_x'\nNOTION_DATABASE_ID=abc123\n", encoding="utf-8")
    monkeypatch.setattr(notion, "RUTA_ENV", archivo)
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)

    assert notion.configuracion() == {"token": "secret_x", "base": "abc123"}
    archivo.write_text("NOTION_TOKEN=secret_x\n", encoding="utf-8")
    assert notion.configuracion() is None
