"""Tratamiento de texto en español para buscar y comparar sin depender de modelos."""

from __future__ import annotations

import re
import unicodedata

from . import rutas  # noqa: F401  (deja `nucleo` e `ingesta` importables)
from nucleo import config

# Palabras que no aportan a una búsqueda: las del núcleo (vacías y genéricas del
# corpus, como "panama") más las propias de una pregunta.
PALABRAS_DE_PREGUNTA = {
    "cual", "cuales", "cuanto", "cuanta", "cuantos", "cuantas", "quien", "quienes", "donde",
    "cuando", "porque", "dime", "dame", "muestra", "muestrame", "mostrar", "explica", "explicame",
    "busca", "buscar", "saber", "sabe", "sabes", "tiene", "tienen", "tengo", "hubo", "hay", "habia",
    "paso", "pasa", "pasando", "ocurrio", "ocurre", "sucedio", "sucede", "dice", "dicen", "dijo",
    "reporta", "reportan", "reporto", "informa", "informan", "noticia", "noticias", "titular",
    "titulares", "tema", "temas", "caso", "casos", "evento", "eventos", "informacion", "dato",
    "datos", "cifra", "cifras", "numero", "favor", "puedes", "puede", "quiero", "necesito",
    "todo", "toda", "todos", "todas", "algo", "alguna", "alguno", "algun", "otro", "otra", "otros",
    "esta", "esto", "estos", "estas", "ese", "esa", "eso", "esos", "esas", "aqui", "alli", "actual",
    "actualmente", "hoy", "ahora", "ayer", "ultimo", "ultima", "ultimos", "ultimas", "reciente",
    "recientes", "sido", "siendo", "estan", "estaba", "fueron", "seria", "sera", "ser", "the",
    "and", "for", "san", "santa", "me", "te", "mi", "tu", "nos", "yo", "ante", "cada", "ni", "pero",
    "tambien", "solo", "mismo", "misma", "durante", "contra", "tras", "segun", "respecto",
    "corpus", "sistema", "medios", "medio", "fuente", "fuentes", "evidencia", "evidencias",
    # juicios y adjetivos genéricos: no describen el asunto
    "verdad", "verdadero", "verdadera", "falso", "falsa", "cierto", "cierta", "mentira", "real",
    "confirma", "confirmar", "clave", "claves", "principal", "principales", "importante",
    "importantes", "relevante", "relevantes", "novedad", "novedades", "situacion", "resumen",
    "resume", "acerca", "relacion", "relacionado", "relacionada", "relacionados", "relacionadas",
    "hace", "hacer", "hizo", "hacen", "pueden", "debe", "deben", "va", "van", "ver", "dar", "dio",
    "dan", "decir", "sigue", "siguen", "existe", "existen", "conoce", "trata", "tratan", "habla",
    "hablan", "cuentame", "publico", "publicaron", "publica", "publican", "salio", "salieron",
    "ultimamente", "recientemente", "general", "tipo", "cosas", "cosa", "parte", "manera", "forma",
}
PALABRAS_VACIAS = set(config.PALABRAS_IGNORADAS) | PALABRAS_DE_PREGUNTA

# Formas distintas de nombrar lo mismo: variantes de una palabra, sinónimos estrictos y su
# equivalente en inglés (el paquete trae titulares en inglés). Sin esto una búsqueda por
# palabras no encuentra "sismo" cuando se pregunta por un "terremoto". No van aquí los
# términos solo relacionados («Tocumen» no es sinónimo de «aeropuerto»): con ellos la
# búsqueda devolvía casos que no respondían la pregunta.
GRUPOS_DE_SINONIMOS = [
    list(config.PALABRAS_SISMO) + ["sismico", "sismica", "telurico", "seismo", "earthquake", "quake"],
    ["inflacion", "inflacionario", "encarecimiento", "carestia", "inflation"],
    ["precio", "price"],
    ["desempleo", "desocupacion", "desempleado", "unemployment"],
    ["empleo", "job"],
    ["pib", "gdp"],
    ["agua", "water"],
    ["electricidad", "electrica", "electrico", "electricity"],
    ["apagon", "blackout"],
    ["buque", "barco", "ship", "vessel"],
    ["puerto", "portuario", "portuaria", "port"],
    ["turismo", "turista", "turistico", "turistica", "tourism", "tourist"],
    ["hotel", "hotelera", "hotelero", "hospedaje"],
    ["lluvia", "lluvioso", "aguacero", "precipitacion", "rain"],
    ["inundacion", "inundado", "inundada", "inundo", "flood", "flooding"],
    ["sequia", "drought"],
    ["ley", "legislacion", "law"],
    ["huelga", "paro", "strike"],
    ["protesta", "manifestacion", "protest"],
    ["exportacion", "exportar", "exporto", "exportan", "exportador", "export"],
    ["aeropuerto", "airport"],
    ["mina", "minera", "minero", "mineria", "mine", "mining"],
    ["cobre", "copper"],
    ["gobierno", "government"],
    ["presidente", "president"],
    ["comercio", "comercial", "trade"],
    ["economia", "economico", "economica", "economy", "economic"],
    ["deuda", "debt"],
    ["impuesto", "tributo", "tax"],
    ["banco", "bancario", "bancaria", "bank"],
    ["salud", "sanitario", "sanitaria", "health"],
    ["migracion", "migrante", "migratorio", "migration", "migrant"],
    ["petroleo", "oil"],
]

# Nombres propios de Panamá que implican un término general, en un solo sentido: una nota
# sobre «Tocumen» es una nota sobre un aeropuerto, pero no toda nota de aeropuertos es de Tocumen.
IMPLICA = {
    "tocumen": ["aeropuerto"],
    "gatun": ["canal"], "calado": ["canal"], "esclusa": ["canal"], "neopanamax": ["canal"],
    "idaan": ["agua"],
    "naturgy": ["electricidad"], "etesa": ["electricidad"], "ensa": ["electricidad"],
    "minsa": ["salud"],
    "meduca": ["educacion"],
}

NOMBRE_TEMA = {
    "economia": "Economía",
    "logistica_canal": "Logística y Canal",
    "turismo": "Turismo",
    "servicios_publicos": "Servicios públicos",
    "eventos_naturales": "Eventos naturales",
    "regulacion": "Regulación",
    "otro": "Otros temas",
}


def normalizar(texto: str | None) -> str:
    """Minúsculas y sin tildes: la misma regla que usa el núcleo de IA."""
    descompuesto = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(caracter for caracter in descompuesto if unicodedata.category(caracter) != "Mn")


LETRAS_RAIZ = 7


def raiz(palabra: str) -> str:
    """Raíz aproximada de una palabra ya normalizada.

    Quita el plural («precios» → «precio», «leyes» → «ley», «buques» y «buque» → «buqu») y
    recorta las palabras largas para juntar sus variantes («exportar», «exportación» →
    «export»; «aumenta», «aumentaron» → «aument»). El recorte es largo a propósito: con
    menos letras «desempleo» se confundía con «desempeño» y «precio» con «precisa».
    """
    if any(caracter.isdigit() for caracter in palabra):
        return palabra.replace(",", ".")
    if palabra.endswith("es") and len(palabra) >= 5:
        palabra = palabra[:-2]
    elif palabra.endswith("s") and len(palabra) >= 4:
        palabra = palabra[:-1]
    if palabra.endswith("e") and len(palabra) >= 4:
        palabra = palabra[:-1]
    if len(palabra) >= LETRAS_RAIZ:
        palabra = palabra[:LETRAS_RAIZ]
        if palabra[-1] in "aeo":
            palabra = palabra[:-1]
    return palabra


def palabras(texto: str | None) -> list[str]:
    return re.findall(r"\w+(?:[.,]\d+)?", normalizar(texto))


def raices(texto: str | None) -> list[str]:
    """Raíces de las palabras con contenido, con repeticiones."""
    return [raiz(palabra) for palabra in palabras(texto)
            if palabra not in PALABRAS_VACIAS and len(palabra) >= 2]


def terminos(texto: str | None) -> list[str]:
    """Raíces de las palabras con contenido, en orden y sin repetir."""
    return list(dict.fromkeys(raices(texto)))


def _tabla_de_sinonimos() -> dict[str, frozenset[str]]:
    tabla: dict[str, set[str]] = {}
    for grupo in GRUPOS_DE_SINONIMOS:
        raices = {raiz(normalizar(palabra)) for palabra in grupo}
        for una in raices:
            tabla.setdefault(una, set()).update(raices)
    return {clave: frozenset(valor) for clave, valor in tabla.items()}


SINONIMOS = _tabla_de_sinonimos()
RAICES_IMPLICADAS = {raiz(nombre): [raiz(general) for general in generales] for nombre, generales in IMPLICA.items()}


def raices_de_documento(texto: str | None) -> list[str]:
    """Raíces de un texto del corpus, más los términos generales que sus nombres propios implican."""
    propias = raices(texto)
    implicadas = {general for una in set(propias) for general in RAICES_IMPLICADAS.get(una, [])}
    return propias + sorted(implicadas - set(propias))


def alternativas(termino: str) -> frozenset[str]:
    """El término y las otras raíces que nombran lo mismo."""
    return SINONIMOS.get(termino, frozenset((termino,)))


def contar_palabras(texto: str | None) -> int:
    """Palabras de un texto sin contar las citas entre corchetes."""
    sin_citas = re.sub(r"\[[^\[\]]+?\]", " ", texto or "")
    return sum(1 for trozo in sin_citas.split() if re.search(r"\w", trozo))
