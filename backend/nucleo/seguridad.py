"""
Controles de seguridad y anti-alucinación.

- detectar_inyeccion: marca textos de fuentes que intentan dar órdenes al sistema (T07).
- validar_afirmaciones: elimina afirmaciones sin una cita válida (cobertura de citas 100%).
- cifras_no_respaldadas: avisa de números del borrador que no están en la evidencia.
- citas_en_texto_invalidas: revisa las citas [ID] dentro del brief, guion y copy.

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
    """Números de un texto, normalizados ('9,5' -> '9.5', '1.000' queda igual)."""
    return {n.replace(",", ".") for n in re.findall(r"\d+(?:[.,]\d+)?", texto)}


def cifras_no_respaldadas(texto, paquete):
    """Números del texto generado que no aparecen en ninguna evidencia.
    Se ignoran enteros menores a 10 (ej. '3 preguntas', '2 fuentes') para no
    llenar de falsas alarmas; es una alerta para la persona revisora."""
    en_evidencia = _numeros(json.dumps(paquete, ensure_ascii=False))
    # También se aceptan sin decimal final: 7.40 -> 7.4
    en_evidencia |= {n.rstrip("0").rstrip(".") for n in en_evidencia if "." in n}
    sospechosos = []
    for n in sorted(_numeros(texto)):
        if n in en_evidencia:
            continue
        if "." not in n and int(n) < 10:
            continue
        sospechosos.append(n)
    return sospechosos


def citas_en_texto(texto):
    """IDs citados entre corchetes en un texto: 'sube [SIN-004]' -> ['SIN-004']"""
    return re.findall(r"\[([^\[\]]+?)\]", texto)


def cita_en_texto_valida(cita, paquete):
    """Acepta [ID] o [ID:campo]. Como algunos IDs tienen ':' (ej. WB:PAN:...:2024),
    el campo es lo que va después del ÚLTIMO ':' y debe existir en ese elemento."""
    if cita in paquete:
        return True
    id_evidencia, _, campo = cita.rpartition(":")
    return id_evidencia in paquete and campo in paquete[id_evidencia]


def citas_en_texto_invalidas(texto, paquete):
    return [c for c in citas_en_texto(texto) if not cita_en_texto_valida(c, paquete)]


def contar_palabras(texto):
    """Palabras sin contar las citas [ID]."""
    sin_citas = re.sub(r"\[[^\[\]]+?\]", " ", texto)
    return sum(1 for token in sin_citas.split() if re.search(r"\w", token))
