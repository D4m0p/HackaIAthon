"""Corre un benchmark de consultas y reporta las métricas de la sección 9.1 del reto.

    python -m interfaz.evaluar interfaz/benchmark_ejemplo.jsonl --ejemplo
    python -m interfaz.evaluar ruta/benchmark.jsonl --salida resultados/

Cada línea del benchmark es un JSON con la consulta («consulta», «pregunta» o «query») y,
si se conoce, su tipo: «sustentada», «contradiccion», «sin_respuesta» o «adversarial».
Se guarda la salida completa de cada consulta y se reportan numerador y denominador:
los fallos quedan listados, no escondidos en un promedio.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from . import fuentes
from .consulta import Motor, verificar

TIPOS = ("sustentada", "contradiccion", "sin_respuesta", "adversarial")


def _leer(ruta: Path) -> list[dict]:
    casos = []
    for numero, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), start=1):
        if not linea.strip():
            continue
        caso = json.loads(linea)
        consulta = caso.get("consulta") or caso.get("pregunta") or caso.get("query")
        if consulta:
            casos.append({"id": str(caso.get("id") or numero), "tipo": caso.get("tipo"), "consulta": consulta})
    return casos


def _cumple(tipo: str | None, respuesta: dict) -> bool | None:
    """Si la respuesta es la esperada para ese tipo de consulta. None cuando no hay etiqueta."""
    if tipo == "sustentada":
        return not respuesta["abstencion"] and bool(respuesta["afirmaciones"] or respuesta["casos"] or respuesta["reglas"])
    if tipo == "contradiccion":
        return len(respuesta["versiones"]) >= 2 or respuesta["abstencion"]
    if tipo == "sin_respuesta":
        return respuesta["abstencion"]
    if tipo == "adversarial":
        return respuesta["tipo"] in ("rechazo", "fuera_de_alcance") or respuesta["abstencion"]
    return None


def evaluar(motor: Motor, casos: list[dict]) -> tuple[list[dict], dict]:
    resultados = []
    for caso in casos:
        respuesta = motor.responder(caso["consulta"])
        validas, _ = verificar(respuesta["afirmaciones"], respuesta["evidencia"])
        resultados.append({**caso, "cumple": _cumple(caso["tipo"], respuesta), "afirmaciones": len(respuesta["afirmaciones"]),
                           "afirmaciones_con_cita_valida": len(validas), "respuesta": respuesta})

    def razon(tipo: str) -> dict:
        del_tipo = [r for r in resultados if r["tipo"] == tipo]
        return {"cumplen": sum(1 for r in del_tipo if r["cumple"]), "total": len(del_tipo),
                "fallos": [f"{r['id']}: {r['consulta']}" for r in del_tipo if not r["cumple"]]}

    tiempos = sorted(r["respuesta"]["tiempo_ms"] for r in resultados)
    sustentadas = [r for r in resultados if r["tipo"] == "sustentada"]
    resumen = {
        "consultas": len(resultados),
        "por_tipo": {tipo: razon(tipo) for tipo in TIPOS},
        "sin_etiqueta": sum(1 for r in resultados if r["tipo"] not in TIPOS),
        "cobertura_de_citas": {"con_cita_valida": sum(r["afirmaciones_con_cita_valida"] for r in resultados),
                               "emitidas": sum(r["afirmaciones"] for r in resultados)},
        "abstenciones_incorrectas": {"cantidad": sum(1 for r in sustentadas if r["respuesta"]["abstencion"]),
                                     "de_respondibles": len(sustentadas)},
        "tiempo_ms": {"mediana": round(statistics.median(tiempos), 1) if tiempos else None,
                      "p95": tiempos[min(len(tiempos) - 1, int(len(tiempos) * 0.95))] if tiempos else None},
    }
    return resultados, resumen


def a_markdown(resumen: dict, origen: str) -> str:
    """El resumen como tabla, para pegar en la página «Pruebas y métricas» de Notion."""
    nombres = {"sustentada": "Respuesta sustentada", "contradiccion": "Contradicción: muestra las versiones o se abstiene",
               "sin_respuesta": "Sin respuesta: abstención correcta", "adversarial": "Adversarial: rechazo o abstención"}
    citas, tiempo, malas = resumen["cobertura_de_citas"], resumen["tiempo_ms"], resumen["abstenciones_incorrectas"]
    lineas = [f"## Evaluación de consultas · {origen}", "", f"{resumen['consultas']} consultas.", "",
              "| Métrica | Resultado | Fallos |", "|---|---|---|"]
    for tipo in TIPOS:
        dato = resumen["por_tipo"][tipo]
        if dato["total"]:
            lineas.append(f"| {nombres[tipo]} | {dato['cumplen']} de {dato['total']} | {'; '.join(dato['fallos']) or 'ninguno'} |")
    lineas += [
        f"| Cobertura de citas | {citas['con_cita_valida']} de {citas['emitidas']} afirmaciones emitidas | — |",
        f"| Abstenciones incorrectas | {malas['cantidad']} de {malas['de_respondibles']} preguntas respondibles | — |",
        f"| Tiempo por consulta | mediana {tiempo['mediana']} ms · p95 {tiempo['p95']} ms | — |",
    ]
    if resumen["sin_etiqueta"]:
        lineas.append(f"| Consultas sin etiqueta de tipo | {resumen['sin_etiqueta']} | — |")
    return "\n".join(lineas) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m interfaz.evaluar", description="Benchmark de consultas")
    parser.add_argument("benchmark", type=Path)
    parser.add_argument("--ejemplo", action="store_true", help="Evaluar sobre los datos de ejemplo sintéticos")
    parser.add_argument("--salida", type=Path, default=None, help="Carpeta donde guardar resultados.jsonl y resumen.md")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    corpus = fuentes.cargar("ejemplo" if args.ejemplo else "auto")
    resultados, resumen = evaluar(Motor(corpus), _leer(args.benchmark))
    informe = a_markdown(resumen, f"{args.benchmark.name} sobre datos {'de ejemplo' if corpus.modo == 'ejemplo' else 'reales'}")
    print(informe)
    if args.salida:
        args.salida.mkdir(parents=True, exist_ok=True)
        with open(args.salida / "resultados.jsonl", "w", encoding="utf-8") as archivo:
            for resultado in resultados:
                archivo.write(json.dumps(resultado, ensure_ascii=False) + "\n")
        (args.salida / "resumen.md").write_text(informe, encoding="utf-8")
        (args.salida / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Salidas guardadas en {args.salida}")


if __name__ == "__main__":
    main()
