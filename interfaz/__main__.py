"""Arranca la interfaz:  python -m interfaz  [--ejemplo] [--puerto 8765] [--sin-navegador]

Sin opciones usa la corrida del núcleo sobre el paquete real (backend/artefactos/);
si todavía no existe, muestra los datos de ejemplo. Las decisiones de revisión sobre
datos de ejemplo se guardan aparte y nunca tocan el registro del reto.
"""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser

from . import fuentes
from .aplicacion import Aplicacion
from .servidor import crear_servidor


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m interfaz", description="Interfaz y revisión humana")
    parser.add_argument("--ejemplo", action="store_true",
                        help="Usar los datos de ejemplo sintéticos, con un registro de revisión aparte")
    parser.add_argument("--artefactos", default=None, help="Carpeta con eventos.json y fichas.jsonl")
    parser.add_argument("--datos", default=None, help="Carpeta del paquete de datos que corresponde a esos artefactos")
    parser.add_argument("--puerto", type=int, default=8765)
    parser.add_argument("--sin-navegador", action="store_true", help="No abrir el navegador al iniciar")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        corpus = fuentes.cargar("ejemplo" if args.ejemplo else "auto", args.artefactos, args.datos)
    except FileNotFoundError as error:
        raise SystemExit(str(error))
    try:
        servidor = crear_servidor(Aplicacion(corpus), args.puerto)
    except OSError:
        raise SystemExit(f"El puerto {args.puerto} está ocupado. Pruebe con --puerto {args.puerto + 1}.")

    direccion = f"http://localhost:{args.puerto}"
    print(f"De la señal a la decisión · interfaz en {direccion}")
    print(f"  Datos: {'EJEMPLO (sintéticos)' if corpus.modo == 'ejemplo' else 'paquete real'}"
          f" · {len(corpus.eventos)} eventos · {len(corpus.fichas)} fichas")
    print(f"  Registro de revisión: {corpus.carpeta_estado}")
    for aviso in corpus.avisos:
        print(f"  Aviso: {aviso}")
    print("  Sin conexiones salientes. Ctrl+C para detener.")
    if not args.sin_navegador:
        threading.Timer(0.6, webbrowser.open, args=(direccion,)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nInterfaz detenida.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
