# Pendientes del núcleo de IA (equipo B)

Lista viva: se tacha cuando se completa. Lo que dependa de otra persona dice de quién.

## Validación sin sesgo

- [ ] **Preguntas nuevas para validar las consultas.** Las 15 paráfrasis de
  `eval/benchmark_parafrasis.jsonl` las escribió el mismo equipo que ajustó el prompt y el
  umbral mirándolas, así que el 9 de 9 está sobreajustado. Hace falta que **otra persona del
  equipo** escriba unas 15 preguntas nuevas (10 con respuesta, dichas con otras palabras que
  los titulares, y 5 sin respuesta en el corpus) en el mismo formato, sin mirar el prompt, y
  correr: `python -m interfaz.evaluar <archivo> --ejemplo` desde la raíz con el entorno del núcleo.
- [ ] **Repetir la comparación de consultas sobre el paquete real** (no solo los datos de ejemplo).
- [x] **Evaluación preliminar con juez IA:** `eval/planilla_juez_ia.xlsx`, etiquetada sin ver
  las respuestas del sistema; el reporte lo declara como referencia no humana.
- [ ] **Etiquetas humanas** en `eval/planilla_etiquetas.xlsx` (idealmente dos personas por
  separado). Con una sola copia humana se puede medir también el acuerdo humano–juez IA.
- [ ] **Sobreagrupación:** el juez IA marca 10 de 20 pares agrupados como hechos distintos
  (alianzas de TVN Media, resultados de MLB). Revisar el umbral sin ajustarlo a esas mismas etiquetas.

## Coordinación con otros equipos

- [ ] **Avisar al equipo C** que `interfaz/consulta.py` ahora usa `nucleo/consultar.py`
  (cambios marcados con "Núcleo de IA (equipo B)"); sus 136 pruebas pasan con y sin el núcleo.
- [ ] **Proponer al equipo C** que sus pruebas usen datos propios en vez de
  `artefactos/ejemplo/` (hoy congelado para no romperlas).
- [ ] **Avisar al equipo A** de las observaciones sobre recirculadas del RSS de TVN y el tipo
  de `fecha_original` (mensaje ya redactado).

## Notion

- [x] Aportar a **Plan y decisiones** (LarpeoIntenso → Documentación funcional): backlog,
  10 decisiones justificadas y cronología con commits.
- [ ] Completar **Casos y evidencias** con la revisión humana de las 5 fichas propuestas (equipo C).
- [ ] Completar los bloques "Completar" de **Presentación Pitch Day** (equipo).
- [x] Crear **Pruebas y métricas** en Notion (LarpeoIntenso → Documentación técnica): matriz
  T01–T10, métricas automáticas, comparación de consultas y pruebas fallidas con su corrección.
- [ ] Actualizar esa página con las métricas finales cuando la planilla esté etiquetada
  (`python -m eval.metricas` y copiar `eval/resultados/metricas.md`).

## Mejoras opcionales

- [ ] Agrupar noticias en inglés con su traducción en español (ver `LIMITACIONES.md`).
- [ ] Frases de ejemplo para "otro" en el clasificador de respaldo sin LLM.
