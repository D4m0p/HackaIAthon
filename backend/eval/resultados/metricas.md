# Métricas del núcleo de IA

Calculadas con `python -m eval.metricas` sobre la corrida del paquete real. Numerador, denominador y fallos visibles: nada se esconde en un promedio.

## Fichas y citas

| Métrica | Resultado |
|---|---|
| Fichas | 10 (por método: {'llm': 10}) |
| Fichas bloqueadas por el validador | 0 (rescatadas con corrección: 0) |
| Cobertura de citas: afirmaciones con cita válida | 13 de 13 (100%) |
| Oraciones citadas del borrador con cifras respaldadas | 11 de 11 (100%) |

## Eficiencia y costo

397 llamadas reales al LLM (172 exitosas) y 229 respondidas desde la caché. Fallos por código: {'503': 13, '429': 197, '429_minuto': 10, '504': 1, 'sin_clave': 4}. Tokens: 502,240. Costo: 0 USD (Planes gratuitos de Gemini y Groq: costo 0. Se reportan los tokens para estimarlo con precios pagos.)

| Tarea | Llamadas | Mediana (s) | p95 (s) | Tokens promedio |
|---|---|---|---|---|
| clasificar_temas | 29 | 6.5 | 12.71 | 4803 |
| consulta | 45 | 0.89 | 1.93 | 1026 |
| consulta_correccion | 3 | 1.11 | 1.3 | 1159 |
| ficha | 71 | 7.19 | 29.44 | 3157 |
| ficha_correccion | 10 | 3.8 | 35.34 | 4000 |
| ficha_reintento | 14 | 3.79 | 23.14 | 3513 |

> **Referencia:** revisada fila por fila por Ariel Jimenez (equipo C) sobre una propuesta prellenada, sin cambios.

## Clasificación de temas (contra las etiquetas de referencia)

100 titulares etiquetados.

| Método | Macro-F1 | Exactitud |
|---|---|---|
| LLM | 0.767 | 85 de 100 (85%) |
| Embeddings (respaldo sin LLM) | 0.409 | 70 de 100 (70%) |
| Palabras clave (baseline) | 0.564 | 79 de 100 (79%) |

Relación con Panamá (LLM): 92 de 100 (92%).

## Ranking (Precision@k)

- precision_5: 4 de 5 (80%)
- precision_10: 8 de 10 (80%)
- precision_15: 12 de 15 (80%)
- Nota: Exploratoria si quien etiqueta no es editor/a de TVN (sección 9.1).

## Agrupación de noticias

- precision: 10 de 20 (50%)
- recall: 10 de 12 (83%)
- Nota: Recall sobre la muestra de pares: incluye solo pares separados parecidos (similitud >= 0,60).

## Validez de sustento

- validez: 15 de 20 (75%)

## Acuerdo entre personas (kappa de Cohen)

Pendiente: se necesita una segunda persona (pasar dos planillas).
