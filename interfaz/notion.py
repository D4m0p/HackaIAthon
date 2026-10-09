"""Escritura opcional de fichas en la base «Casos y evidencias» de Notion.

El reto permite registrar la ficha a mano; esto solo ahorra copiar y pegar. Es la única
parte de la interfaz que usa internet, y solo cuando la persona revisora lo pide.

Configuración (en interfaz/.env o en variables de entorno, nunca en el código):
    NOTION_TOKEN=secret_...          token de una integración interna
    NOTION_DATABASE_ID=...           base compartida con esa integración

    python -m interfaz.notion --probar
    python -m interfaz.notion --crear-base ID_DE_LA_PAGINA_PADRE
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from . import revision
from .exportar import a_bloques_notion
from .texto import normalizar

API = "https://api.notion.com/v1"
VERSION_API = "2022-06-28"
RUTA_ENV = Path(__file__).resolve().parent / ".env"
BLOQUES_POR_LLAMADA = 90
SECCION_QUE_SE_ACTUALIZA = "Borrador · paquete editorial"

COLUMNAS = {
    "ID de caso": {"rich_text": {}},
    "Tema": {"select": {}},
    "Puntaje": {"number": {"format": "number"}},
    "Nivel": {"select": {"options": [{"name": n} for n in ("alto", "medio", "bajo")]}},
    "Posición": {"number": {"format": "number"}},
    "Estado de evidencia": {"select": {"options": [
        {"name": n} for n in ("insuficiente", "parcial", "suficiente para el borrador")]}},
    "Estado de revisión": {"select": {"options": [{"name": n} for n in revision.ESTADOS]}},
    "Persona revisora": {"rich_text": {}},
    "Fuentes independientes": {"number": {"format": "number"}},
    "Versión de reglas": {"rich_text": {}},
}


class ErrorNotion(Exception):
    """Notion no aceptó la operación o no hubo conexión. El mensaje nunca incluye el token."""


def _leer_env(ruta: Path) -> dict:
    valores = {}
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            clave, separador, valor = linea.partition("=")
            if separador and not clave.strip().startswith("#"):
                valores[clave.strip()] = valor.strip().strip("\"'")
    return valores


def configuracion() -> dict | None:
    archivo = _leer_env(RUTA_ENV)
    token = os.environ.get("NOTION_TOKEN") or archivo.get("NOTION_TOKEN")
    base = os.environ.get("NOTION_DATABASE_ID") or archivo.get("NOTION_DATABASE_ID")
    return {"token": token, "base": base} if token and base else None


def _enviar(metodo: str, ruta: str, token: str, cuerpo: dict | None = None) -> dict:
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    peticion = urllib.request.Request(f"{API}{ruta}", data=datos, method=metodo, headers={
        "Authorization": f"Bearer {token}", "Notion-Version": VERSION_API, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(peticion, timeout=20) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            detalle = json.loads(error.read().decode("utf-8")).get("message", "")
        except (ValueError, OSError):
            detalle = ""
        raise ErrorNotion(f"Notion respondió {error.code}. {detalle}".strip()) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ErrorNotion("No hay conexión con Notion. Use «Copiar para Notion» y pegue la ficha a mano.") from None


def _texto(valor) -> list[dict]:
    return [{"type": "text", "text": {"content": str(valor)[:1900]}}]


def propiedades_notion(valores: dict, esquema: dict) -> dict:
    """Convierte los valores del caso al formato de cada columna que la base realmente tiene.
    Las columnas que falten o sean de otro tipo se omiten; el contenido de la página no depende de ellas."""
    por_nombre = {normalizar(nombre): (nombre, definicion) for nombre, definicion in esquema.items()}
    salida = {}
    titulo = next((nombre for nombre, definicion in esquema.items() if definicion.get("type") == "title"), None)
    if titulo:
        salida[titulo] = {"title": _texto(valores["titulo"])}
    for clave, valor in valores.items():
        if clave == "titulo" or normalizar(clave) not in por_nombre:
            continue
        nombre, definicion = por_nombre[normalizar(clave)]
        tipo = definicion.get("type")
        if tipo == "rich_text":
            salida[nombre] = {"rich_text": _texto(valor)}
        elif tipo == "number" and isinstance(valor, (int, float)):
            salida[nombre] = {"number": valor}
        elif tipo == "select" and valor != "":
            salida[nombre] = {"select": {"name": str(valor).replace(",", " ")[:100]}}
        elif tipo == "status":
            opciones = {normalizar(o["name"]): o["name"] for o in definicion.get("status", {}).get("options", [])}
            if normalizar(str(valor)) in opciones:
                salida[nombre] = {"status": {"name": opciones[normalizar(str(valor))]}}
    return salida


def sincronizar(valores: dict, nodos: list[tuple], pagina_previa: str | None = None,
                enviar=None, config: dict | None = None) -> dict:
    """Crea la página del caso o actualiza la que ya existe. Devuelve {id, url, accion}.

    Al actualizar no se reescribe lo anterior: se agregan al final el borrador vigente y la
    revisión, para que Notion conserve el rastro de lo que se decidió antes."""
    enviar = enviar or _enviar
    config = config or configuracion()
    if not config:
        raise ErrorNotion("Notion no está configurado: faltan NOTION_TOKEN y NOTION_DATABASE_ID en interfaz/.env.")
    token, base = config["token"], config["base"]
    esquema = enviar("GET", f"/databases/{base}", token).get("properties", {})
    propiedades = propiedades_notion(valores, esquema)

    if pagina_previa:
        pagina = enviar("PATCH", f"/pages/{pagina_previa}", token, {"properties": propiedades})
        inicio = next((i for i, nodo in enumerate(nodos) if nodo[:2] == ("h2", SECCION_QUE_SE_ACTUALIZA)), 0)
        bloques = [{"object": "block", "type": "divider", "divider": {}}] + a_bloques_notion(
            [("h2", f"Actualización · estado: {valores['Estado de revisión']}")] + nodos[inicio:])
        accion = "actualizada"
    else:
        bloques = a_bloques_notion(nodos)
        pagina = enviar("POST", "/pages", token, {
            "parent": {"database_id": base}, "properties": propiedades, "children": bloques[:BLOQUES_POR_LLAMADA]})
        bloques = bloques[BLOQUES_POR_LLAMADA:]
        accion = "creada"

    for inicio in range(0, len(bloques), BLOQUES_POR_LLAMADA):
        enviar("PATCH", f"/blocks/{pagina['id']}/children", token,
               {"children": bloques[inicio:inicio + BLOQUES_POR_LLAMADA]})
    return {"id": pagina["id"], "url": pagina.get("url"), "accion": accion}


def crear_base(pagina_padre: str, token: str) -> dict:
    """Crea la base «Casos y evidencias» con las columnas que la interfaz sabe llenar."""
    return _enviar("POST", "/databases", token, {
        "parent": {"type": "page_id", "page_id": pagina_padre},
        "title": _texto("Casos y evidencias"),
        "properties": {"Caso": {"title": {}}, **COLUMNAS},
    })


def main() -> None:
    parser = argparse.ArgumentParser(description="Conexión de la interfaz con Notion")
    parser.add_argument("--probar", action="store_true", help="Comprueba el acceso a la base configurada")
    parser.add_argument("--crear-base", metavar="ID_PAGINA", help="Crea la base dentro de esa página")
    args = parser.parse_args()
    archivo = _leer_env(RUTA_ENV)
    token = os.environ.get("NOTION_TOKEN") or archivo.get("NOTION_TOKEN")
    if not token:
        raise SystemExit("Falta NOTION_TOKEN en interfaz/.env (ver interfaz/.env.example).")
    try:
        if args.crear_base:
            base = crear_base(args.crear_base, token)
            print(f"Base creada. Agregue a interfaz/.env:\nNOTION_DATABASE_ID={base['id']}")
        else:
            config = configuracion()
            if not config:
                raise SystemExit("Falta NOTION_DATABASE_ID en interfaz/.env.")
            base = _enviar("GET", f"/databases/{config['base']}", token)
            print("Acceso correcto. Columnas:", ", ".join(base.get("properties", {})))
    except ErrorNotion as error:
        raise SystemExit(str(error))


if __name__ == "__main__":
    main()
