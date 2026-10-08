"""
Corre el núcleo de IA de punta a punta con un solo comando.

    python -m nucleo.pipeline --fecha-corte 2025-09-30T00:00:00Z
    python -m nucleo.pipeline --fecha-corte 2025-09-30T00:00:00Z --offline

Con --offline no se usa internet en absoluto: los temas y las redacciones salen
de artefactos/ (versionados en git) y lo que falte se resuelve con el respaldo
local. Es el modo para la demo (prueba T10).

Salidas (en --salida, por defecto artefactos/):
- eventos.json   eventos organizados, contextualizados y priorizados
- fichas.jsonl   fichas del top-N (formato del contrato de datos, sección 7)
"""

import argparse
import json
import os
from collections import Counter
from pathlib import Path

CARPETA_BACKEND = Path(__file__).parent.parent
DATOS_EJEMPLO = CARPETA_BACKEND / "datos_ejemplo"


def correr(noticias_csv, indicadores_csv, sismos_geojson, fecha_corte,
           offline=False, top_n=None, carpeta_salida=None):
    if offline:
        # Debe definirse ANTES de cargar el modelo de embeddings: impide descargas
        os.environ["HF_HUB_OFFLINE"] = "1"

    from nucleo import config
    from nucleo.contextualizar import cargar_indicadores, cargar_sismos, contextualizar
    from nucleo.fichas import generar_fichas, guardar_fichas
    from nucleo.organizar import cargar_noticias, organizar
    from nucleo.priorizar import priorizar

    usar_llm = not offline
    eventos = organizar(cargar_noticias(noticias_csv), usar_llm=usar_llm)
    contextualizar(eventos, cargar_indicadores(indicadores_csv), cargar_sismos(sismos_geojson))
    priorizar(eventos, fecha_corte)
    fichas = generar_fichas(eventos, top_n or config.FICHAS_TOP_N, usar_llm=usar_llm)

    salida = Path(carpeta_salida or CARPETA_BACKEND / config.CARPETA_ARTEFACTOS)
    salida.mkdir(exist_ok=True)
    (salida / "eventos.json").write_text(json.dumps(eventos, ensure_ascii=False, indent=1, default=str),
                                         encoding="utf-8")
    guardar_fichas(fichas, salida / "fichas.jsonl")
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
    parser.add_argument("--fecha-corte", required=True,
                        help="Fecha de corte del snapshot en UTC (manifest.json), ej. 2025-09-30T00:00:00Z")
    parser.add_argument("--offline", action="store_true", help="No usar internet (demo, prueba T10)")
    parser.add_argument("--top", type=int, default=None, help="Cuántas fichas generar")
    parser.add_argument("--salida", default=None, help="Carpeta de salida (por defecto artefactos/)")
    args = parser.parse_args()

    eventos, fichas = correr(args.noticias, args.indicadores, args.sismos, args.fecha_corte,
                             args.offline, args.top, args.salida)
    _resumen(eventos, fichas, args.offline)


if __name__ == "__main__":
    main()
