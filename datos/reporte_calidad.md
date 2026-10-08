# Reporte de calidad del paquete

Fecha de corte (UTC): 2026-10-08T18:41:06Z

## Resumen

| Archivo | Leídas | Válidas | Apartadas |
|---|---|---|---|
| noticias.csv | 599 | 599 | 0 |
| indicadores.csv | 540 | 540 | 0 |
| eventos.geojson | 82 | 82 | 0 |

## Noticias

- Registros únicos: 599 (meta 200, mínimo operativo 100).
- De TVN: 154 (mínimo 20).
- Medios distintos: 175.
- Duplicados por URL fusionados: 79.
- Cobertura efectiva de detección: 2026-09-11T21:30:00Z a 2026-10-08T18:41:07Z.
- Sin fecha de publicación conocida: 396 (GDELT solo informa la detección; no se inventa la publicación).
- Marcadas como recirculadas: 101.

### Por origen

| Concepto | Cantidad |
|---|---|
| gdelt_doc | 445 |
| tvn_rss | 154 |

### Por tema de la consulta de extracción

| Concepto | Cantidad |
|---|---|
| general | 225 |
| economia | 191 |
| sin dato | 154 |
| logistica | 29 |

### Por idioma

| Concepto | Cantidad |
|---|---|
| es | 464 |
| en | 94 |
| el | 13 |
| zh | 7 |
| fr | 3 |
| pt | 3 |
| ko | 2 |
| ru | 2 |
| de | 2 |
| lithuanian | 1 |
| bulgarian | 1 |
| persian | 1 |
| ja | 1 |
| tr | 1 |
| th | 1 |
| ar | 1 |
| ukrainian | 1 |
| indonesian | 1 |

### Motivos de rechazo

Ninguno.

### Nulos conservados por campo

| Concepto | Cantidad |
|---|---|
| fecha_publicacion | 396 |
| tema | 154 |
| palabras_clave | 445 |
| seccion | 445 |
| pais_medio | 163 |

## Indicadores

- Cuadrícula: 540 combinaciones país × indicador × año (6 países, 6 indicadores, 2010 a 2024).
- Con valor: 540. Sin valor (conservadas como nulo): 0.

### Observaciones faltantes por indicador

Ninguno.

### Motivos de rechazo

Ninguno.

## Eventos sísmicos

- Eventos: 82.
- Período: 2024-01-07T01:02:08Z a 2024-12-29T23:00:10Z.
- Magnitud: 3.2 a 5.8.

### Motivos de rechazo

Ninguno.

## Incidencias

- Descarga fallida: raw/gdelt/logistica_20260918_20260928.json (No se pudo descargar https://api.gdeltproject.org/api/v2/doc/doc?query=panama+%28canal+OR+logistics+OR+shipping+OR+port+OR+log%C3%ADstica+OR+puerto%29&mode=ArtList&format=json&sort=DateDesc&maxrecords=75&startdatetime=20260918184106&enddatetime=20260928184106: HTTP Error 429: Too Many Requests)
- Descarga fallida: raw/gdelt/logistica_20260928_20261008.json (pendiente: GDELT limitó las consultas en esta ejecución)
- Descarga fallida: raw/gdelt/turismo_20260908_20260918.json (pendiente: GDELT limitó las consultas en esta ejecución)
- Descarga fallida: raw/gdelt/turismo_20260918_20260928.json (pendiente: GDELT limitó las consultas en esta ejecución)
- Descarga fallida: raw/gdelt/turismo_20260928_20261008.json (pendiente: GDELT limitó las consultas en esta ejecución)
- Descarga fallida: raw/gdelt/eventos_naturales_20260908_20260918.json (pendiente: GDELT limitó las consultas en esta ejecución)
- Descarga fallida: raw/gdelt/eventos_naturales_20260918_20260928.json (pendiente: GDELT limitó las consultas en esta ejecución)
- Descarga fallida: raw/gdelt/eventos_naturales_20260928_20261008.json (pendiente: GDELT limitó las consultas en esta ejecución)
- Descarga fallida: raw/gdelt/tvn_20260908_20260918.json (pendiente: GDELT limitó las consultas en esta ejecución)
- Descarga fallida: raw/gdelt/tvn_20260918_20260928.json (pendiente: GDELT limitó las consultas en esta ejecución)
- Descarga fallida: raw/gdelt/tvn_20260928_20261008.json (pendiente: GDELT limitó las consultas en esta ejecución)
