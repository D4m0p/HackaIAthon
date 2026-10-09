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
cp .env.example .env    # completar GEMINI_API_KEY y GROQ_API_KEY (nunca se suben a git)

# Descarga única del modelo de embeddings BAAI/bge-m3 (~2,2 GB)
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"
```

La instalación y la descarga del modelo necesitan internet **una sola vez** (~1 GB de librerías y ~2,2 GB del modelo). Después todo funciona sin conexión. En la máquina de la demo hay que hacerlo antes del evento.

**Proveedores de LLM (planes gratuitos).** Se usan en cascada: Gemini (`gemini-3.8-flash` y `gemini-3.5-flash` para fichas, `gemini-3.5-flash-lite` para temas) y, si Gemini no tiene cuota, Groq (`openai/gpt-oss-120b` y `qwen/qwen3.8-27b`). Claves gratuitas en [aistudio.google.com/apikey](https://aistudio.google.com/apikey) y [console.groq.com/keys](https://console.groq.com/keys). Si falta una clave, ese proveedor se salta sin error. Un modelo con el cupo diario agotado no se reintenta en esa ejecución; ante el límite por minuto de Groq se espera y se reintenta. Cada tema y cada ficha registran qué modelo los generó.

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

**Cómo decide.** El LLM asigna a cada titular un tema y su relación con Panamá (directa, indirecta o ninguna), con definiciones que dicen qué queda fuera de cada tema (versión `temas-v2` en `config.py`); esa relación alimenta la relevancia R del puntaje. Agrupación, contexto oficial, puntaje y estado de evidencia son reglas sin LLM. Si el validador bloquea una ficha redactada por el LLM, se le pide una corrección con los motivos exactos y se usa solo si mejora; si no, la ficha queda en "requiere evidencia" con sus motivos visibles.

**Sin internet.** Los temas que asigna el LLM y sus redacciones se guardan en `artefactos/` (`temas.json`, `redacciones.json`) junto con los embeddings ya calculados, y se versionan en git. Con `--offline` el resultado es idéntico al de la corrida con conexión. Lo que no esté guardado se resuelve sin LLM: el tema con el clasificador por embeddings y la ficha con una plantilla que solo repite lo que dicen las fuentes, ambos marcados para revisión.

**Datos de ejemplo.** Sin `--paquete`, el pipeline usa los datos sintéticos de `backend/datos_ejemplo/` (hay que indicar la fecha de corte) y escribe en `artefactos/ejemplo_corrida/`:

```bash
python -m nucleo.pipeline --fecha-corte 2025-09-30T00:00:00Z
```

`artefactos/ejemplo/` es otra cosa: una salida **congelada** que usan las pruebas de la interfaz; el pipeline no la toca (ver su `LEEME.md`).

### Evaluación

`backend/eval/planilla_etiquetas.xlsx` tiene 100 titulares reales sorteados con semilla fija para etiquetar a mano, a ciegas: tema, relación con Panamá y si merece estar en la agenda de TVN. Esas etiquetas son la referencia para medir macro-F1 de temas (LLM, embeddings y palabras clave) y Precision@5 del ranking. Para regenerarla, desde `backend/`: `python -m eval.crear_planilla`.

### Pruebas

```bash
cd backend
python -m pytest
```

Desde la raíz, `python -m pytest` corre las pruebas del paquete de datos y las de la interfaz, que solo usan la biblioteca estándar (ver `pytest.ini`); las del núcleo se corren aquí. Para cuidar la cuota gratuita de los LLM, las pruebas **no llaman al LLM por defecto**: revisan los resultados ya guardados en `artefactos/`. Con `PROBAR_LLM=1 python -m pytest` se generan los que falten.

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
| `organizar.py` | 2 | Filtro de idioma, embeddings locales, tema y relación con Panamá (LLM con respaldo) y agrupación híbrida de eventos |
| `contextualizar.py` | 3 | Vincula eventos con Banco Mundial y USGS sin forzar relaciones |
| `priorizar.py` | 4 | P = 30R + 25I + 20U + 15N + 10E y estado de evidencia, independiente del puntaje |
| `fichas.py`, `plantilla.py` | 5 y 6 | Ficha de evidencia y paquete editorial con citas `[ID:campo]`; corrección automática si el validador bloquea |
| `seguridad.py` | — | Anti-inyección y validador que bloquea contenido sin respaldo |
| `llm.py`, `artefactos.py` | — | Capa única de LLM (Gemini y Groq en cascada, con verificación del esquema); resultados versionados |
| `pipeline.py` | — | Corre todo con un comando; `--paquete` usa el cargador del equipo A, `--offline` no usa internet |
| `eval/crear_planilla.py` | — | Genera la planilla de etiquetado humano |
| `baseline.py` | — | Versión sin IA (palabras clave) para comparar |
| `config.py` | — | Umbrales, pesos y reglas, con la versión de reglas vigente |

Las limitaciones conocidas están en [`backend/LIMITACIONES.md`](backend/LIMITACIONES.md).

## Interfaz y revisión (`interfaz/`)

La pantalla del prototipo y la etapa 7 del reto: muestra la bandeja priorizada y la ficha de cada caso, responde consultas en español con cita por afirmación, y registra la decisión humana (aceptar, corregir o descartar) en una bitácora lista para Notion. No recalcula nada: lee lo que producen el paquete de datos y el núcleo de IA.

### Ejecutar

No hay nada que instalar: solo usa la biblioteca estándar de Python y funciona sin internet.

```bash
python -m interfaz              # abre http://localhost:8765
python -m interfaz --ejemplo    # datos de ejemplo sintéticos, con un registro aparte
```

Sin opciones lee `backend/artefactos/eventos.json` y `fichas.jsonl`, es decir, la corrida del núcleo sobre el paquete real. Si esa corrida todavía no existe, muestra los datos de ejemplo de `backend/artefactos/ejemplo/` y lo avisa en pantalla. Otras opciones: `--puerto`, `--sin-navegador`, `--artefactos` y `--datos`.

Las decisiones de revisión se guardan en `interfaz/estado/real/` o en `interfaz/estado/ejemplo/` (fuera de git). Lo que se practica con los datos de ejemplo nunca se mezcla con el registro del reto.

| Vista | Etapa | Qué muestra |
|---|---|---|
| Bandeja | 4 | Casos ordenados por puntaje, con sus cinco componentes, el estado de evidencia aparte y el estado de revisión |
| Ficha | 5 y 6 | Qué se reporta, quién lo reporta por procedencia independiente, afirmaciones con cita, cifras en conflicto, contexto oficial, pendientes y el paquete editorial |
| Ficha · revisión | 7 | Tomar, pedir evidencia, aprobar como borrador, descartar o reabrir; corrección del borrador con validación de citas |
| Consulta | — | Preguntas en español sobre el corpus: respuesta con cita o abstención explícita |
| Registro | 7 | Bitácora de decisiones, tiempos de consulta y exportación de `fichas_revisadas.jsonl` |
| Datos | 1 | Verificación en vivo del paquete contra su manifest, calidad, fuentes y lo que no entró |
| Recorrido | — | Guion de la demo: las siete etapas, T01 a T10 y las preguntas del jurado, a un clic |

### Revisión humana

- Los estados son los cinco del reto: nuevo, en revisión, requiere evidencia, aprobado como borrador y descartado. No existe un estado para publicar.
- Cada decisión la firma una persona y queda en `bitacora.jsonl` con fecha, estado anterior, estado nuevo, nota, puntaje y versión de reglas. La bitácora solo crece.
- La prioridad no habilita nada: un caso con evidencia insuficiente no se puede aprobar, por alto que sea su puntaje, y tampoco un borrador que el validador bloquea.
- Descartar, reabrir y aprobar con evidencia parcial o cifras en conflicto exigen una nota.
- Al corregir el borrador se vuelven a aplicar los controles del núcleo (`nucleo/seguridad.py`): citas válidas y cifras presentes en lo que cita cada oración.
- Si el núcleo regenera una ficha después de una decisión, el caso queda marcado para revisarse de nuevo.

### Consultas en español

El motor (`consulta.py`) responde solo con el corpus cargado. Cada afirmación cita un elemento y un campo, y antes de mostrarse se verifica que sus cifras estén en lo citado; lo que no pasa se descarta.

| Pregunta | Respuesta |
|---|---|
| «¿Qué cinco temas merecen revisión…?» | Los casos del ranking, con por qué suben, qué evidencia hay y qué falta verificar |
| Un indicador («inflación de Panamá en 2023») | El dato del Banco Mundial con país, año y unidad. Si se pide «hoy» o un año fuera del snapshot, se abstiene y ofrece el último dato anual, marcado como tal |
| Un sismo con filtro (año, mes, magnitud, lugar) | Los registros de USGS que cumplen, con el aviso de que la caja no equivale a Panamá |
| Un tema o una cifra en las noticias | Lo que publica cada medio, como declaración atribuida. Si hay cifras distintas se muestran todas |
| Algo que el corpus no contiene | Abstención, lo más cercano y qué haría falta para responder |
| Instrucciones, secretos o acciones («publica…») | Rechazo: consultar es solo leer |
| Veracidad, culpabilidad, rating, inversión, datos personales, predicciones | Fuera de alcance, con el motivo |

La búsqueda es por palabras (BM25 con raíces y sinónimos), sin modelo: es instantánea y no necesita el entorno del núcleo. La cobertura de lo preguntado decide cuándo abstenerse.

### Registro en Notion

En cada ficha, «Copiar para Notion» deja en el portapapeles el documento del caso (IDs, fuentes, puntaje desglosado, estado de evidencia, borrador, validación y revisión humana) para pegarlo en «Casos y evidencias».

El envío automático es opcional. Para activarlo, copie `interfaz/.env.example` como `interfaz/.env` y complete el token de una integración interna y el ID de la base:

```bash
python -m interfaz.notion --crear-base ID_DE_LA_PAGINA   # crea la base con sus columnas
python -m interfaz.notion --probar                       # comprueba el acceso
```

Con eso aparece el botón «Enviar a Notion», que crea la página del caso o agrega la revisión nueva a la que ya existe. Es lo único de la interfaz que usa internet.

### Fichas a pedido

El núcleo genera en lote las primeras fichas del ranking. Para los demás casos la interfaz muestra la evidencia y los pendientes, y ofrece generar la ficha si se ejecuta con el entorno del núcleo:

```bash
backend/.venv/bin/python -m interfaz        # en Windows: backend\.venv\Scripts\python -m interfaz
```

### Pruebas

```bash
python -m pytest interfaz/tests
```

| Prueba | Qué comprueba | Archivo |
|---|---|---|
| T08 | La bandeja y la ficha exponen componentes y regla; prioridad alta con evidencia insuficiente no se puede aprobar; no hay estado para publicar | `interfaz/tests/test_t08_prioridad_alta.py` |
| T09 | Paquete editorial completo y dentro de límites, citas que resuelven, hechos y declaraciones distinguidos, y bloqueo de una corrección sin respaldo | `interfaz/tests/test_t09_brief_editorial.py` |
| T04 a T07 | Dato anual con su año, cifras en conflicto, abstención y rechazo de instrucciones, desde la consulta | `interfaz/tests/test_consulta.py` |
| T10 | El recorrido completo funciona sin abrir conexiones | `interfaz/tests/test_sin_internet.py` |
| — | Estados, bitácora y separación entre el ejemplo y el reto | `interfaz/tests/test_revision.py` |
| — | Rutas del servidor, archivos fuera de la carpeta web y peticiones de otro origen | `interfaz/tests/test_servidor.py` |
| — | Documento para Notion y envío por la API con un Notion simulado | `interfaz/tests/test_notion.py` |
| — | Benchmark de desarrollo dentro de las metas de la sección 9.1 | `interfaz/tests/test_evaluar.py` |

### Evaluación de consultas

```bash
python -m interfaz.evaluar interfaz/benchmark_ejemplo.jsonl --ejemplo
python -m interfaz.evaluar ruta/benchmark.jsonl --salida resultados/    # benchmark de la organización
```

Corre cada consulta, guarda su salida completa y reporta con numerador y denominador: respuestas sustentadas, contradicciones mostradas, abstenciones correctas e incorrectas, consultas adversariales contenidas, cobertura de citas y tiempo mediano y p95. Los fallos salen listados con su consulta. El resumen es una tabla lista para la página «Pruebas y métricas» de Notion.

`benchmark_ejemplo.jsonl` trae 40 consultas de desarrollo sobre los datos de ejemplo (20 sustentadas, 6 de contradicción, 8 sin respuesta y 6 adversariales). Las escribió el equipo junto con el motor, así que sirven para detectar regresiones, no como evaluación independiente: esa corresponde al benchmark reservado, con etiquetas de revisión humana.

### Módulos

| Módulo | Qué hace |
|---|---|
| `fuentes.py` | Carga los artefactos del núcleo y el paquete de datos; arma la evidencia citable de cada evento |
| `revision.py` | Estados, reglas de aprobación, corrección del borrador y bitácora |
| `consulta.py`, `recuperacion.py`, `texto.py` | Consultas en español, búsqueda BM25 y tratamiento del texto |
| `evaluar.py` | Benchmark de consultas con las métricas de la sección 9.1 |
| `exportar.py`, `notion.py` | Documento de la ficha en Markdown o en bloques de Notion, y cliente de la API |
| `aplicacion.py`, `servidor.py` | Lo que la pantalla necesita y el servidor local (solo atiende a la propia máquina) |
| `puente.py` | Reutiliza `config.py`, `seguridad.py` y `plantilla.py` del núcleo sin exigir sus dependencias |
| `web/` | La pantalla: HTML, CSS y JavaScript sin bibliotecas externas |

### Limitaciones conocidas

- La búsqueda es por palabras: no encuentra una nota en inglés a partir de una pregunta en español, salvo por los sinónimos listados en `texto.py`, y una palabra desconocida en la pregunta puede provocar una abstención de más. Los casos parciales se muestran como «lo más cercano».
- El envío a Notion por la API se probó contra un Notion simulado; falta verificarlo con el token real del espacio del equipo.
- La revisión es de una sola máquina: no hay cuentas ni permisos, la persona se identifica con su nombre.
