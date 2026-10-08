"""
Baseline "sin IA" para comparar contra el núcleo (requisito de la sección 8).

Hace lo mismo que organizar.py pero con métodos simples:
- Tema: listas de palabras clave.
- Agrupación: similitud TF-IDF (palabras en común), no significado.

Si los embeddings no superan a esto en las métricas, hay que decirlo en Notion.
"""

from sklearn.feature_extraction.text import TfidfVectorizer

from nucleo import config
from nucleo.organizar import _agrupar, _dias_entre, normalizar

PALABRAS_CLAVE = {
    "economia": ["inflacion", "precio", "pib", "economia", "desempleo", "empleo", "deuda", "impuesto"],
    "logistica_canal": ["canal", "buque", "calado", "puerto", "contenedor", "exportacion", "naviera"],
    "turismo": ["turista", "turismo", "hotel", "hotelera", "tocumen", "vuelo", "crucero"],
    "servicios_publicos": ["agua", "electricidad", "apagon", "metro", "bus", "hospital", "css"],
    "eventos_naturales": ["sismo", "temblor", "terremoto", "lluvia", "inundacion", "sequia", "tormenta"],
    "regulacion": ["ley", "decreto", "asamblea", "norma", "superintendencia", "corte suprema", "acuerdo"],
}

# Umbrales propios del baseline (TF-IDF da similitudes más bajas que los embeddings)
UMBRAL_EVENTO_TFIDF = 0.30
UMBRAL_REPLICA_TFIDF = 0.85


def clasificar_tema_baseline(titulo):
    texto = normalizar(titulo)
    conteo = {tema: sum(p in texto for p in palabras) for tema, palabras in PALABRAS_CLAVE.items()}
    mejor = max(conteo, key=conteo.get)
    return mejor if conteo[mejor] > 0 else "otro"


def organizar_baseline(noticias):
    """Misma salida que organizar.organizar(), para poder comparar."""
    titulos = [normalizar(n["titulo"]) for n in noticias]
    matriz = TfidfVectorizer().fit_transform(titulos)
    sim = (matriz @ matriz.T).toarray()

    def mismo_evento(a, b):
        return (sim[a, b] >= UMBRAL_EVENTO_TFIDF
                and _dias_entre(noticias[a]["fecha"], noticias[b]["fecha"]) <= config.VENTANA_DIAS)

    eventos = []
    for indices in _agrupar(list(range(len(noticias))), mismo_evento):
        ids = sorted(noticias[i]["id_noticia"] for i in indices)
        procedencias = _agrupar(indices, lambda a, b: sim[a, b] >= UMBRAL_REPLICA_TFIDF)
        eventos.append({
            "id_evento": f"EV-{ids[0]}",
            "tema": clasificar_tema_baseline(noticias[indices[0]]["titulo"]),
            "ids_noticias": ids,
            "n_fuentes_independientes": len(procedencias),
        })
    eventos.sort(key=lambda e: e["id_evento"])
    return eventos
