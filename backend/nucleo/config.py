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
MODELOS_RAPIDOS = ["gemini-3.5-flash-lite", "gemini-3.5-flash"]
# Modelos de mejor calidad para fichas y borradores.
MODELOS_REDACCION = ["gemini-3.8-flash", "gemini-3.5-flash"]
# Temperatura 0 = respuestas lo más consistentes posible.
TEMPERATURA = 0
# Cuántos titulares se mandan por llamada al clasificar temas.
TAMANO_LOTE_TEMAS = 50
# Rondas de intentos: en cada ronda se prueban todos los modelos de la lista;
# entre rondas se espera un poco (2 s, 4 s...).
REINTENTOS_LLM = 2
# Tiempo máximo de espera por llamada.
TIMEOUT_LLM_SEGUNDOS = 60

# Definición de cada tema, tal como se le explica al LLM.
DEFINICION_TEMAS = {
    "economia": "inflación, precios, crecimiento, empleo y desempleo, deuda, impuestos, finanzas públicas",
    "logistica_canal": "Canal de Panamá, buques, puertos, contenedores, comercio exterior y cadena logística",
    "turismo": "turistas, hoteles, vuelos, aerolíneas, cruceros y actividad turística",
    "servicios_publicos": "agua potable, electricidad, transporte público, metro, salud pública, recolección de basura",
    "eventos_naturales": "sismos, lluvias, inundaciones, sequías, deslizamientos y fenómenos climáticos",
    "regulacion": "leyes, decretos, normas, acuerdos de superintendencias, fallos judiciales y cambios regulatorios",
    "otro": "cualquier tema que no encaje claramente en los anteriores (deportes, farándula, sucesos, etc.)",
}

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

# R · Relevancia: lugares e instituciones que vinculan una noticia con Panamá.
LUGARES_PANAMA = [
    "panama", "canal", "gatun", "tocumen", "chiriqui", "bocas del toro", "cocle",
    "colon", "darien", "herrera", "los santos", "veraguas", "san miguelito",
    "arraijan", "chorrera", "guna yala", "embera", "ngabe",
]
MEDIOS_PANAMENOS = ["tvn"]

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
# Si se detectó más de estos días después de publicada, es una noticia recirculada.
DIAS_RECIRCULADA = 30
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
