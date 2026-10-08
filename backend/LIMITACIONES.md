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
