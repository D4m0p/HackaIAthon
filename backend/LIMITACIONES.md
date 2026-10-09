# Limitaciones conocidas del núcleo de IA

Registro de lo que el sistema no hace o hace de forma aproximada, con su impacto y
lo que haría falta para resolverlo. Alimenta la página "Riesgos y ética" de Notion.

## Noticias en otros idiomas

**Qué pasa.** El panel muestra solo noticias en español e inglés
(`config.IDIOMAS_PANEL`). En el paquete v1 quedan fuera 26 de 504 noticias (griego,
chino, portugués, francés y otros), casi todas ajenas a Panamá: fletes marítimos,
bolsa china, política de Brasil. No se borran: se listan en
`artefactos/excluidas_idioma.json` con su motivo.

**Limitación que sigue abierta.** Una noticia en inglés y otra en español sobre el
mismo hecho no se agrupan en un solo evento, porque la agrupación exige al menos una
palabra relevante compartida y esa regla compara palabras en español. En el paquete
v1 son 5 de 43 noticias en inglés, y casi todas son traducciones de notas en español
(newsroompanama.com traduce a La Estrella o Prensa; PressTV e HispanTV son la misma
cadena).

**Impacto.** Esos 5 hechos aparecen dos veces en la bandeja. No inflan la evidencia de
ningún evento, porque cada versión queda en un evento distinto.

**Cómo se resolvería.** Permitir agrupar español con inglés cuando el parecido
semántico es alto (bge-m3 es multilingüe; umbral sugerido 0,75) y contar la traducción
como la **misma procedencia**, no como una confirmación independiente ("una agencia
replicada cuenta como una sola procedencia", sección 4 del reglamento).

## Clasificación sin LLM

**Qué pasa.** Si un titular no tiene tema guardado y no hay LLM disponible, el tema lo
asigna un clasificador por embeddings, menos preciso (con datos reales llegó a poner
noticias de fútbol en turismo). La ficha queda marcada: "tema asignado por respaldo,
confirmar en la revisión".

**Cómo se resolvería.** Medirlo con la planilla etiquetada (`eval/`) y, si conviene,
entrenar un clasificador sobre esas etiquetas.

## Calidad de la clasificación y la agrupación

La versión `temas-v2` se ajustó al ver errores con los datos reales. Medida contra la
planilla revisada (`eval/planilla_revisada.xlsx`): macro-F1 de temas 0,767 con LLM frente a
0,564 de palabras clave, y Precision@5 de 4 de 5. Quedan errores: procesos judiciales de
otros países (Duterte, la JEP de Colombia) siguen saliendo como "regulación", aunque no
llegan al top-10. La agrupación **sobreagrupa**: 10 de 20 pares agrupados son hechos
distintos del mismo tema. La medición viene de una sola persona revisora; falta una
segunda para medir el acuerdo.

## Sismos sin casos reales

USGS aporta sismos de 2024 y las noticias del paquete son de 2026: el vínculo noticia ↔
sismo funciona (probado con datos sintéticos), pero en este paquete no hay casos reales.

## Contradicciones

El detector de cifras en conflicto solo compara porcentajes que aparecen en los
titulares de un mismo evento. Otras contradicciones las tiene que notar la revisión humana.

## Dependencia de planes gratuitos de LLM

Gemini y Groq se usan en sus planes gratuitos, con cuotas bajas (en una jornada de
desarrollo Gemini rechazó 177 llamadas por cupo agotado). La demo no depende de ellos
porque todo sale de los artefactos versionados, pero regenerar resultados puede tener
que esperar a que se renueve la cuota.
