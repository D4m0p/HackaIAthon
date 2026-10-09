"""Servidor local de la interfaz: una API JSON pequeña y los archivos de la pantalla.

Escucha solo en la propia máquina y no abre conexiones salientes, salvo el envío
a Notion cuando la persona revisora lo pide.
"""

from __future__ import annotations

import json
import re
import sys
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

from . import rutas
from .aplicacion import Aplicacion, CasoInexistente
from .notion import ErrorNotion
from .revision import ReglaDeRevision

MAXIMO_CUERPO = 200_000
TIPOS = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml", ".json": "application/json; charset=utf-8",
    ".ico": "image/x-icon", ".png": "image/png", ".woff2": "font/woff2",
}
# La pantalla solo puede cargar y llamar a este mismo servidor.
POLITICA = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
            "font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'")
ID = r"([A-Za-z0-9._:\-]+)"


class Peticion(Exception):
    def __init__(self, estado: HTTPStatus, mensaje: str):
        super().__init__(mensaje)
        self.estado, self.mensaje = estado, mensaje


def crear_manejador(aplicacion: Aplicacion):
    rutas_get = [
        (r"/api/estado", lambda m: aplicacion.estado()),
        (r"/api/bandeja", lambda m: aplicacion.bandeja()),
        (r"/api/registro", lambda m: aplicacion.registro()),
        (r"/api/datos", lambda m: aplicacion.datos()),
        (rf"/api/casos/{ID}", lambda m: aplicacion.caso(m.group(1))),
    ]
    rutas_post = [
        (r"/api/consulta", lambda m, c: aplicacion.consultar(c.get("pregunta"))),
        (r"/api/ejemplo/reiniciar", lambda m, c: aplicacion.reiniciar_ejemplo() or {"reiniciado": True}),
        (rf"/api/casos/{ID}/revision",
         lambda m, c: aplicacion.cambiar_estado(m.group(1), c.get("estado"), c.get("revisor"), c.get("nota"))),
        (rf"/api/casos/{ID}/borrador",
         lambda m, c: aplicacion.corregir(m.group(1), c.get("cambios"), c.get("revisor"), c.get("nota"))),
        (rf"/api/casos/{ID}/ficha", lambda m, c: aplicacion.generar_ficha(m.group(1))),
        (rf"/api/casos/{ID}/notion", lambda m, c: aplicacion.enviar_a_notion(m.group(1), c.get("revisor"))),
    ]

    class Manejador(BaseHTTPRequestHandler):
        server_version = "Interfaz"

        def log_message(self, formato, *argumentos):  # silencio: la bitácora es el registro que importa
            pass

        # -- respuestas --------------------------------------------------------
        def _responder(self, estado: HTTPStatus, cuerpo: bytes, tipo: str, extra: dict | None = None) -> None:
            self.send_response(estado)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", POLITICA)
            for clave, valor in (extra or {}).items():
                self.send_header(clave, valor)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(cuerpo)

        def _json(self, datos, estado: HTTPStatus = HTTPStatus.OK) -> None:
            self._responder(estado, json.dumps(datos, ensure_ascii=False).encode("utf-8"), TIPOS[".json"])

        def _error(self, estado: HTTPStatus, mensaje: str) -> None:
            self._json({"error": mensaje}, estado)

        # -- controles ---------------------------------------------------------
        def _origen_local(self) -> bool:
            """Rechaza peticiones que llegan con otro nombre de host o desde otra página."""
            puerto = self.server.server_address[1]
            permitidos = {f"127.0.0.1:{puerto}", f"localhost:{puerto}"}
            if self.headers.get("Host") not in permitidos:
                return False
            origen = self.headers.get("Origin")
            return origen is None or origen in {f"http://{host}" for host in permitidos}

        def _cuerpo(self) -> dict:
            if "application/json" not in (self.headers.get("Content-Type") or ""):
                raise Peticion(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "El cuerpo debe ser JSON.")
            try:
                largo = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise Peticion(HTTPStatus.BAD_REQUEST, "Falta el tamaño del cuerpo.") from None
            if largo > MAXIMO_CUERPO:
                raise Peticion(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "El cuerpo es demasiado grande.")
            try:
                datos = json.loads(self.rfile.read(largo).decode("utf-8") or "{}")
            except (ValueError, UnicodeDecodeError):
                raise Peticion(HTTPStatus.BAD_REQUEST, "El cuerpo no es JSON válido.") from None
            if not isinstance(datos, dict):
                raise Peticion(HTTPStatus.BAD_REQUEST, "Se esperaba un objeto JSON.")
            return datos

        def _atender(self, accion) -> None:
            if not self._origen_local():
                return self._error(HTTPStatus.FORBIDDEN, "Solo se atiende a la propia máquina.")
            try:
                accion()
            except Peticion as error:
                self._error(error.estado, error.mensaje)
            except CasoInexistente:
                self._error(HTTPStatus.NOT_FOUND, "Ese caso no existe en la bandeja.")
            except ReglaDeRevision as error:
                self._error(HTTPStatus.CONFLICT, str(error))
            except ErrorNotion as error:
                self._error(HTTPStatus.BAD_GATEWAY, str(error))
            except (PermissionError, RuntimeError) as error:
                self._error(HTTPStatus.CONFLICT, str(error))
            except Exception:  # el servidor no debe caerse en plena demo
                traceback.print_exc(file=sys.stderr)
                self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "Error interno. El detalle quedó en la consola.")

        # -- verbos ------------------------------------------------------------
        def do_GET(self) -> None:
            self._atender(self._get)

        do_HEAD = do_GET

        def do_POST(self) -> None:
            self._atender(self._post)

        def _get(self) -> None:
            ruta = unquote(urlsplit(self.path).path)
            for patron, funcion in rutas_get:
                coincidencia = re.fullmatch(patron, ruta)
                if coincidencia:
                    return self._json(funcion(coincidencia))
            coincidencia = re.fullmatch(rf"/api/casos/{ID}/markdown", ruta)
            if coincidencia:
                return self._responder(HTTPStatus.OK, aplicacion.markdown(coincidencia.group(1)).encode("utf-8"),
                                       "text/markdown; charset=utf-8")
            if ruta == "/api/exportar/fichas_revisadas.jsonl":
                lineas = "".join(json.dumps(f, ensure_ascii=False) + "\n" for f in aplicacion.fichas_revisadas())
                return self._responder(HTTPStatus.OK, lineas.encode("utf-8"), "application/x-ndjson; charset=utf-8",
                                       {"Content-Disposition": 'attachment; filename="fichas_revisadas.jsonl"'})
            if ruta.startswith("/api/"):
                raise Peticion(HTTPStatus.NOT_FOUND, "Ruta desconocida.")
            self._archivo(ruta)

        def _post(self) -> None:
            ruta = unquote(urlsplit(self.path).path)
            cuerpo = self._cuerpo()
            for patron, funcion in rutas_post:
                coincidencia = re.fullmatch(patron, ruta)
                if coincidencia:
                    return self._json(funcion(coincidencia, cuerpo))
            raise Peticion(HTTPStatus.NOT_FOUND, "Ruta desconocida.")

        def _archivo(self, ruta: str) -> None:
            relativa = "index.html" if ruta in ("", "/") else ruta.lstrip("/")
            destino = (rutas.WEB / relativa).resolve()
            if rutas.WEB.resolve() not in destino.parents or destino.suffix not in TIPOS or not destino.is_file():
                raise Peticion(HTTPStatus.NOT_FOUND, "No encontrado.")
            self._responder(HTTPStatus.OK, destino.read_bytes(), TIPOS[destino.suffix])

    return Manejador


def crear_servidor(aplicacion: Aplicacion, puerto: int = 8765) -> ThreadingHTTPServer:
    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), crear_manejador(aplicacion))
    servidor.daemon_threads = True
    return servidor
