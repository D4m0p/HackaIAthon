# Consultas: BM25 (baseline) vs búsqueda híbrida

Evaluador: interfaz/evaluar.py (equipo C) sobre los datos de ejemplo sintéticos. Fecha: 2026-10-08.

- **BM25**: motor de consultas de la interfaz tal como estaba (búsqueda por palabras con sinónimos).
- **Híbrida**: el mismo motor más nucleo/consultar.py: si BM25 no encuentra respuesta, los 3 eventos más parecidos por significado (bge-m3, parecido mayor o igual a 0,35) se le pasan al LLM, que decide si responden la pregunta; su texto pasa por el validador del núcleo. Sin LLM se mantiene la abstención.

## Benchmark del equipo C (40 consultas)

| Métrica | BM25 | Híbrida |
|---|---|---|
| Respuesta sustentada | 20 de 20 | 20 de 20 |
| Contradicción: todas las versiones o abstención | 6 de 6 | 6 de 6 |
| Sin respuesta: abstención correcta | 8 de 8 | 8 de 8 |
| Adversarial: rechazo o abstención | 6 de 6 | 6 de 6 |
| Cobertura de citas | 43 de 43 | 43 de 43 |
| Tiempo mediana / p95 | 0.2 ms / 1.6 ms | 0.6 ms / 2537.2 ms |

Resultado: la búsqueda híbrida no rompe nada (40 de 40 en ambos).

## Paráfrasis (15 consultas, benchmark_parafrasis.jsonl)

Preguntas sobre los mismos hechos con otras palabras ("¿Tembló la tierra en el occidente del país?" en lugar de "sismo en Chiriquí") y 5 sin respuesta en el corpus.

| Métrica | BM25 | Híbrida |
|---|---|---|
| Respuesta sustentada | 0 de 9 | 9 de 9 |
| Contradicción: todas las versiones o abstención | 1 de 1 | 1 de 1 |
| Sin respuesta: abstención correcta | 5 de 5 | 5 de 5 |
| Adversarial: rechazo o abstención | — | — |
| Cobertura de citas | 0 de 0 | 19 de 19 |
| Tiempo mediana / p95 | 0.2 ms / 9.5 ms | 1152.1 ms / 11000.5 ms |

## Límites de esta medición

- Las 15 paráfrasis las escribió el mismo equipo que ajustó el prompt y el umbral mirándolas (primera corrida: 4 de 9 sustentadas; tras ajustar: 9 de 9). El resultado está sobreajustado: hace falta validarlo con preguntas nuevas escritas por otra persona.
- Son datos sintéticos (19 noticias). Falta repetirlo sobre el paquete real.
- La híbrida tarda más (llamada al LLM): mediana de ~1 s, p95 de ~11 s, dentro de la meta de mediana de 15 s.
