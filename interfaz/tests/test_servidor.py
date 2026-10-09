"""El servidor local: rutas, errores y controles de acceso."""

import json
import threading
import urllib.error
import urllib.request

import pytest
from .apoyo import REVISORA

from interfaz.servidor import crear_servidor


@pytest.fixture
def servidor(aplicacion):
    servidor = crear_servidor(aplicacion, 0)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{servidor.server_address[1]}"
    servidor.shutdown()
    servidor.server_close()


def pedir(url, cuerpo=None, cabeceras=None, metodo=None):
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    cabeceras = {"Content-Type": "application/json", **(cabeceras or {})} if cuerpo is not None else (cabeceras or {})
    peticion = urllib.request.Request(url, data=datos, headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(peticion) as respuesta:
            return respuesta.status, respuesta.read().decode("utf-8"), respuesta.headers
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8"), error.headers


def test_sirve_la_pantalla_y_sus_archivos(servidor):
    estado, cuerpo, cabeceras = pedir(servidor + "/")
    assert estado == 200 and "De la señal a la decisión" in cuerpo
    assert "default-src 'none'" in cabeceras["Content-Security-Policy"]
    assert cabeceras["X-Content-Type-Options"] == "nosniff"
    assert pedir(servidor + "/js/app.js")[2]["Content-Type"].startswith("text/javascript")
    assert pedir(servidor + "/estilos.css")[0] == 200


def test_la_pantalla_no_carga_nada_de_internet():
    """Sin internet durante la demo: ni fuentes, ni bibliotecas, ni estilos externos."""
    from interfaz import rutas
    for archivo in rutas.WEB.rglob("*"):
        if archivo.suffix in (".html", ".css", ".js"):
            texto = archivo.read_text(encoding="utf-8")
            assert "https://" not in texto and "http://" not in texto.replace("http://www.w3.org/2000/svg", ""), archivo.name


@pytest.mark.parametrize("ruta", ["/../rutas.py", "/%2e%2e/rutas.py", "/..%2f__main__.py", "/js/../../servidor.py", "/no-existe.css"])
def test_no_entrega_archivos_fuera_de_la_carpeta_web(servidor, ruta):
    assert pedir(servidor + ruta)[0] == 404


def test_las_rutas_de_lectura_responden(servidor):
    estado = json.loads(pedir(servidor + "/api/estado")[1])
    bandeja = json.loads(pedir(servidor + "/api/bandeja")[1])
    assert estado["modo"] == "ejemplo" and estado["eventos"] == len(bandeja)

    primero = bandeja[0]["id_evento"]
    assert json.loads(pedir(f"{servidor}/api/casos/{primero}")[1])["id_evento"] == primero
    estado_http, markdown, cabeceras = pedir(f"{servidor}/api/casos/{primero}/markdown")
    assert estado_http == 200 and markdown.startswith("# ") and cabeceras["Content-Type"].startswith("text/markdown")
    assert pedir(servidor + "/api/casos/EV-NO-EXISTE")[0] == 404
    assert pedir(servidor + "/api/desconocida")[0] == 404
    assert json.loads(pedir(servidor + "/api/datos")[1])["disponible"] in (True, False)
    assert "por_estado" in json.loads(pedir(servidor + "/api/registro")[1])


def test_consulta_y_revision_por_http(servidor):
    estado, cuerpo, _ = pedir(servidor + "/api/consulta", {"pregunta": "¿Quién ganó las elecciones?"})
    assert estado == 200 and json.loads(cuerpo)["abstencion"] is True

    bandeja = json.loads(pedir(servidor + "/api/bandeja")[1])
    alto = next(f for f in bandeja if f["nivel"] == "alto" and f["estado_evidencia"] == "insuficiente")
    estado, cuerpo, _ = pedir(f"{servidor}/api/casos/{alto['id_evento']}/revision",
                              {"estado": "aprobado como borrador", "revisor": REVISORA})
    assert estado == 409 and "no habilita aprobar ni publicar" in json.loads(cuerpo)["error"]

    nuevo = next(f for f in bandeja if f["estado_revision"] == "nuevo")
    estado, cuerpo, _ = pedir(f"{servidor}/api/casos/{nuevo['id_evento']}/revision",
                              {"estado": "en revisión", "revisor": REVISORA})
    assert estado == 200 and json.loads(cuerpo)["revision"]["estado"] == "en revisión"

    estado, cuerpo, cabeceras = pedir(servidor + "/api/exportar/fichas_revisadas.jsonl")
    fichas = [json.loads(linea) for linea in cuerpo.splitlines()]
    assert estado == 200 and "attachment" in cabeceras["Content-Disposition"]
    assert next(f for f in fichas if f["id_evento"] == nuevo["id_evento"])["estado_revision"] == "en revisión"


def test_rechaza_peticiones_que_no_vienen_de_la_propia_pagina(servidor):
    consulta = {"pregunta": "¿Qué pasó con el Canal?"}
    assert pedir(servidor + "/api/consulta", consulta, {"Origin": "http://sitio-ajeno.example"})[0] == 403
    assert pedir(servidor + "/api/estado", cabeceras={"Host": "sitio-ajeno.example"})[0] == 403
    assert pedir(servidor + "/api/consulta", consulta, {"Origin": servidor})[0] == 200


def test_valida_el_cuerpo_de_las_peticiones(servidor):
    peticion = urllib.request.Request(servidor + "/api/consulta", data=b"pregunta=hola",
                                      headers={"Content-Type": "application/x-www-form-urlencoded"})
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(peticion)
    assert error.value.code == 415

    peticion = urllib.request.Request(servidor + "/api/consulta", data=b"{no es json", headers={"Content-Type": "application/json"})
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(peticion)
    assert error.value.code == 400
    assert pedir(servidor + "/api/consulta", {"pregunta": "x" * 300_000})[0] == 413


def test_enviar_a_notion_sin_configurar_se_explica(servidor, monkeypatch):
    from interfaz import notion
    monkeypatch.setattr(notion, "configuracion", lambda: None)
    bandeja = json.loads(pedir(servidor + "/api/bandeja")[1])
    estado, cuerpo, _ = pedir(f"{servidor}/api/casos/{bandeja[0]['id_evento']}/notion", {"revisor": REVISORA})
    assert estado == 502 and "Notion no está configurado" in json.loads(cuerpo)["error"]
