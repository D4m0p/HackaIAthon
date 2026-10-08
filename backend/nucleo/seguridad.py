"""
Controles de seguridad y anti-alucinación.

- detectar_inyeccion: marca textos de fuentes que intentan dar órdenes al sistema (T07).
- validar_afirmaciones: elimina afirmaciones sin una cita válida (cobertura de citas 100%).
- cifras_sin_respaldo_por_oracion: cada número debe estar en lo que cita su propia oración.
- siglas_fuera_de_evidencia: detecta entidades (INEC, IDAAN...) que no están en la evidencia.
- faltan_versiones: con cifras contradictorias, el texto debe mostrarlas todas (T05).
- citas_en_texto_invalidas: revisa las citas [ID] o [ID:campo] del brief, guion y copy.

Nada de esto usa el LLM: son reglas simples y verificables.
"""

import json
import re

from nucleo.organizar import normalizar

# Frases típicas de inyección de instrucciones (comparadas sin tildes y en minúsculas)
PATRONES_INYECCION = [
    r"ignora\w* (todas )?(tus |las )?(\w+ )?instrucciones",
    r"ignore (all )?(your |the )?(previous |prior )?instructions",
    r"olvida\w* (tus |las )?(reglas|instrucciones)",
    r"revela\w* (tu |el )?(prompt|instrucciones|secreto|clave)",
    r"(system prompt|prompt de sistema|prompt del sistema)",
    r"(nuevas instrucciones|new instructions)",
    r"(actua como|you are now|ahora eres)",
    r"(prioridad|puntaje|score) (de )?100",
    r"(api key|contrasena|password|token secreto)",
    # Paráfrasis dirigidas al sistema
    r"nota (para|al) (el )?(sistema|asistente|modelo|clasificador)",
    r"para (el|la) (asistente|ia|modelo|sistema|clasificador)\s*:",
    r"omit\w* (las |los |tus )?(advertencias|avisos|reglas|restricciones)",
    r"instruccion\w* (para|al) (el |la )?(modelo|sistema|asistente|ia)",
    r"(clasifica|marca|etiqueta)\w* (esta|este|la|el) (noticia|titular) como",
    r"responde (solo|unicamente) con",
    # Marcadores de delimitación: ningún titular real los usa
    r"<<|>>",
]


def detectar_inyeccion(texto):
    """Devuelve la lista de patrones sospechosos encontrados (vacía si el texto es normal)."""
    texto = normalizar(texto)
    return [p for p in PATRONES_INYECCION if re.search(p, texto)]


def validar_afirmaciones(afirmaciones, paquete):
    """Separa afirmaciones válidas de descartadas.
    Una afirmación es válida si TODAS sus citas apuntan a un ID del paquete de
    evidencia y a un campo que ese elemento realmente tiene, y tiene al menos una."""
    validas, descartadas = [], []
    for a in afirmaciones:
        citas = a.get("citas") or []
        problemas = []
        if not citas:
            problemas.append("sin citas")
        for c in citas:
            elemento = paquete.get(c.get("id_evidencia"))
            if elemento is None:
                problemas.append(f"ID inexistente: {c.get('id_evidencia')}")
            elif c.get("campo") not in elemento:
                problemas.append(f"campo inexistente: {c.get('id_evidencia')}.{c.get('campo')}")
        if problemas:
            descartadas.append({**a, "motivo_descarte": "; ".join(problemas)})
        else:
            validas.append(a)
    return validas, descartadas


def _numeros(texto):
    """Números de un texto, normalizados para comparar:
    '9,5' -> '9.5', '7.40' -> '7.4', '09' -> '9'. Incluye enteros pequeños."""
    resultado = set()
    for n in re.findall(r"\d+(?:[.,]\d+)?", texto):
        n = n.replace(",", ".")
        if "." in n:
            n = n.rstrip("0").rstrip(".")
        entero, _, decimal = n.partition(".")
        n = (entero.lstrip("0") or "0") + (f".{decimal}" if decimal else "")
        resultado.add(n)
    return resultado


def _quitar_citas(texto):
    return re.sub(r"\[[^\[\]]+?\]", " ", texto)


def citas_en_texto(texto):
    """Citas entre corchetes en un texto: 'sube [SIN-004:titulo]' -> ['SIN-004:titulo']"""
    return re.findall(r"\[([^\[\]]+?)\]", texto)


def _resolver_cita(cita, paquete):
    """[ID] -> (ID, None); [ID:campo] -> (ID, campo). Como algunos IDs tienen ':'
    (ej. WB:PAN:...:2024), el campo es lo que va después del ÚLTIMO ':'.
    Devuelve None si la cita no corresponde a nada del paquete."""
    if cita in paquete:
        return cita, None
    id_evidencia, _, campo = cita.rpartition(":")
    if id_evidencia in paquete and campo in paquete[id_evidencia]:
        return id_evidencia, campo
    return None


def cita_en_texto_valida(cita, paquete):
    return _resolver_cita(cita, paquete) is not None


def citas_en_texto_invalidas(texto, paquete):
    return [c for c in citas_en_texto(texto) if not cita_en_texto_valida(c, paquete)]


def _texto_citado(citas, paquete):
    """Texto de lo que realmente se citó: el campo indicado, o el elemento entero si no hay campo."""
    partes = []
    for cita in citas:
        resuelta = _resolver_cita(cita, paquete)
        if resuelta:
            id_evidencia, campo = resuelta
            valor = paquete[id_evidencia] if campo is None else paquete[id_evidencia][campo]
            partes.append(json.dumps(valor, ensure_ascii=False))
    return " ".join(partes)


def oraciones(texto):
    """Divide en oraciones (sin cortar decimales como 9.5)."""
    return [o.strip() for o in re.split(r"(?<=[.!?])\s+", texto) if o.strip()]


def cifras_sin_respaldo_por_oracion(texto, paquete):
    """Cada número de una oración debe aparecer en lo que esa misma oración cita.
    Devuelve la lista de problemas (vacía si todo está respaldado)."""
    problemas = []
    for oracion in oraciones(texto):
        numeros = _numeros(_quitar_citas(oracion))
        if not numeros:
            continue
        citas = citas_en_texto(oracion)
        if not citas:
            problemas.append(f"cifra sin cita ({', '.join(sorted(numeros))}): «{oracion[:90]}»")
            continue
        faltan = numeros - _numeros(_texto_citado(citas, paquete))
        if faltan:
            problemas.append(f"cifra que no está en lo citado ({', '.join(sorted(faltan))}): «{oracion[:90]}»")
    return problemas


def cifras_sin_respaldo_en_afirmacion(afirmacion, paquete):
    """Los números de una afirmación deben estar en los campos que ella misma cita."""
    citas = [f"{c['id_evidencia']}:{c['campo']}" for c in afirmacion.get("citas", [])]
    faltan = _numeros(_quitar_citas(afirmacion["texto"])) - _numeros(_texto_citado(citas, paquete))
    return sorted(faltan)


def cifras_fuera_de_evidencia(texto, paquete):
    """Para textos sin citas (qué se reporta, qué falta verificar, preguntas...):
    números que no aparecen en ninguna parte de la evidencia."""
    return sorted(_numeros(_quitar_citas(texto)) - _numeros(json.dumps(paquete, ensure_ascii=False)))


def siglas_fuera_de_evidencia(texto, paquete):
    """Siglas (INEC, IDAAN...) que no aparecen en la evidencia: posibles entidades inventadas."""
    from nucleo import config
    evidencia = normalizar(json.dumps(paquete, ensure_ascii=False))
    siglas = set(re.findall(r"\b[A-ZÁÉÍÓÚÑ]{3,}\b", _quitar_citas(texto)))
    return sorted(s for s in siglas
                  if s not in config.SIGLAS_PERMITIDAS and normalizar(s) not in evidencia)


def faltan_versiones(texto, contradicciones):
    """Cifras contradictorias que NO aparecen en el texto (T05: hay que mostrar todas)."""
    presentes = _numeros(_quitar_citas(texto))
    return [c["cifra"] for c in contradicciones if not (_numeros(c["cifra"]) <= presentes)]


def contar_palabras(texto):
    """Palabras sin contar las citas [ID]."""
    return sum(1 for token in _quitar_citas(texto).split() if re.search(r"\w", token))
