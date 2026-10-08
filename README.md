# De la señal a la decisión

Copiloto de inteligencia informativa para TVN Media: convierte noticias públicas e indicadores oficiales en una bandeja de temas priorizados, fichas de evidencia y borradores para revisión humana.

hackIAthon · cuarta edición · modalidad editorial.

## Datos: paquete "Panamá · Señales y Evidencias v1"

El prototipo trabaja sobre un paquete congelado de datos públicos que está en `datos/`. La demo no necesita internet.

| Archivo | Fuente | Contenido |
|---|---|---|
| `datos/processed/noticias.csv` | RSS de TVN y GDELT DOC 2.0 | Titulares y metadatos de los 30 días previos al corte |
| `datos/processed/indicadores.csv` | Banco Mundial | 6 países, 6 indicadores, 2010–2024 |
| `datos/processed/eventos.geojson` | USGS | Sismos de 2024, magnitud ≥ 3, caja regional |
| `datos/manifest.json` | — | Fecha de corte, consultas, SHA-256 y transformaciones |
| `datos/fuentes.json` | — | Catálogo de fuentes y condiciones de uso |
| `datos/reporte_calidad.md` | — | Registros válidos, apartados y nulos |
| `datos/diccionario.md` | — | Significado de cada campo |

### Cargar el paquete

```python
from ingesta import cargar_paquete

paquete = cargar_paquete()
paquete.noticias      # lista de diccionarios
paquete.indicadores
paquete.eventos
paquete.reporte       # reporte de calidad
paquete.rechazados    # filas apartadas, con su motivo
paquete.integro       # False si un archivo falta o no coincide con el manifest
paquete.incidencias   # qué falló, en texto
```

La carga no abre conexiones y nunca se detiene por datos defectuosos: una fila inválida se aparta con su motivo, y un archivo ausente o alterado se anota en `incidencias` mientras el resto se carga.

Dos reglas para quien use las noticias:

- `fecha_deteccion` no es la fecha de publicación. Para mostrar una fecha use `ingesta.fecha_para_mostrar(noticia)` y, para pasarla a hora de Panamá, `ingesta.a_hora_panama(fecha)`.
- Una noticia con `recirculada = true` es contenido antiguo que volvió a circular: no debe presentarse como un hecho nuevo.

### Reconstruir el paquete

Solo hace falta para generar una versión nueva; usa internet y la biblioteca estándar de Python.

```bash
python -m ingesta.snapshot                 # descarga las cuatro fuentes y procesa
python -m ingesta.snapshot --reanudar      # repite solo las descargas que fallaron
python -m ingesta.snapshot --sin-descarga  # reprocesa datos/raw sin usar internet
```

### Condiciones de uso de las fuentes

- **TVN:** el RSS es público pero no declara licencia abierta. Se guardan titular, URL, fecha y palabras clave. No se copian descripciones, cuerpos, imágenes ni videos.
- **GDELT:** uso abierto citando a The GDELT Project. No transfiere derechos sobre los artículos enlazados.
- **Banco Mundial:** CC BY 4.0.
- **USGS:** dominio público; se cita a USGS como fuente.

## Instalación y pruebas

Requiere Python 3.10 o superior.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest
```

| Prueba | Qué comprueba | Archivo |
|---|---|---|
| T01 | Fechas inválidas y nulos: se separan los errores y la carga continúa | `tests/test_t01_carga_con_errores.py` |
| T03 | Una noticia antigua recirculada conserva su fecha original | `tests/test_t03_noticia_recirculada.py` |
| T10 | La demo funciona sin internet a partir del snapshot | `tests/test_t10_sin_internet.py` |
