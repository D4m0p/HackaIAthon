"""
Corre el núcleo de IA de punta a punta con un solo comando.

    python -m nucleo.pipeline --paquete ../datos --offline              (datos reales del equipo A)
    python -m nucleo.pipeline --fecha-corte 2025-09-30T00:00:00Z        (datos de ejemplo)

Con --paquete se usa el cargador del equipo A (ingesta.cargar_paquete): valida
el paquete contra su manifest, reporta incidencias sin detenerse y toma de ahí la
fecha de corte.

Con --offline no se usa internet en absoluto: los temas y las redacciones salen
de artefactos/ (versionados en git) y lo que falte se resuelve con el respaldo
local. Es el modo para la demo (prueba T10).

Salidas (en --salida; por defecto artefactos/ con --paquete y artefactos/ejemplo_corrida/ sin él):
- eventos.json   eventos organizados, contextualizados y priorizados
- fichas.jsonl   fichas del top-N (formato del contrato de datos, sección 7)
- excluidas_idioma.json   noticias fuera del panel por idioma (no se borran del paquete)
"""

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

CARPETA_BACKEND = Path(__file__).parent.parent
DATOS_EJEMPLO = CARPETA_BACKEND / "datos_ejemplo"


def cargar_desde_paquete(carpeta_datos):
    """Usa el cargador del equipo A. `carpeta_datos` es la carpeta datos/ del repo;
    el paquete de Python `ingesta` está en la carpeta de arriba."""
    from nucleo.contextualizar import indicadores_desde_lista, sismos_desde_lista
    from nucleo.organizar import preparar_noticias

    carpeta_datos = Path(carpeta_datos).resolve()
    sys.path.insert(0, str(carpeta_datos.parent))
    from ingesta import cargar_paquete

    paquete = cargar_paquete(carpeta_datos)
    if not paquete.integro:
        # Igual que el equipo A: se avisa y se sigue con lo que sí cargó
        print("AVISO: el paquete no está íntegro:")
        for incidencia in paquete.incidencias:
            print(f"  - {incidencia}")
    return (preparar_noticias(paquete.noticias), indicadores_desde_lista(paquete.indicadores),
            sismos_desde_lista(paquete.eventos), paquete.fecha_corte)


def correr(noticias_csv=None, indicadores_csv=None, sismos_geojson=None, fecha_corte=None,
           offline=False, top_n=None, carpeta_salida=None, paquete=None):
    if offline:
        # Debe definirse ANTES de cargar el modelo de embeddings: impide descargas
        os.environ["HF_HUB_OFFLINE"] = "1"

    from nucleo import config
    from nucleo.contextualizar import cargar_indicadores, cargar_sismos, contextualizar
    from nucleo.fichas import generar_fichas, guardar_fichas
    from nucleo.organizar import cargar_noticias, filtrar_por_idioma, organizar
    from nucleo.priorizar import priorizar

    if paquete:
        noticias, indicadores, sismos, corte_manifest = cargar_desde_paquete(paquete)
        fecha_corte = fecha_corte or corte_manifest
    else:
        noticias = cargar_noticias(noticias_csv)
        indicadores, sismos = cargar_indicadores(indicadores_csv), cargar_sismos(sismos_geojson)
    if not fecha_corte:
        raise SystemExit("Falta la fecha de corte: use --fecha-corte o --paquete (la toma del manifest).")

    noticias, excluidas = filtrar_por_idioma(noticias)

    usar_llm = not offline
    eventos = organizar(noticias, usar_llm=usar_llm)
    contextualizar(eventos, indicadores, sismos)
    priorizar(eventos, fecha_corte)
    fichas = generar_fichas(eventos, top_n or config.FICHAS_TOP_N, usar_llm=usar_llm)

    # Datos reales (--paquete) -> artefactos/; datos de ejemplo -> artefactos/ejemplo_corrida/.
    # artefactos/ejemplo/ NO se toca: es un archivo congelado que usan las pruebas de la
    # interfaz (equipo C) y no debe cambiar con cada corrida (ver su LEEME.md).
    por_defecto = CARPETA_BACKEND / config.CARPETA_ARTEFACTOS
    salida = Path(carpeta_salida or (por_defecto if paquete else por_defecto / "ejemplo_corrida"))
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "eventos.json").write_text(json.dumps(eventos, ensure_ascii=False, indent=1, default=str),
                                         encoding="utf-8")
    guardar_fichas(fichas, salida / "fichas.jsonl")
    (salida / "excluidas_idioma.json").write_text(json.dumps(excluidas, ensure_ascii=False, indent=1),
                                                  encoding="utf-8")
    if excluidas:
        print(f"Fuera del panel por idioma: {len(excluidas)} noticias (ver excluidas_idioma.json)")
    return eventos, fichas


def _resumen(eventos, fichas, offline):
    metodos_tema = Counter(n["metodo_tema"] for e in eventos for n in e["noticias"])
    metodos_ficha = Counter(f["generado"]["metodo"] for f in fichas)
    print(f"Modo: {'OFFLINE (sin internet)' if offline else 'con conexión'}")
    print(f"Eventos: {len(eventos)} · temas por método: {dict(metodos_tema)}")
    print(f"Fichas: {len(fichas)} · por método: {dict(metodos_ficha)}")
    print("\nRanking:")
    for e in eventos[:15]:
        p = e["prioridad"]
        print(f"  {p['posicion']:>2}. {p['puntaje']:>5} {p['nivel']:<5} {e['estado_evidencia'][:12]:<12} "
              f"{e['titulo_representativo'][:60]}")


def main():
    parser = argparse.ArgumentParser(description="Núcleo de IA: noticias -> eventos priorizados -> fichas")
    parser.add_argument("--noticias", default=DATOS_EJEMPLO / "noticias_ejemplo.csv")
    parser.add_argument("--indicadores", default=DATOS_EJEMPLO / "indicadores_ejemplo.csv")
    parser.add_argument("--sismos", default=DATOS_EJEMPLO / "eventos_ejemplo.geojson")
    parser.add_argument("--paquete", default=None,
                        help="Carpeta datos/ del equipo A; usa su cargador y la fecha de corte del manifest")
    parser.add_argument("--fecha-corte", default=None,
                        help="Fecha de corte en UTC, ej. 2025-09-30T00:00:00Z (con --paquete se toma del manifest)")
    parser.add_argument("--offline", action="store_true", help="No usar internet (demo, prueba T10)")
    parser.add_argument("--top", type=int, default=None, help="Cuántas fichas generar")
    parser.add_argument("--salida", default=None,
                        help="Carpeta de salida (por defecto artefactos/, o artefactos/ejemplo_corrida/ sin --paquete)")
    args = parser.parse_args()

    eventos, fichas = correr(args.noticias, args.indicadores, args.sismos, args.fecha_corte,
                             args.offline, args.top, args.salida, args.paquete)
    _resumen(eventos, fichas, args.offline)


if __name__ == "__main__":
    main()
