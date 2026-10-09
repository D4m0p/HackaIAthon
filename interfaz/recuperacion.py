"""Recuperación por palabras (BM25) sobre los eventos del corpus.

Además del puntaje devuelve la cobertura: qué parte de lo que se preguntó aparece
realmente en el documento. Con ella se decide cuándo abstenerse.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from .texto import alternativas, raices_de_documento

K1 = 1.4
B = 0.6


@dataclass
class Coincidencia:
    id: str
    puntaje: float
    cobertura: float            # 0 a 1: peso de los términos de la consulta que el documento contiene
    encontrados: list[str]
    faltantes: list[str]


class Indice:
    def __init__(self, documentos: dict[str, str]):
        self._frecuencias = {id_doc: Counter(raices_de_documento(texto)) for id_doc, texto in documentos.items()}
        self._largo = {id_doc: sum(frecuencias.values()) for id_doc, frecuencias in self._frecuencias.items()}
        total = len(self._frecuencias)
        self._largo_medio = (sum(self._largo.values()) / total) if total else 1.0

    def _documentos_con(self, raices_posibles: frozenset[str]) -> int:
        return sum(1 for frecuencias in self._frecuencias.values() if any(r in frecuencias for r in raices_posibles))

    def _peso(self, raices_posibles: frozenset[str]) -> float:
        """IDF del concepto. Uno que no aparece en ningún documento pesa lo máximo:
        si la consulta lo pide y el corpus no lo tiene, la cobertura debe caer."""
        total = len(self._frecuencias)
        con = self._documentos_con(raices_posibles)
        return math.log(1 + (total - con + 0.5) / (con + 0.5))

    def buscar(self, terminos_consulta: list[str], limite: int = 8) -> list[Coincidencia]:
        conceptos = [(termino, alternativas(termino)) for termino in dict.fromkeys(terminos_consulta)]
        if not conceptos or not self._frecuencias:
            return []
        pesos = {termino: self._peso(posibles) for termino, posibles in conceptos}
        peso_total = sum(pesos.values()) or 1.0

        resultados = []
        for id_doc, frecuencias in self._frecuencias.items():
            puntaje, peso_encontrado, encontrados = 0.0, 0.0, []
            ajuste_largo = 1 - B + B * self._largo[id_doc] / self._largo_medio
            for termino, posibles in conceptos:
                veces = sum(frecuencias.get(r, 0) for r in posibles)
                if not veces:
                    continue
                puntaje += pesos[termino] * veces * (K1 + 1) / (veces + K1 * ajuste_largo)
                peso_encontrado += pesos[termino]
                encontrados.append(termino)
            if encontrados:
                faltantes = [termino for termino, _ in conceptos if termino not in encontrados]
                resultados.append(Coincidencia(id_doc, round(puntaje, 4), round(peso_encontrado / peso_total, 4),
                                               encontrados, faltantes))
        resultados.sort(key=lambda c: (-c.cobertura, -c.puntaje, c.id))
        return resultados[:limite]
