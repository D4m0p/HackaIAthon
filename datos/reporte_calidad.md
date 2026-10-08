# Reporte de calidad del paquete

Fecha de corte (UTC): 2026-10-08T18:41:06Z

## Resumen

| Archivo | Leídas | Válidas | Apartadas |
|---|---|---|---|
| noticias.csv | 442 | 442 | 0 |
| indicadores.csv | 540 | 540 | 0 |
| eventos.geojson | 82 | 82 | 0 |

## Noticias

- Registros únicos: 442 (meta 200, mínimo operativo 100).
- De TVN: 154 (mínimo 20).
- Medios distintos: 66.
- Duplicados por URL fusionados: 12.
- Cobertura efectiva de detección: 2026-09-11T22:45:00Z a 2026-10-08T18:41:07Z.
- Sin fecha de publicación conocida: 263 (GDELT solo informa la detección; no se inventa la publicación).
- Marcadas como recirculadas: 100.

### Por origen

| Concepto | Cantidad |
|---|---|
| gdelt_doc | 288 |
| tvn_rss | 154 |

### Por tema de la consulta de extracción

| Concepto | Cantidad |
|---|---|
| general | 225 |
| sin dato | 154 |
| economia | 63 |

### Por idioma

| Concepto | Cantidad |
|---|---|
| es | 401 |
| en | 24 |
| greek | 10 |
| pt | 2 |
| chinese | 2 |
| thai | 1 |
| arabic | 1 |
| fr | 1 |

### Motivos de rechazo

Ninguno.

### Nulos conservados por campo

| Concepto | Cantidad |
|---|---|
| fecha_publicacion | 263 |
| tema | 154 |
| palabras_clave | 288 |
| seccion | 288 |
| pais_medio | 157 |

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

- Descarga fallida: raw/gdelt/economia_20260918_20260928.json (No se pudo descargar https://api.gdeltproject.org/api/v2/doc/doc?query=panama+%28economy+OR+inflation+OR+employment+OR+investment+OR+econom%C3%ADa+OR+inflaci%C3%B3n+OR+empleo%29&mode=ArtList&format=json&sort=DateDesc&maxrecords=75&startdatetime=20260918184106&enddatetime=20260928184106: HTTP Error 429: Too Many Requests)
- Descarga fallida: raw/gdelt/economia_20260928_20261008.json (pendiente: GDELT limitó las consultas en esta ejecución)
- Descarga fallida: raw/gdelt/logistica_20260908_20260918.json (pendiente: GDELT limitó las consultas en esta ejecución)
- Descarga fallida: raw/gdelt/logistica_20260918_20260928.json (pendiente: GDELT limitó las consultas en esta ejecución)
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
