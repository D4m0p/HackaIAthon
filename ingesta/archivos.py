"""Lectura y escritura de los archivos del paquete, siempre en UTF-8."""

from __future__ import annotations

import csv
import json
from pathlib import Path

VERDADERO, FALSO = "true", "false"


def _a_texto(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return VERDADERO if valor else FALSO
    return str(valor)


def escribir_csv(ruta: Path, filas: list[dict], campos: list[str]) -> None:
    """Escribe el CSV con los nulos como celda vacía (nunca como cero)."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo, lineterminator="\n")
        escritor.writerow(campos)
        for fila in filas:
            escritor.writerow([_a_texto(fila.get(campo)) for campo in campos])


def leer_csv(ruta: Path) -> list[dict]:
    """Lee el CSV devolviendo None en las celdas vacías."""
    with open(ruta, encoding="utf-8-sig", newline="") as archivo:
        return [
            {campo: (valor if valor not in ("", None) else None) for campo, valor in fila.items() if campo}
            for fila in csv.DictReader(archivo)
        ]


def escribir_json(ruta: Path, contenido) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(contenido, archivo, ensure_ascii=False, indent=2)
        archivo.write("\n")


def leer_json(ruta: Path):
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


def a_booleano(valor):
    if isinstance(valor, str) and valor.strip().lower() in (VERDADERO, FALSO):
        return valor.strip().lower() == VERDADERO
    return valor


def a_entero(valor):
    """Convierte a entero si el texto lo permite; si no, lo deja para que la validación lo reporte."""
    if isinstance(valor, str):
        try:
            return int(valor.strip())
        except ValueError:
            return valor
    return valor


def a_decimal(valor):
    if isinstance(valor, str):
        try:
            return float(valor.strip())
        except ValueError:
            return valor
    return valor
