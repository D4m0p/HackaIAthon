"""
Configuración del núcleo de IA.

Todo lo que se puede ajustar (umbrales, temas, pesos) vive aquí, para que
cualquier cambio quede en un solo lugar y se pueda justificar en Notion.
"""

# Versión de las reglas. Cambiarla cada vez que se toque un umbral o un peso,
# y registrar el motivo en Notion (Plan y decisiones).
VERSION_REGLAS = "reglas-v1"

# Modelo de embeddings local (multilingüe, funciona sin internet una vez descargado).
# Decisión: se eligió bge-m3 frente a MiniLM, mpnet y e5 porque fue el único que
# separó con margen claro "mismo evento" de "eventos distintos" (ver Notion).
MODELO_EMBEDDINGS = "BAAI/bge-m3"

# Caché temporal del LLM y registro de llamadas (no se sube a git).
CARPETA_CACHE = "cache"
# Resultados versionados que permiten la demo sin internet (SÍ se sube a git):
# temas por titular, redacciones por evento y embeddings ya calculados.
CARPETA_ARTEFACTOS = "artefactos"

# ---------------------------------------------------------------------------
# LLM (Gemini)
# ---------------------------------------------------------------------------
# Cada tarea tiene una lista de modelos en orden de preferencia. Si uno está
# saturado o no responde, se pasa al siguiente sin esperar.
# Modelos rápidos para tareas simples en lote (clasificar temas).
# Groq va al final como respaldo gratuito ("groq:" = proveedor Groq). Plan gratis:
# 1.000 llamadas/día y 8.000 tokens/minuto POR MODELO, por eso se usan dos modelos.
# En los 18 titulares de ejemplo ambos coincidieron con Gemini en el tema (18/18).
MODELOS_GROQ = ["groq:openai/gpt-oss-120b", "groq:qwen/qwen3.8-27b"]
MODELOS_RAPIDOS = ["gemini-3.5-flash-lite", "gemini-3.5-flash", *MODELOS_GROQ]
# Modelos de mejor calidad para fichas y borradores.
MODELOS_REDACCION = ["gemini-3.8-flash", "gemini-3.5-flash", *MODELOS_GROQ]
# Tope de tokens de salida por llamada a Groq (una ficha completa usa menos de 3.000).
GROQ_MAX_TOKENS_SALIDA = 3000
# Si Groq pide esperar hasta esto (límite por minuto), se espera y se reintenta una vez.
GROQ_ESPERA_MAXIMA = 60
# Espera entre rondas cuando todos los modelos disponibles fallaron por límite por minuto.
ESPERA_LIMITE_POR_MINUTO = 30
# Temperatura 0 = respuestas lo más consistentes posible.
TEMPERATURA = 0
# Cuántos titulares se mandan por llamada al clasificar temas (40 cabe en el
# límite de tokens por minuto de Groq, contando el motivo y la relación con Panamá).
TAMANO_LOTE_TEMAS = 40
# Rondas de intentos: en cada ronda se prueban todos los modelos de la lista;
# entre rondas se espera un poco (2 s, 4 s...).
REINTENTOS_LLM = 2
# Tiempo máximo de espera por llamada.
TIMEOUT_LLM_SEGUNDOS = 60

# Versión de la clasificación de temas. Cambiarla obliga a reclasificar: los temas
# guardados con otra versión dejan de usarse.
# v2: definiciones con exclusiones explícitas + relación con Panamá (tras ver con los
#     datos reales que "salud pública" atraía consejos médicos y farándula).
VERSION_CLASIFICACION = "temas-v2"

# Definición de cada tema, tal como se le explica al LLM. Incluye qué NO entra.
DEFINICION_TEMAS = {
    "economia": ("inflación, precios, crecimiento, empleo y desempleo, deuda, impuestos, finanzas "
                 "públicas, inversión y comercio. NO: consejos de finanzas personales."),
    "logistica_canal": ("Canal de Panamá, buques, puertos, contenedores, comercio exterior y cadena "
                        "logística. NO: sanciones o conflictos de otros países sin efecto en esa logística."),
    "turismo": "turistas, hoteles, vuelos, aerolíneas, cruceros y actividad turística.",
    "servicios_publicos": ("servicios que presta el Estado: agua potable, electricidad, transporte "
                           "público, metro, carreteras, recolección de basura, hospitales públicos, CSS "
                           "y campañas del Ministerio de Salud. NO: consejos de salud personal, "
                           "testimonios o historias de vida, farándula, ni sucesos policiales."),
    "eventos_naturales": ("sismos, lluvias, inundaciones, sequías, deslizamientos, fenómenos climáticos "
                          "y simulacros o alertas ante ellos."),
    "regulacion": ("leyes, decretos, normas, acuerdos de superintendencias y fallos judiciales de "
                   "Panamá. NO: procesos judiciales de otros países."),
    "otro": ("lo que no encaja claramente en los anteriores: deportes, farándula, entretenimiento, "
             "salud y bienestar personal, sucesos policiales, política o justicia de otros países."),
}

# Relación de la noticia con Panamá, la decide el LLM al clasificar. Se usa en R.
RELACIONES_PANAMA = {
    "directa": "ocurre en Panamá o involucra directamente a instituciones, personas o empresas de Panamá",
    "indirecta": "ocurre fuera, pero tiene un efecto concreto y explicable en Panamá (ej. comercio, Canal, migración)",
    "ninguna": "no ocurre en Panamá ni tiene un efecto concreto en Panamá",
}
# Aporte de cada relación a la mitad "Panamá" de R.
VALOR_RELACION_PANAMA = {"directa": 1.0, "indirecta": 0.5, "ninguna": 0.0}

# ---------------------------------------------------------------------------
# Temas del reto (sección 3, etapa 2)
# Cada tema tiene varias frases de ejemplo. Un titular se compara con todas
# y se queda con el tema de la frase más parecida.
# ---------------------------------------------------------------------------
TEMAS = {
    "economia": [
        "inflación y aumento de precios en Panamá",
        "crecimiento económico y producto interno bruto",
        "desempleo, empleo y mercado laboral",
        "deuda pública, impuestos y presupuesto del Estado",
    ],
    "logistica_canal": [
        "tránsito de buques por el Canal de Panamá",
        "restricciones de calado y nivel de agua en el Canal",
        "puertos, contenedores y comercio marítimo",
        "exportaciones, importaciones y cadena logística",
    ],
    "turismo": [
        "llegada de turistas y visitantes a Panamá",
        "hoteles, ocupación hotelera y temporada turística",
        "aeropuerto de Tocumen, vuelos y aerolíneas",
        "cruceros y turismo internacional",
    ],
    "servicios_publicos": [
        "cortes de agua potable y abastecimiento",
        "apagones y servicio de electricidad",
        "transporte público, metro y buses",
        "hospitales, salud pública y Caja de Seguro Social",
    ],
    "eventos_naturales": [
        "sismo o terremoto registrado",
        "inundaciones y lluvias intensas",
        "sequía y fenómeno de El Niño",
        "deslizamientos, tormentas y alertas climáticas",
    ],
    "regulacion": [
        "nueva ley aprobada por la Asamblea Nacional",
        "decreto ejecutivo y nueva normativa",
        "regulación bancaria y financiera",
        "fallo de la Corte Suprema",
    ],
}

# Si el mejor parecido con cualquier tema es menor a esto, el tema queda como "otro".
UMBRAL_TEMA = 0.43

# ---------------------------------------------------------------------------
# Agrupación de noticias en eventos (CU-03, T02)
# ---------------------------------------------------------------------------
# Agrupación híbrida: una noticia se une a un evento solo si cumple las tres:
#   1. Semántica: parecido promedio con el evento >= UMBRAL_EVENTO
#   2. Léxica: comparte al menos una palabra relevante con alguna noticia del evento
#   3. Fecha: está a VENTANA_DIAS o menos de todas las noticias del evento
UMBRAL_EVENTO = 0.50
VENTANA_DIAS = 3

# Palabras que NO cuentan como "palabra relevante compartida": palabras vacías
# del español y términos que aparecen en casi todos los titulares del corpus.
PALABRAS_IGNORADAS = {
    # generales del corpus
    "panama", "panameno", "panamena", "panamenos", "panamenas", "pais", "nacional",
    "segun", "nuevo", "nueva", "nuevos", "nuevas",
    # palabras vacías
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al", "a",
    "en", "por", "para", "con", "sin", "sobre", "ante", "tras", "entre", "hasta",
    "desde", "y", "o", "e", "u", "que", "se", "su", "sus", "es", "son", "ser",
    "fue", "esta", "este", "estos", "estas", "como", "mas", "muy", "ya", "lo",
    "le", "les", "no", "si", "hay", "ha", "han",
}
# Las palabras se comparan por sus primeras letras, para que "precio" y "precios"
# cuenten como la misma palabra.
LETRAS_RAIZ = 5

# Dos titulares casi idénticos en medios distintos = la misma procedencia
# (ej. una agencia replicada). Cuentan como UNA sola fuente independiente.
UMBRAL_REPLICA = 0.92

# ---------------------------------------------------------------------------
# Contextualización (etapa 3)
# ---------------------------------------------------------------------------
PAIS_PRINCIPAL = "PAN"
# Países de comparación (economías de tamaño y perfil parecido a Panamá).
PAISES_COMPARACION = ["CRI", "DOM"]
# Cuántos años de la serie de Panamá se muestran (CU-02: incorporar una serie oficial).
ANIOS_SERIE = 5

# Un indicador se vincula a un evento SOLO si sus titulares mencionan alguna de
# estas palabras (comparadas sin tildes y en minúsculas). Si no, no se fuerza.
INDICADORES = {
    "NY.GDP.MKTP.KD.ZG": {
        "nombre": "Crecimiento del PIB",
        "palabras": ["pib", "crecimiento economico", "economia crece", "producto interno", "recesion"],
    },
    "FP.CPI.TOTL.ZG": {
        "nombre": "Inflación, precios al consumidor",
        "palabras": ["inflacion", "precio", "canasta basica", "costo de vida"],
    },
    "SL.UEM.TOTL.ZS": {
        "nombre": "Desempleo",
        "palabras": ["desempleo", "desocupacion", "empleo", "mercado laboral"],
    },
    "NE.EXP.GNFS.ZS": {
        "nombre": "Exportaciones de bienes y servicios",
        "palabras": ["exportacion", "comercio exterior"],
    },
    "SP.POP.TOTL": {
        "nombre": "Población total",
        "palabras": ["poblacion", "censo", "habitantes"],
    },
    "IT.NET.USER.ZS": {
        "nombre": "Personas que usan internet",
        "palabras": ["internet", "conectividad", "brecha digital"],
    },
}

# Sismos USGS: solo para eventos cuyos titulares hablen de sismos (nunca para
# inundaciones u otros fenómenos), y solo si coincide la fecha Y (lugar o magnitud).
PALABRAS_SISMO = ["sismo", "temblor", "terremoto"]
VENTANA_DIAS_SISMO = 2
TOLERANCIA_MAGNITUD = 0.2

# ---------------------------------------------------------------------------
# Priorización (etapa 4) · P = 30R + 25I + 20U + 15N + 10E
# ---------------------------------------------------------------------------
PESOS = {"R": 30, "I": 25, "U": 20, "N": 15, "E": 10}
# Rangos sin solapamiento: bajo [0,40), medio [40,70), alto [70,100]
NIVELES = [(70, "alto"), (40, "medio"), (0, "bajo")]

# R · Relevancia. La relación con Panamá la decide el LLM (RELACIONES_PANAMA). Si no
# hay LLM, se usa la mención de estos lugares como respaldo.
# Nota: "lo publicó TVN" NO cuenta como relación con Panamá (TVN también publica
# noticias de Siberia o Filipinas); se quitó esa regla al ver los datos reales.
LUGARES_PANAMA = [
    "panama", "canal", "gatun", "tocumen", "chiriqui", "bocas del toro", "cocle",
    "colon", "darien", "herrera", "los santos", "veraguas", "san miguelito",
    "arraijan", "chorrera", "guna yala", "embera", "ngabe",
]

# I · Impacto: peso base por tema (alcance sectorial típico en Panamá).
# Es una decisión editorial: ajustarla con la persona editorial y registrar el cambio.
IMPACTO_BASE_TEMA = {
    "logistica_canal": 0.8,
    "economia": 0.7,
    "servicios_publicos": 0.7,
    "eventos_naturales": 0.6,
    "regulacion": 0.6,
    "turismo": 0.5,
    "otro": 0.2,
}
# Bonus de impacto si un dato oficial respalda el alcance del tema.
BONUS_IMPACTO_DATO_OFICIAL = 0.2

# U · Urgencia: baja de 1 a 0 a lo largo de estos días desde la publicación más reciente.
DIAS_URGENCIA = 7

# N · Novedad: se compara con los eventos publicados antes, dentro de esta ventana.
DIAS_NOVEDAD = 30
# Parecido con un evento anterior: <= MIN -> totalmente nuevo; >= MAX -> repetido.
NOVEDAD_SIM_MIN = 0.50
NOVEDAD_SIM_MAX = 0.90
# Si se detectó más de estos días después de su fecha original, es una noticia
# recirculada. Mismo umbral que usa el equipo A (ingesta/recirculacion.py), para que
# haya una sola regla. Con datos de A se usa directamente su campo "recirculada".
DIAS_RECIRCULADA = 7
# Una noticia recirculada se limita a menos de este puntaje (= nunca pasa de "bajo").
TOPE_RECIRCULADA = 40

# ---------------------------------------------------------------------------
# Fichas y borradores (etapas 5 y 6)
# ---------------------------------------------------------------------------
MODALIDAD = "editorial_tvn"
# Cuántas fichas se generan en lote (las primeras del ranking). El resto, a pedido.
FICHAS_TOP_N = 10
# Límites del paquete editorial (sección 3 del reto)
LIMITE_PALABRAS_BRIEF = 250
LIMITE_PALABRAS_COPY = 80
# Guion de 45-60 segundos ~ 100-160 palabras leídas en voz alta
RANGO_PALABRAS_GUION = (100, 160)
# Siglas que pueden aparecer aunque no estén en la evidencia (no son entidades citadas).
SIGLAS_PERMITIDAS = {"TVN", "UTC"}

# Valores de alcance_texto que significan "solo hay titular y metadatos".
ALCANCES_SOLO_TITULAR = {"titular", "titular_y_metadatos"}

# ---------------------------------------------------------------------------
# Idiomas
# ---------------------------------------------------------------------------
# Solo estas noticias entran al panel. Las demás no se borran del paquete: se
# marcan como fuera de alcance. Decisión: en el paquete real, el inglés trae
# mayormente noticias sobre Panamá; los otros idiomas (griego, chino, portugués,
# francés...) son casi todo ruido (fletes, bolsa china, política de Brasil).
# Una noticia sin idioma declarado se conserva.
IDIOMAS_PANEL = {"es", "en"}

# ---------------------------------------------------------------------------
# Consultas (nucleo/consultar.py, usado por la interfaz)
# ---------------------------------------------------------------------------
# Largo máximo de la respuesta redactada por el LLM.
LIMITE_PALABRAS_RESPUESTA = 120
# Parecido mínimo (bge-m3) para que un evento se le pase al LLM cuando la búsqueda por
# palabras no encontró respuesta. No decide si responder: eso lo decide el LLM leyendo
# la evidencia. Por debajo de esto ni se consulta (ahorra llamadas).
UMBRAL_CANDIDATO_SEMANTICO = 0.35
