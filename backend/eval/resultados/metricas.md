# Métricas del núcleo de IA

Calculadas con `python -m eval.metricas` sobre la corrida del paquete real. Numerador, denominador y fallos visibles: nada se esconde en un promedio.

## Fichas y citas

| Métrica | Resultado |
|---|---|
| Fichas | 10 (por método: {'llm': 10}) |
| Fichas bloqueadas por el validador | 0 (rescatadas con corrección: 2) |
| Cobertura de citas: afirmaciones con cita válida | 14 de 14 (100%) |
| Oraciones citadas del borrador con cifras respaldadas | 16 de 16 (100%) |

## Eficiencia y costo

351 llamadas reales al LLM (136 exitosas) y 36 respondidas desde la caché. Fallos por código: {'503': 13, '429': 191, '429_minuto': 6, '504': 1, 'sin_clave': 4}. Tokens: 402,263. Costo: 0 USD (Planes gratuitos de Gemini y Groq: costo 0. Se reportan los tokens para estimarlo con precios pagos.)

| Tarea | Llamadas | Mediana (s) | p95 (s) | Tokens promedio |
|---|---|---|---|---|
| clasificar_temas | 29 | 6.5 | 12.71 | 4803 |
| consulta | 41 | 0.88 | 1.79 | 1023 |
| consulta_correccion | 2 | 1.06 | 1.3 | 1144 |
| ficha | 48 | 7.79 | 22.0 | 3331 |
| ficha_correccion | 6 | 3.65 | 25.15 | 4068 |
| ficha_reintento | 10 | 3.59 | 13.19 | 3442 |

## Clasificación de temas (contra etiquetas humanas)

Pendiente: hoja Etiquetas sin la columna tema completa.

## Ranking (Precision@k)

Pendiente: hoja Agenda sin etiquetar.

## Agrupación de noticias

Pendiente: hoja Pares sin etiquetar.

## Validez de sustento

Pendiente: hoja Afirmaciones sin etiquetar.

## Acuerdo entre personas (kappa de Cohen)

Pendiente: se necesita una segunda persona (pasar dos planillas).
