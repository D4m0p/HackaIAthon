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

## Núcleo de IA (`backend/`)

Toma el paquete de datos y produce la bandeja priorizada y las fichas (etapas 2 a 6 del reto): agrupa las noticias del mismo evento, les asigna tema, las vincula con datos oficiales cuando hay relación sustentada, calcula el puntaje de atención y redacta fichas y borradores con citas. Toda redacción pasa por un validador que bloquea lo que no está respaldado por la evidencia. Nada se publica: cada ficha queda para revisión humana.

### Instalación

Se instala aparte del paquete de datos, que solo usa la biblioteca estándar.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # completar GEMINI_API_KEY (nunca se sube a git)

# Descarga única del modelo de embeddings BAAI/bge-m3 (~2,2 GB)
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"
```

La instalación y la descarga del modelo necesitan internet **una sola vez** (~1 GB de librerías y ~2,2 GB del modelo). Después todo funciona sin conexión. En la máquina de la demo hay que hacerlo antes del evento.

### Ejecutar

```bash
cd backend
python -m nucleo.pipeline --paquete ../datos             # con Gemini
python -m nucleo.pipeline --paquete ../datos --offline   # demo sin internet (T10)
```

Con `--paquete` se usa `ingesta.cargar_paquete()` y la fecha de corte del manifest. Las salidas quedan en `backend/artefactos/`:

| Archivo | Contenido |
|---|---|
| `eventos.json` | Eventos organizados, contextualizados y priorizados, con el puntaje desglosado |
| `fichas.jsonl` | Fichas del top 10 con afirmaciones citadas, borrador y resultado del validador |
| `excluidas_idioma.json` | Noticias fuera del panel por idioma (solo se muestran español e inglés) |

**Sin internet.** Los temas que asigna el LLM y sus redacciones se guardan en `artefactos/` (`temas.json`, `redacciones.json`) junto con los embeddings ya calculados, y se versionan en git. Con `--offline` el resultado es idéntico al de la corrida con conexión. Lo que no esté guardado se resuelve sin LLM: el tema con el clasificador por embeddings y la ficha con una plantilla que solo repite lo que dicen las fuentes, ambos marcados para revisión.

### Pruebas

```bash
cd backend
python -m pytest
```

Desde la raíz, `python -m pytest` corre solo las pruebas del paquete de datos (ver `pytest.ini`). Las pruebas que llaman a Gemini se saltan solas si no hay clave o conexión.

| Prueba | Qué comprueba | Archivo |
|---|---|---|
| T02 | Tres registros del mismo evento: un evento, sin perder fuentes ni triplicar la corroboración | `backend/tests/test_organizar.py` |
| T04 | Una cifra anual del Banco Mundial conserva país, año y unidad y no se presenta como dato de hoy | `backend/tests/test_contextualizar.py` |
| T05 | Dos cifras incompatibles: se muestran ambas y la ficha no elige una | `backend/tests/test_fichas.py`, `test_seguridad.py` |
| T07 | Un titular que da instrucciones no llega al LLM ni cambia el resultado | `backend/tests/test_seguridad.py`, `test_organizar.py` |
| T08 | El puntaje expone sus componentes y la regla; la prioridad no habilita publicar | `backend/tests/test_priorizar.py` |
| T09 | Afirmaciones citadas; el validador bloquea cifras y entidades sin respaldo | `backend/tests/test_fichas.py` |
| T10 | Sin internet el ranking y las fichas son idénticos a la corrida de referencia | `backend/tests/test_offline.py` |

### Módulos

| Módulo | Etapa | Qué hace |
|---|---|---|
| `organizar.py` | 2 | Embeddings locales, temas (Gemini con respaldo) y agrupación híbrida de eventos |
| `contextualizar.py` | 3 | Vincula eventos con Banco Mundial y USGS sin forzar relaciones |
| `priorizar.py` | 4 | P = 30R + 25I + 20U + 15N + 10E y estado de evidencia, independiente del puntaje |
| `fichas.py`, `plantilla.py` | 5 y 6 | Ficha de evidencia y paquete editorial con citas `[ID:campo]` |
| `seguridad.py` | — | Anti-inyección y validador que bloquea contenido sin respaldo |
| `llm.py`, `artefactos.py` | — | Capa única de Gemini con modelos de respaldo; resultados versionados |
| `baseline.py` | — | Versión sin IA (palabras clave) para comparar |
| `config.py` | — | Umbrales, pesos y reglas, con la versión de reglas vigente |

Las limitaciones conocidas están en [`backend/LIMITACIONES.md`](backend/LIMITACIONES.md).
