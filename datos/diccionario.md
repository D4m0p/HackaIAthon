# Diccionario de datos · Panamá · Señales y Evidencias v1

Todos los archivos están en UTF-8. Las fechas son ISO 8601 en UTC (`2026-10-08T18:41:06Z`); la interfaz las muestra en hora de Panamá con `ingesta.a_hora_panama`. Una celda vacía significa "dato no disponible": nunca se sustituye por cero.

## processed/noticias.csv

Una fila por URL única. Solo titulares y metadatos: no hay cuerpo de artículo ni descripción.

| Campo | Tipo | Nulo | Descripción |
|---|---|---|---|
| id_noticia | texto | no | `N-` más 12 caracteres del SHA-1 de la URL normalizada. No cambia entre extracciones. |
| titulo | texto | no | Titular tal como lo entrega la fuente. |
| url | texto | no | URL normalizada: sin fragmento, sin parámetros de rastreo, sin barra final. |
| medio | texto | no | `TVN` o el dominio del medio. |
| idioma | texto | sí | Código ISO 639-1 (`es`, `en`…). |
| fecha_publicacion | fecha | sí | Cuándo lo publicó el medio. En TVN viene del RSS. En GDELT solo se llena si la URL trae la fecha; si no, queda vacía. |
| fecha_deteccion | fecha | sí | Cuándo se detectó: `seendate` de GDELT o el momento de lectura del RSS. **No es la fecha de publicación.** |
| fecha_extraccion | fecha | no | Cuándo se descargó la fuente. |
| tema | texto | sí | Tema de la consulta con la que GDELT devolvió la nota (`general`, `economia`, `logistica`, `turismo`, `eventos_naturales`, `tvn`). Es una pista de extracción, no una clasificación. Vacío en TVN RSS. |
| origen | texto | no | `tvn_rss` o `gdelt_doc`. |
| alcance_texto | texto | no | Siempre `titular_y_metadatos`. Toda salida basada en estas filas debe decir "basado únicamente en titular/metadatos". |
| palabras_clave | texto | sí | Etiquetas del RSS de TVN, separadas por coma. |
| seccion | texto | sí | Sección de TVN según la URL (`nacionales`, `economia`…). |
| pais_medio | texto | sí | País del medio según GDELT. |
| recirculada | booleano | no | `true` si `fecha_original` precede a la detección por más de 7 días. No debe presentarse como hecho nuevo. |
| fecha_original | fecha | sí | Fecha más antigua conocida del contenido. Es la que debe mostrarse (`ingesta.fecha_para_mostrar`). |

## processed/indicadores.csv

Cuadrícula completa de 6 países × 6 indicadores × 15 años (2010–2024) = 540 filas. Son datos **anuales**: no describen la situación de hoy.

| Campo | Tipo | Nulo | Descripción |
|---|---|---|---|
| pais_iso3 | texto | no | `PAN`, `CRI`, `COL`, `DOM`, `MEX`, `GTM`. |
| indicador_id | texto | no | Código del Banco Mundial. |
| anio | entero | no | Año de referencia del dato. |
| valor | decimal | sí | Vacío si el Banco Mundial no publica la observación. |
| unidad | texto | no | Unidad del valor (ver tabla siguiente). |
| fuente_url | texto | no | Página del indicador para ese país. |
| fecha_extraccion | fecha | no | Cuándo se descargó. |
| licencia | texto | no | `CC BY 4.0`. |
| indicador_nombre | texto | no | Nombre en español. |
| actualizacion_fuente | texto | sí | Última actualización declarada por la API. |

| indicador_id | Nombre | Unidad |
|---|---|---|
| NY.GDP.MKTP.KD.ZG | Crecimiento del PIB | % anual |
| FP.CPI.TOTL.ZG | Inflación, precios al consumidor | % anual |
| SL.UEM.TOTL.ZS | Desempleo total (estimación modelada OIT) | % de la población activa |
| SP.POP.TOTL | Población total | personas |
| IT.NET.USER.ZS | Personas que usan internet | % de la población |
| NE.EXP.GNFS.ZS | Exportaciones de bienes y servicios | % del PIB |

## processed/eventos.geojson

`FeatureCollection` con los sismos de 2024 de magnitud ≥ 3 en la caja latitud 5 a 12, longitud −86 a −76. **La caja no equivale al territorio de Panamá** e incluye eventos de países vecinos y del mar. Solo sustenta hechos sísmicos: no es evidencia de inundaciones ni de pérdidas económicas.

| Propiedad | Tipo | Nulo | Descripción |
|---|---|---|---|
| id | texto | no | Identificador de USGS. |
| magnitude | decimal | no | Magnitud. |
| time | fecha | no | Momento del sismo. |
| updated | fecha | sí | Última revisión del registro en USGS. |
| longitude, latitude | decimal | no | Coordenadas en grados. |
| depth | decimal | sí | Profundidad en km. |
| place | texto | sí | Descripción del lugar, en inglés, tal como la da USGS. |
| status | texto | sí | `reviewed` o `automatic`. |
| url | texto | no | Página del evento. |
| magnitude_type | texto | sí | Tipo de magnitud (`mb`, `mww`…). |

## Otros archivos

| Archivo | Contenido |
|---|---|
| `manifest.json` | Versión, fecha de corte, consultas ejecutadas, cantidad de registros, condiciones de uso, SHA-256 y transformaciones. |
| `fuentes.json` | Catálogo de las cuatro fuentes, con los campos de la página "Catálogo de datos" de Notion. |
| `reporte_calidad.md` / `.json` | Qué se leyó, qué se apartó y por qué; nulos por campo y cobertura efectiva. |
| `exclusiones.json` | Noticias retiradas por decisión del equipo, con ID y motivo. El manifest las cuenta en `registros_excluidos`. |
| `processed/rechazados.json` | Registros que no pasaron la validación, con su motivo. |
| `raw/` | Respuestas originales de las fuentes y `extraccion.json`, el registro de cada descarga. El RSS de TVN no se incluye porque trae extractos e imágenes; su huella y su URL sí quedan registradas. |
