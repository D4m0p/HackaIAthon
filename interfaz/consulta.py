"""Consultas en español sobre el corpus, con cita por afirmación y abstención explícita.

Principios:
- Una afirmación sobre el mundo solo sale si cita un elemento del corpus y un campo
  que la contiene. Todo número que aparece en ella debe estar en lo que cita.
- Lo que publica un medio es una declaración atribuida; un dato oficial es un hecho
  con su año y su unidad. El orden de la bandeja es un cálculo del sistema, no un hecho.
- Si el corpus no contiene la respuesta, se dice y se explica qué haría falta.
- La pregunta nunca cambia reglas, estados ni puntajes: consultar es solo leer.
"""

from __future__ import annotations

import json
import re
import time

from . import fuentes
from .fuentes import PAISES, Corpus
from .puente import config, seguridad
from .recuperacion import Indice
from .texto import NOMBRE_TEMA, normalizar, terminos

from nucleo.plantilla import redaccion_por_plantilla  # noqa: E402  (sin dependencias)

LIMITE_PREGUNTA = 400
# Parte de lo preguntado que debe aparecer en un evento para usarlo como respuesta.
COBERTURA_SUFICIENTE = 0.6
# Por debajo de esto ni siquiera se muestra como "relacionado".
COBERTURA_MINIMA = 0.1
MAXIMO_EVENTOS = 3
MAXIMO_AFIRMACIONES_POR_EVENTO = 5
MAXIMO_SISMOS = 8

COMPONENTES = {
    "R": ("Relevancia", "Relación con Panamá y con los temas de la modalidad."),
    "I": ("Impacto potencial", "Interés público o alcance sectorial, justificado con datos."),
    "U": ("Urgencia", "Tiempo disponible para revisar la información o el evento."),
    "N": ("Novedad", "Diferencia frente a eventos ya agrupados; duplicar no suma."),
    "E": ("Evidencia disponible", "Fuentes pertinentes, primarias y con procedencia identificable."),
}

# --- Consultas que no se atienden -------------------------------------------------
_ORDEN = r"^\W*(?:por favor,? |ahora |ya )?"
PATRONES_SECRETO = [
    r"(dame|dime|muestra\w*|ensena\w*|imprime|comparte|revela\w*|cual es|cuales son|escribe|repite) (\w+ ){0,4}"
    r"(prompt|tus instrucciones|instrucciones (del|de) sistema|instrucciones (internas|ocultas|iniciales|originales)|"
    r"reglas internas|clave de api|clave secreta|claves de acceso|credencial\w*|tokens?|variables de entorno|"
    r"configuracion interna)",
    r"\.env\b", r"gemini_api_key", r"notion_token", r"api ?key",
]
PATRONES_ACCION = [
    _ORDEN + r"(publica|publique|publiquen|publicar|difunde|transmite)\b",
    _ORDEN + r"(aprueba|aprobar|descarta|descartar|elimina|eliminar|borra|borrar)\b.*"
             r"\b(todo|todas|todos|casos?|fichas?|noticias?|bitacora|registros?|borrador|borradores)\b",
    _ORDEN + r"(cambia|cambiar|modifica|modificar|sube|subele|baja|bajale|ajusta|pon|ponle|asigna)\b.*"
             r"\b(puntaje|prioridad|pesos?|estado de revision|reglas?|umbral|umbrales)\b",
    _ORDEN + r"marca\w*\b.*\bcomo\b",
    _ORDEN + r"(ejecuta|ejecutar|corre|correr)\b.*\b(comando|script|codigo|sql)\b",
    _ORDEN + r"(envia|enviar|manda|mandar)\b.*\b(correo|email|mensaje|whatsapp)\b",
    r"\b(publicalo|publicala|apruebalo|apruebala|borralo|borrala|eliminalo|eliminala|descartalo|descartala)\b",
    r"\b(que|para que) (publiques|apruebes|descartes|elimines|borres|cambies|modifiques|marques|asignes)\b",
    r"\b(puedes|podrias|debes|tienes que|necesito que|quiero que) (\w+ ){0,2}"
    r"(publicar|aprobar|descartar|eliminar|borrar|modificar|marcar)\b",
    r"\bsin revision humana\b|\bpublicacion automatica\b|\bpublica\w* automaticamente\b",
]
FUERA_DE_ALCANCE = [
    ("culpabilidad",
     r"\b(culpable|culpables|delincuente|delincuentes|corrupto|corruptos|estafador|estafadores)\b"
     r"|\bquien (es|fue|tiene) (el |la )?(culpa|responsable del delito)",
     "No se atribuye culpabilidad ni se elaboran listas de personas señaladas. Una acusación solo se "
     "muestra como declaración atribuida a quien la publica, nunca como hecho probado."),
    ("riesgo individual",
     r"\b(fraude bancario|solvencia|insolvente|riesgo de credito|riesgo crediticio|score de (cliente|clientes|credito)|"
     r"moroso|morosos|impago|impagos|cartera de clientes)\b|\bva a quebrar\b",
     "El prototipo no evalúa fraude, solvencia ni riesgo de crédito de personas o empresas. "
     "Solo ofrece contexto público del entorno, para análisis."),
    ("audiencia",
     r"\b(rating|ratings|sintonia|televidentes|conversion publicitaria|puntos de rating)\b|\bcuanta gente vio\b"
     r"|\baudiencia (de|del) (programa|noticiero|canal|tvn|la television)",
     "El paquete público no contiene mediciones de rating, audiencia ni conversión publicitaria, "
     "así que no se puede responder ni estimar."),
    ("recomendación financiera",
     r"\b(debo|deberia|conviene|recomiendas?|recomendable|sugieres|aconsejas)\b.{0,30}\b(comprar|vender|invertir)\b"
     r"|\b(comprar|vender) (acciones|bonos|dolares|divisas)\b",
     "No se dan recomendaciones de compra, venta o inversión."),
    ("datos personales",
     r"\b(direccion|telefono|celular|cedula|domicilio) (de|del|de la)\b|\bdonde vive\b|\bperfil de\b|\bnumero de cuenta\b",
     "No se almacenan ni se buscan datos personales, y no se construyen perfiles de personas."),
    ("predicción",
     _ORDEN + r"(supon|estima|predice|pronostica|proyecta|adivina)\b"
     r"|\b(inventa|inventate|inventar|invente)\b|\b(cuanto|cual|como) sera\b|\bque pasara\b|\bva a (subir|bajar)\b",
     "No se inventan, estiman ni proyectan cifras. Solo se muestra lo que está en el corpus, con su fuente y su fecha."),
]
PATRON_VEREDICTO = (r"\b(es|son|sera|seria|fue) (verdad|verdadera|verdaderas|verdadero|falsa|falsas|falso|cierto|cierta|"
                    r"mentira|real)\b|\bfake news\b|\bnoticias? falsas?\b|\b(desmiente|desmentir|bulo)\b"
                    r"|\bconfirma(me)? (que|si)\b")
AVISO_VEREDICTO = ("El sistema no etiqueta noticias como verdaderas o falsas. Muestra qué hay en el corpus, "
                   "de quién proviene y qué falta verificar; la conclusión es de la persona revisora.")

# --- Intenciones ------------------------------------------------------------------
PATRON_AGENDA = (
    r"\btop ?\d+\b|\bagenda\b|\b(merecen|merece|ameritan|amerita) (revision|atencion)\b"
    r"|\b(que|cuales) (\w+ ){0,4}(temas|casos|noticias|eventos|senales|historias|asuntos)\b.*"
    r"\b(revis\w+|prioriz\w+|prioritari\w+|prioridad|importantes?|urgentes?|relevantes?|atender|atencion|cubrir|"
    r"destacad\w+|merec\w+)\b"
    r"|\b(debo|deberia|debemos|deberiamos|conviene|toca) (revisar|cubrir|atender|priorizar|investigar)\b"
    r"|\b(los|las|lo) mas (urgentes?|importantes?|relevantes?|novedos[oa]s?|prioritari[oa]s?)\b"
    r"|\bque (hay|tenemos) (para )?(hoy|revisar)\b|\b(casos|temas) (pendientes|por revisar|sin revisar)\b")
PATRON_CIFRA = (
    r"\b(cuant[oa]s?|a cuanto|de cuanto|en cuanto)\b"
    r"|\bque (porcentaje|cifra|monto|cantidad|numero|tasa|precio|costo|valor|magnitud)\b"
    r"|\bcual (es|fue|era|seria) (el|la) (cifra|porcentaje|monto|cantidad|numero|tasa|precio|costo|valor|total|nivel|"
    r"magnitud|tarifa|salario|presupuesto)\b")
PATRON_ACTUAL = (r"\b(hoy|actual|actualmente|ahora|vigente|ayer|en este momento|al dia de hoy)\b"
                 r"|\b(este|esta|el ultimo|la ultima|el pasado|la pasada) (ano|mes|semana|trimestre)\b")
PATRON_SISMO = r"\b(sismo|sismos|temblor|temblores|terremoto|terremotos|sismic[oa]s?|teluric[oa]s?)\b"
# Con estas palabras se pregunta por lo que publican los medios, no por el dato oficial.
PATRON_PRENSA = r"\b(noticias?|titulares?|medios|prensa|reportan?|publican?|dicen|cobertura)\b"
PATRON_MAS_FUERTE = r"\bmas (fuerte|fuertes|grande|grandes|intenso|intensos)\b|\bmayor(es)? magnitud(es)?\b"
PATRON_MAGNITUD_MINIMA = (r"(?:mayor(?:es)?(?: o igual(?:es)?)? (?:a|de|que)|mas de|superior(?:es)? a|al menos|"
                          r"desde|por encima de)\s*(\d+(?:[.,]\d+)?)")
PATRON_MAGNITUD_EXACTA = r"\bmagnitud (?:de )?(\d+(?:[.,]\d+)?)\b"

NUMEROS_EN_PALABRAS = {"dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
                       "nueve": 9, "diez": 10, "doce": 12, "quince": 15, "veinte": 20}
MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
         "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
NOMBRE_MES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
              "octubre", "noviembre", "diciembre"]

TEMAS_EN_CONSULTA = {
    "economia": ["econom", "inflacion", "empleo", "finanz", "precios"],
    "logistica_canal": ["logist", "canal", "puerto", "maritim", "navier", "comercio exterior"],
    "turismo": ["turis", "hotel"],
    "servicios_publicos": ["servicios publicos", "servicio publico", "agua", "electricidad", "transporte", "salud"],
    "eventos_naturales": ["eventos naturales", "evento natural", "clima", "sismo", "temblor", "lluvia", "inundacion",
                          "desastre"],
    "regulacion": ["regula", "leyes", "ley ", "decreto", "normativ", "legisla"],
}
INDICADORES_EN_CONSULTA = {
    "FP.CPI.TOTL.ZG": ["inflacion", "ipc", "indice de precios", "precios al consumidor"],
    "NY.GDP.MKTP.KD.ZG": ["pib", "producto interno", "crecimiento economico", "crecimiento de la economia",
                          "crecio la economia", "economia crecio"],
    "SL.UEM.TOTL.ZS": ["desempleo", "desocupacion", "desempleados", "tasa de paro"],
    "SP.POP.TOTL": ["poblacion", "habitantes", "cuantas personas viven"],
    "IT.NET.USER.ZS": ["uso de internet", "usuarios de internet", "usan internet", "usa internet",
                       "acceso a internet", "penetracion de internet"],
    "NE.EXP.GNFS.ZS": ["exportaciones", "exportacion", "exporto", "exporta"],
}
PAISES_EN_CONSULTA = {
    "PAN": ["panama", "paname"], "CRI": ["costa rica", "costarric"], "COL": ["colombia"],
    "DOM": ["republica dominicana", "dominican"], "MEX": ["mexico", "mexican"], "GTM": ["guatemal"],
}
OTROS_PAISES = ["honduras", "nicaragua", "el salvador", "estados unidos", "eeuu", "venezuela", "ecuador", "peru",
                "chile", "argentina", "brasil", "china", "espana", "belice", "cuba", "canada", "bolivia", "uruguay",
                "paraguay"]
PALABRAS_DE_UBICACION = {"south", "north", "east", "west", "from", "near", "coast", "region", "offshore"}

AVISO_SOLO_TITULAR = "Basado únicamente en titular/metadatos."
AVISO_PRIORIDAD = "La prioridad ordena la revisión; no confirma la noticia ni habilita su publicación."
AVISO_ANUAL = ("Los indicadores del Banco Mundial son anuales e históricos: no describen la situación de hoy "
               "ni explican por sí solos lo que reporta una noticia.")
AVISO_CAJA_SISMOS = ("El catálogo sísmico del corpus cubre una caja regional (latitud 5 a 12, longitud −86 a −76): "
                     "incluye zonas fuera de Panamá. Solo sustenta hechos sísmicos, no daños ni pérdidas.")
AVISO_VERSIONES = ("Hay cifras distintas en los titulares: se muestran todas. Falta verificar cuál corresponde "
                   "y a qué período; el sistema no elige.")
ETIQUETA_PRENSA = "Lo que publican los medios (sin verificar)"
ETIQUETA_OFICIAL = "Dato oficial vinculado al caso"


# ---------------------------------------------------------------------------
# Verificación de lo que se va a responder
# ---------------------------------------------------------------------------
def _numeros(texto: str) -> list[str]:
    sin_citas = re.sub(r"\[[^\[\]]+?\]", " ", texto)
    sin_miles = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", sin_citas)
    return re.findall(r"\d+(?:\.\d+)?", sin_miles)


def cifras_sin_respaldo(afirmacion: dict, evidencia: dict) -> list[str]:
    """Números de la afirmación que no están en los campos que cita. Un valor redondeado
    cuenta como respaldado si el campo citado redondea a lo mismo."""
    citados: list[float] = []
    for cita in afirmacion["citas"]:
        valor = evidencia[cita["id_evidencia"]][cita["campo"]]
        citados += [float(n) for n in _numeros(json.dumps(valor, ensure_ascii=False))]
    faltan = []
    for numero in _numeros(afirmacion["texto"]):
        decimales = len(numero.partition(".")[2])
        if not any(abs(round(c, decimales) - float(numero)) < 1e-9 for c in citados):
            faltan.append(numero)
    return faltan


def verificar(afirmaciones: list[dict], evidencia: dict) -> tuple[list[dict], list[dict]]:
    """Separa las afirmaciones que se pueden mostrar de las que no tienen respaldo."""
    validas, descartadas = seguridad.validar_afirmaciones(afirmaciones, evidencia)
    for afirmacion in list(validas):
        faltan = cifras_sin_respaldo(afirmacion, evidencia)
        if faltan:
            validas.remove(afirmacion)
            descartadas.append({**afirmacion, "motivo_descarte": f"cifras que no están en lo citado: {', '.join(faltan)}"})
    return validas, descartadas


def formatear_valor(valor, unidad: str | None = None) -> str:
    """Valor de un indicador para leer: personas con separador de miles, lo demás con dos decimales."""
    if valor is None:
        return "sin dato"
    if unidad == "personas" or (abs(valor) >= 10000 and float(valor).is_integer()):
        return f"{round(valor):,}"
    texto = f"{valor:.2f}".rstrip("0").rstrip(".")
    return "0" if texto in ("-0", "") else texto


def _cuantos(cantidad: int, uno: str, varios: str) -> str:
    return f"{cantidad} {uno if cantidad == 1 else varios}"


def _inicial_minuscula(nombre: str) -> str:
    """«Crecimiento del PIB» -> «crecimiento del PIB»: sin tocar las siglas."""
    return nombre[:1].lower() + nombre[1:]


# ---------------------------------------------------------------------------
# Motor
# ---------------------------------------------------------------------------
class Motor:
    def __init__(self, corpus: Corpus, estado_de=None):
        self.corpus = corpus
        self._estado_de = estado_de or (lambda evento: None)
        self._evidencia = {e["id_evento"]: fuentes.evidencia_de_evento(e) for e in corpus.eventos}
        self._eventos = {e["id_evento"]: e for e in corpus.eventos}
        self._indice = Indice({e["id_evento"]: self._texto_de_evento(e) for e in corpus.eventos})
        # Núcleo de IA (equipo B): búsqueda semántica y respuesta redactada por el LLM.
        # Solo si están instaladas las dependencias del núcleo; si no, el motor funciona igual.
        self._semantico = self._cargar_semantico(corpus)
        self._series: dict[tuple[str, str], dict[int, dict]] = {}
        for fila in corpus.indicadores:
            self._series.setdefault((fila["pais_iso3"], fila["indicador_id"]), {})[fila["anio"]] = fila
        lugares = {palabra for sismo in corpus.sismos for palabra in re.findall(r"[a-z]{4,}", normalizar(sismo["lugar"]))}
        self._lugares_sismicos = lugares - PALABRAS_DE_UBICACION

    @staticmethod
    def _texto_de_evento(evento: dict) -> str:
        titulos = " ".join(noticia["titulo"] for noticia in evento["noticias"])
        return f"{titulos} {' '.join(evento['medios'])}"

    # -- piezas de respuesta -------------------------------------------------
    def _base(self, pregunta: str, tipo: str) -> dict:
        return {
            "pregunta": pregunta, "tipo": tipo, "abstencion": False, "titulo": "", "resumen": None,
            "afirmaciones": [], "descartadas": [], "versiones": [], "evidencia": {}, "casos": [],
            "relacionados": [], "calculos": [], "series": [], "reglas": [], "faltante": [], "avisos": [],
            "recuperacion": None, "corte_utc": self.corpus.fecha_corte, "version_reglas": config.VERSION_REGLAS,
        }

    def _abstenerse(self, respuesta: dict, titulo: str, resumen: str, faltante: list[str] | None = None) -> dict:
        respuesta.update(abstencion=True, tipo="abstencion", titulo=titulo, resumen=resumen)
        respuesta["faltante"] = faltante or []
        return respuesta

    def tarjeta(self, evento: dict) -> dict:
        """Resumen de un caso para mostrarlo junto a una respuesta."""
        prioridad = evento["prioridad"]
        ficha = self.corpus.fichas.get(evento["id_evento"])
        evidencia, no_confiable = self._evidencia[evento["id_evento"]]
        aportes = sorted(prioridad["componentes"].items(), key=lambda par: -par[1]["aporte"])
        return {
            "id_evento": evento["id_evento"],
            "id_caso": f"CASO-{evento['id_evento']}",
            "posicion": prioridad["posicion"],
            "puntaje": prioridad["puntaje"],
            "nivel": prioridad["nivel"],
            "titulo": evento["titulo_representativo"],
            "no_confiable": bool(no_confiable) and not evidencia,
            "tema": evento["tema"],
            "n_noticias": evento["n_noticias"],
            "fuentes_independientes": evento["n_fuentes_independientes"],
            "estado_evidencia": evento["estado_evidencia"],
            "motivo_estado_evidencia": evento["motivo_estado_evidencia"],
            "dato_oficial": bool(evento.get("contexto")),
            "contradiccion": bool(evento["posibles_contradicciones"]),
            "antigua": any(noticia.get("antiguedad") for noticia in evento["noticias"]),
            "por_que": [{"componente": clave, "nombre": COMPONENTES[clave][0], "aporte": componente["aporte"],
                         "peso": componente["peso"], "explicacion": componente["explicacion"]}
                        for clave, componente in aportes[:3]],
            "vacios": self._pendientes(evento, ficha, evidencia),
            "estado_revision": self._estado_de(evento),
            "tiene_ficha": ficha is not None,
        }

    @staticmethod
    def _pendientes(evento: dict, ficha: dict | None, evidencia: dict) -> list[str]:
        if ficha and ficha.get("que_falta_verificar"):
            return ficha["que_falta_verificar"]
        if not evidencia:
            return ["No hay evidencia utilizable: el único titular se marcó como contenido no confiable."]
        return redaccion_por_plantilla(evento, evidencia, False)["que_falta_verificar"]

    def _afirmaciones_de_evento(self, evento: dict) -> list[dict]:
        """Lo ya validado en la ficha; si no hay ficha, lo que cada fuente dice, citado tal cual."""
        ficha = self.corpus.fichas.get(evento["id_evento"])
        evidencia, _ = self._evidencia[evento["id_evento"]]
        if ficha and ficha.get("afirmaciones"):
            return ficha["afirmaciones"]
        if not evidencia:
            return []
        return redaccion_por_plantilla(evento, evidencia, False)["afirmaciones"]

    def versiones(self, evento: dict) -> list[dict]:
        """Cifras en conflicto dentro de un evento, cada una con quién la publica."""
        noticias = {noticia["id_noticia"]: noticia for noticia in evento["noticias"]}
        return [{
            "cifra": version["cifra"],
            "id_evento": evento["id_evento"],
            "fuentes": [{"id_noticia": i, "medio": noticias[i]["medio"], "titulo": noticias[i]["titulo"]}
                        for i in version["ids_noticia"] if i in noticias],
        } for version in evento["posibles_contradicciones"]]

    @staticmethod
    def _cita_titular_con_cifra(afirmacion: dict, evidencia: dict) -> bool:
        for cita in afirmacion["citas"]:
            elemento = evidencia.get(cita["id_evidencia"], {})
            if elemento.get("tipo") == "noticia" and re.search(r"\d", elemento.get("titulo", "")):
                return True
        return False

    def _agregar(self, respuesta: dict, evento: dict, afirmacion: dict, etiqueta: str | None = None) -> None:
        evidencia, _ = self._evidencia[evento["id_evento"]]
        respuesta["afirmaciones"].append({**afirmacion, "id_evento": evento["id_evento"], "etiqueta": etiqueta})
        for cita in afirmacion["citas"]:
            if cita["id_evidencia"] in evidencia:
                respuesta["evidencia"][cita["id_evidencia"]] = evidencia[cita["id_evidencia"]]

    def _agregar_evento(self, respuesta: dict, evento: dict, pide_cifra: bool) -> int:
        """Suma las afirmaciones citables del evento. Si se pidió una cifra, solo cuentan
        los titulares que traen un número; el dato oficial se agrega como contexto.
        Devuelve cuántas afirmaciones responden a lo preguntado."""
        evidencia, _ = self._evidencia[evento["id_evento"]]
        afirmaciones = self._afirmaciones_de_evento(evento)
        if not pide_cifra:
            for afirmacion in afirmaciones[:MAXIMO_AFIRMACIONES_POR_EVENTO]:
                self._agregar(respuesta, evento, afirmacion)
            respuesta["versiones"] += self.versiones(evento)
            return min(len(afirmaciones), MAXIMO_AFIRMACIONES_POR_EVENTO)

        con_cifra = [a for a in afirmaciones if self._cita_titular_con_cifra(a, evidencia)]
        if not con_cifra:
            return 0
        for afirmacion in con_cifra[:MAXIMO_AFIRMACIONES_POR_EVENTO]:
            self._agregar(respuesta, evento, afirmacion, ETIQUETA_PRENSA)
        for afirmacion in afirmaciones:
            if afirmacion["tipo"] == "hecho" and afirmacion not in con_cifra:
                self._agregar(respuesta, evento, afirmacion, ETIQUETA_OFICIAL)
        respuesta["versiones"] += self.versiones(evento)
        return len(con_cifra)

    # -- núcleo de IA (equipo B) -----------------------------------------------
    @staticmethod
    def _cargar_semantico(corpus: Corpus) -> dict | None:
        from .puente import nucleo_completo
        if not corpus.eventos or not nucleo_completo():
            return None
        try:
            from nucleo import consultar
            return {"buscador": consultar.BuscadorSemantico(corpus.eventos),
                    "redactar": consultar.redactar_respuesta}
        except Exception:  # sin modelo de embeddings u otra falta del entorno: motor sin semántica
            return None

    def _redaccion_llm(self, pregunta: str, eventos: list[dict]) -> dict | None:
        """Respuesta redactada por el LLM con la evidencia de esos eventos, ya validada
        por el núcleo. None si no hay LLM, si dice que no alcanza o si no pasa el validador."""
        if self._semantico is None:
            return None
        evidencia, contradicciones = {}, []
        for evento in eventos:
            evidencia.update(self._evidencia[evento["id_evento"]][0])
            contradicciones += evento["posibles_contradicciones"]
        try:
            return self._semantico["redactar"](pregunta, evidencia, contradicciones)
        except Exception:
            return None

    def _rescate_semantico(self, pregunta: str, respuesta: dict) -> dict | None:
        """BM25 no encontró respuesta. Los eventos más parecidos por significado se le
        pasan al LLM, que decide si responden la pregunta. Sin LLM, o si dice que no, o
        si su texto no pasa el validador, se mantiene la abstención (devuelve None)."""
        try:
            candidatos = [(i, s) for i, s in self._semantico["buscador"].buscar(pregunta, 3)
                          if s >= config.UMBRAL_CANDIDATO_SEMANTICO]
        except Exception:
            return None
        if not candidatos:
            return None
        redaccion = self._redaccion_llm(pregunta, [self._eventos[i] for i, _ in candidatos])
        if redaccion is None:
            return None

        # Solo los casos que la respuesta realmente cita
        citados = set(seguridad.citas_en_texto(redaccion["texto"]))
        def citado(id_evento: str) -> bool:
            return any(c == i or c.startswith(i + ":") for c in citados for i in self._evidencia[id_evento][0])
        eventos = [self._eventos[i] for i, _ in candidatos if citado(i)]
        if not eventos:
            return None

        respuesta["recuperacion"] = {
            "metodo": "búsqueda semántica (bge-m3) y juicio del LLM sobre si la evidencia responde",
            "umbral_similitud": config.UMBRAL_CANDIDATO_SEMANTICO,
            "candidatos": [{"id_evento": i, "titulo": self._eventos[i]["titulo_representativo"], "similitud": s}
                           for i, s in candidatos],
        }
        respuesta["casos"] = [self.tarjeta(evento) for evento in eventos]
        for evento in eventos:
            self._agregar_evento(respuesta, evento, False)
        respuesta["titulo"] = f"{_cuantos(len(eventos), 'caso', 'casos')} del corpus sobre lo consultado"
        respuesta["resumen"] = redaccion["texto"]
        respuesta["resumen_redactado_por"] = redaccion["modelo"]
        respuesta["avisos"].append("Respuesta encontrada por significado y redactada por un LLM con la evidencia "
                                   "citada; cada cifra se verificó contra lo que cita.")
        if any(evento.get("aviso_alcance") for evento in eventos):
            respuesta["avisos"].append(AVISO_SOLO_TITULAR)
        if respuesta["versiones"]:
            respuesta["avisos"].append(AVISO_VERSIONES)
        return respuesta

    # -- entrada ---------------------------------------------------------------
    def responder(self, pregunta: str | None) -> dict:
        inicio = time.perf_counter()
        pregunta = " ".join((pregunta or "").split())[:LIMITE_PREGUNTA]
        respuesta = self._resolver(pregunta)
        respuesta["afirmaciones"], respuesta["descartadas"] = verificar(respuesta["afirmaciones"], respuesta["evidencia"])
        citados = {cita["id_evidencia"] for afirmacion in respuesta["afirmaciones"] for cita in afirmacion["citas"]}
        respuesta["evidencia"] = {i: e for i, e in respuesta["evidencia"].items() if i in citados}
        respuesta["tiempo_ms"] = round((time.perf_counter() - inicio) * 1000, 1)
        return respuesta

    def _resolver(self, pregunta: str) -> dict:
        texto = normalizar(pregunta)
        if not re.search(r"\w", texto):
            return self._ayuda(pregunta)

        rechazo = self._rechazo(pregunta, texto)
        if rechazo:
            return rechazo
        for categoria, patron, mensaje in FUERA_DE_ALCANCE:
            if re.search(patron, texto):
                return self._fuera_de_alcance(pregunta, categoria, mensaje)

        reglas = self._reglas(pregunta, texto)
        if reglas:
            return reglas
        if re.search(PATRON_AGENDA, texto):
            return self._agenda(pregunta, texto)

        respuesta = self._sobre_el_contenido(pregunta, texto)
        if re.search(PATRON_VEREDICTO, texto) and respuesta["tipo"] != "ayuda":
            # Se pidió decir si algo es cierto: se muestra la evidencia, sin concluir
            respuesta["avisos"].insert(0, AVISO_VEREDICTO)
            if not respuesta["abstencion"]:
                respuesta["tipo"] = "sin_veredicto"
        return respuesta

    def _sobre_el_contenido(self, pregunta: str, texto: str) -> dict:
        if not re.search(PATRON_PRENSA, texto):
            if re.search(PATRON_SISMO, texto) and self._pide_catalogo_sismico(texto):
                return self._sismos(pregunta, texto)
            indicador = next((codigo for codigo, frases in INDICADORES_EN_CONSULTA.items()
                              if any(re.search(rf"\b{re.escape(frase)}", texto) for frase in frases)), None)
            if indicador and any(codigo == indicador for _, codigo in self._series):
                return self._indicador(pregunta, texto, indicador)
        return self._busqueda(pregunta, texto)

    # -- lo que no se atiende --------------------------------------------------
    def _rechazo(self, pregunta: str, texto: str) -> dict | None:
        inyeccion = seguridad.detectar_inyeccion(pregunta)
        secreto = any(re.search(patron, texto) for patron in PATRONES_SECRETO)
        accion = any(re.search(patron, texto) for patron in PATRONES_ACCION)
        if not (inyeccion or secreto or accion):
            return None
        respuesta = self._base(pregunta, "rechazo")
        respuesta["abstencion"] = True
        if inyeccion or secreto:
            respuesta["titulo"] = "Consulta rechazada: no se revelan instrucciones ni secretos"
            respuesta["resumen"] = ("La consulta pide cambiar el comportamiento del sistema o revelar su configuración. "
                                    "Las reglas no se modifican desde una pregunta ni desde el texto de una fuente, "
                                    "y las credenciales no forman parte de lo que el sistema puede leer.")
        else:
            respuesta["titulo"] = "Consulta rechazada: las consultas son de solo lectura"
            respuesta["resumen"] = ("Consultar no publica, aprueba, descarta ni cambia puntajes o estados. "
                                    "Esas decisiones las toma una persona en la ficha del caso y quedan firmadas "
                                    "en la bitácora. Nada se publica de forma automática.")
        respuesta["faltante"] = ["Reformule como una pregunta sobre el contenido del corpus."]
        return respuesta

    def _fuera_de_alcance(self, pregunta: str, categoria: str, mensaje: str) -> dict:
        respuesta = self._base(pregunta, "fuera_de_alcance")
        respuesta.update(abstencion=True, titulo=f"Fuera del alcance del prototipo: {categoria}", resumen=mensaje)
        respuesta["faltante"] = ["Puede preguntar qué reportan los medios sobre un tema, qué dato oficial hay "
                                 "y de qué año, o qué casos merecen revisión."]
        return respuesta

    def _ayuda(self, pregunta: str) -> dict:
        respuesta = self._base(pregunta, "ayuda")
        respuesta.update(abstencion=True, titulo="Escriba una pregunta sobre el corpus",
                         resumen="Por ejemplo: «¿Qué cinco temas merecen revisión para la agenda de Panamá y por qué?»")
        return respuesta

    # -- cómo funciona el sistema --------------------------------------------
    def _reglas(self, pregunta: str, texto: str) -> dict | None:
        bloques, ejemplo = [], None
        como = re.search(r"\b(como|formula|calcul\w+|pesos?|pondera\w+|componentes?|significa|que es|que mide|regla)\b", texto)
        if re.search(r"\b(puntaje|prioridad|prioriza\w*|priorizacion|ranking)\b", texto) and como:
            bloques.append({
                "titulo": "Cómo se calcula el puntaje de atención",
                "texto": f"P = {' + '.join(f'{peso}{clave}' for clave, peso in config.PESOS.items())}. Cada componente "
                         "va de 0 a 1 y se multiplica por su peso; el puntaje va de 0 a 100. Sirve para ordenar la "
                         "revisión: no es una probabilidad de verdad.",
                "puntos": [f"{clave} · {COMPONENTES[clave][0]} (peso {peso}): {COMPONENTES[clave][1]}"
                           for clave, peso in config.PESOS.items()]
                + ["Niveles sin solapamiento: bajo [0, 40), medio [40, 70), alto [70, 100].",
                   "Empates: primero mayor urgencia y luego el ID del evento.",
                   f"Una noticia recirculada nunca pasa del nivel bajo (tope {config.TOPE_RECIRCULADA}).",
                   f"Versión de reglas vigente: {config.VERSION_REGLAS}."],
            })
        if re.search(r"\b(fuentes? independientes?|procedencias?|replic\w+|misma agencia|corrobora\w+)\b", texto):
            ejemplo = next((e for e in self.corpus.eventos if e["n_noticias"] > e["n_fuentes_independientes"]), None)
            bloques.append({
                "titulo": "Repetición no es corroboración",
                "texto": "Si varios medios replican el mismo cable, cuentan como una sola procedencia. Cinco medios "
                         "con el mismo titular de agencia suman una fuente independiente, no cinco.",
                "puntos": [f"Dos titulares casi idénticos (similitud de {config.UMBRAL_REPLICA} o más) en medios "
                           "distintos se tratan como la misma procedencia.",
                           "El componente E del puntaje y el estado de evidencia usan las procedencias "
                           "independientes, no la cantidad de notas: duplicar no sube la prioridad."],
            })
        if re.search(r"\bestados? de evidencia\b|\bevidencia (insuficiente|parcial|suficiente)\b", texto) and como:
            bloques.append({
                "titulo": "Estado de evidencia: independiente del puntaje",
                "texto": "Una prioridad alta con evidencia insuficiente requiere investigación; no habilita publicar.",
                "puntos": ["Insuficiente: una sola procedencia y ningún dato oficial vinculado.",
                           "Parcial: dos o más procedencias independientes o un dato oficial, pero no ambos; "
                           "o los titulares reportan cifras distintas.",
                           "Suficiente para el borrador: dos o más procedencias independientes y un dato oficial.",
                           "El sistema nunca etiqueta una noticia como verdadera o falsa."],
            })
        if re.search(r"\bestados? de revision\b|\bque significa (aprobar|aprobado)\b|\baprobar (es|significa)\b", texto):
            bloques.append({
                "titulo": "Estados de revisión humana",
                "texto": "Aprobar un borrador no significa publicarlo: no existe un estado para publicar.",
                "puntos": ["Nuevo · En revisión · Requiere evidencia · Aprobado como borrador · Descartado.",
                           "Cada cambio lo firma una persona y queda en la bitácora con fecha y nota.",
                           "No se puede aprobar un caso con evidencia insuficiente ni un borrador con contenido "
                           "sin respaldo, por alto que sea su puntaje."],
            })
        if not bloques:
            return None
        respuesta = self._base(pregunta, "reglas")
        respuesta.update(titulo=bloques[0]["titulo"], reglas=bloques)
        if ejemplo:
            respuesta["casos"] = [self.tarjeta(ejemplo)]
            respuesta["resumen"] = "Ejemplo del corpus: un evento con más notas que procedencias independientes."
        return respuesta

    # -- agenda (CU-01) --------------------------------------------------------
    def _agenda(self, pregunta: str, texto: str) -> dict:
        respuesta = self._base(pregunta, "agenda")
        en_digitos = [int(n) for n in re.findall(r"\b\d{1,2}\b", texto) if 1 <= int(n) <= 20]
        en_palabras = [valor for palabra, valor in NUMEROS_EN_PALABRAS.items() if re.search(rf"\b{palabra}\b", texto)]
        cantidad = (en_digitos or en_palabras or [5])[0]

        eventos, filtros = list(self.corpus.eventos), []
        tema = next((t for t, claves in TEMAS_EN_CONSULTA.items() if any(clave in texto + " " for clave in claves)), None)
        if tema:
            eventos = [e for e in eventos if e["tema"] == tema]
            filtros.append(f"tema {NOMBRE_TEMA[tema].lower()}")
        nivel = next((n for n in ("alto", "medio", "bajo") if re.search(rf"\b(prioridad|nivel) {n[:-1]}[oa]\b", texto)), None)
        if nivel:
            eventos = [e for e in eventos if e["prioridad"]["nivel"] == nivel]
            filtros.append(f"nivel {nivel}")
        if re.search(r"\b(sin evidencia|evidencia insuficiente|falta evidencia|requieren? (investigacion|evidencia))\b", texto):
            eventos = [e for e in eventos if e["estado_evidencia"] == "insuficiente"]
            filtros.append("evidencia insuficiente")
        elif re.search(r"\b(evidencia suficiente|con evidencia|respaldad[oa]s?|listos? para (el )?borrador)\b", texto):
            eventos = [e for e in eventos if e["estado_evidencia"] == "suficiente para el borrador"]
            filtros.append("evidencia suficiente para el borrador")

        orden = "puntaje de atención"
        for clave, patron in (("U", r"\burgent"), ("N", r"\bnovedos"), ("I", r"\bimpacto\b")):
            if re.search(patron, texto):
                eventos.sort(key=lambda e, c=clave: (-e["prioridad"]["componentes"][c]["valor"], e["prioridad"]["posicion"]))
                orden = COMPONENTES[clave][0].lower()
                break

        elegidos = eventos[:cantidad]
        respuesta["casos"] = [self.tarjeta(evento) for evento in elegidos]
        respuesta["recuperacion"] = {"metodo": "ranking del núcleo (sin búsqueda)", "filtros": filtros, "orden": orden}
        if not elegidos:
            return self._abstenerse(respuesta, "Ningún caso cumple ese filtro",
                                    f"La bandeja no tiene casos con {', '.join(filtros) or 'esas condiciones'}.")

        detalle = f" con {', '.join(filtros)}" if filtros else ""
        respuesta["titulo"] = f"{_cuantos(len(elegidos), 'caso', 'casos')} para revisar{detalle}, por {orden}"
        respuesta["resumen"] = ("Orden calculado por el sistema sobre el snapshot. Cada caso muestra por qué sube, "
                                "qué evidencia hay y qué falta verificar.")
        respuesta["calculos"].append({"descripcion": "Casos mostrados", "valor": f"{len(elegidos)} de {len(eventos)}"})
        insuficientes = sum(1 for e in elegidos if e["estado_evidencia"] == "insuficiente")
        if insuficientes:
            respuesta["calculos"].append({
                "descripcion": "Con evidencia insuficiente: requieren investigación antes de producir",
                "valor": str(insuficientes)})
        respuesta["avisos"] = [AVISO_PRIORIDAD]
        if any(e.get("aviso_alcance") for e in elegidos):
            respuesta["avisos"].append(AVISO_SOLO_TITULAR)
        return respuesta

    # -- sismos (USGS) ---------------------------------------------------------
    def _pide_catalogo_sismico(self, texto: str) -> bool:
        """True si la pregunta trae un filtro propio del catálogo y no es sobre una noticia."""
        return bool(re.search(r"\b(usgs|catalogo|registr\w+|cuant[oa]s)\b|\b(?:19|20)\d{2}\b", texto)
                    or re.search(PATRON_MAS_FUERTE, texto) or re.search(PATRON_MAGNITUD_MINIMA, texto)
                    or re.search(PATRON_MAGNITUD_EXACTA, texto)
                    or any(re.search(rf"\b{mes}\b", texto) for mes in MESES))

    def _sismos(self, pregunta: str, texto: str) -> dict:
        respuesta = self._base(pregunta, "sismos")
        sismos = [s for s in self.corpus.sismos if s["magnitud"] is not None and s["fecha_utc"]]
        anios_corpus = sorted({s["fecha_utc"][:4] for s in sismos})
        cobertura = ", ".join(anios_corpus) or "ningún año"
        filtros = []
        respuesta["avisos"] = [AVISO_CAJA_SISMOS]

        anios = re.findall(r"\b(?:19|20)\d{2}\b", texto)
        fuera = [anio for anio in anios if anio not in anios_corpus]
        if fuera:
            self._relacionar_eventos(respuesta, texto)
            return self._abstenerse(respuesta, f"El corpus no tiene registros sísmicos de {', '.join(fuera)}",
                                    f"El catálogo de USGS incluido en el snapshot cubre {cobertura}.",
                                    ["El catálogo de USGS del período solicitado."])
        if not anios and re.search(PATRON_ACTUAL, texto):
            self._relacionar_eventos(respuesta, texto)
            return self._abstenerse(respuesta, "No hay registros sísmicos recientes en el corpus",
                                    f"El catálogo de USGS del snapshot cubre {cobertura}: no sirve para confirmar "
                                    "un sismo de hoy.",
                                    ["Una consulta actual al catálogo de USGS, con su hora de actualización."])
        if anios:
            sismos = [s for s in sismos if s["fecha_utc"][:4] in anios]
            filtros.append(f"año {', '.join(anios)}")

        mes = next((numero for nombre, numero in MESES.items() if re.search(rf"\b{nombre}\b", texto)), None)
        if mes:
            sismos = [s for s in sismos if int(s["fecha_utc"][5:7]) == mes]
            filtros.append(NOMBRE_MES[mes])

        minimo = re.search(PATRON_MAGNITUD_MINIMA, texto)
        exacta = re.search(PATRON_MAGNITUD_EXACTA, texto)
        if minimo:
            umbral = float(minimo.group(1).replace(",", "."))
            incluye_igual = bool(re.search(r"o igual|al menos|desde", minimo.group(0)))
            sismos = [s for s in sismos if s["magnitud"] > umbral or (incluye_igual and s["magnitud"] == umbral)]
            filtros.append(f"magnitud {'≥' if incluye_igual else '>'} {umbral:g}")
        elif exacta:
            valor = float(exacta.group(1).replace(",", "."))
            sismos = [s for s in sismos if abs(s["magnitud"] - valor) < 0.05]
            filtros.append(f"magnitud {valor:g}")

        pedidos = sorted(lugar for lugar in self._lugares_sismicos if re.search(rf"\b{lugar}\b", texto))
        if pedidos:
            sismos = [s for s in sismos if any(re.search(rf"\b{lugar}\b", normalizar(s["lugar"])) for lugar in pedidos)]
            filtros.append(f"lugar {', '.join(pedidos)}")

        total = len(sismos)
        mas_fuerte = re.search(PATRON_MAS_FUERTE, texto)
        if mas_fuerte or minimo or exacta:
            sismos.sort(key=lambda s: (-s["magnitud"], s["fecha_utc"]))
        else:
            sismos.sort(key=lambda s: s["fecha_utc"], reverse=True)
        if mas_fuerte:
            uno_solo = re.search(r"\bmas (fuerte|grande|intenso)\b|\bmayor magnitud\b", texto)
            sismos = sismos[:1 if uno_solo else 5]

        descripcion = ", ".join(filtros) or "sin filtros"
        respuesta["recuperacion"] = {"metodo": "filtro sobre el catálogo sísmico de USGS", "filtros": filtros}
        if not sismos:
            self._relacionar_eventos(respuesta, texto)
            return self._abstenerse(respuesta, "Ningún registro sísmico cumple ese filtro",
                                    f"Se buscó en {len(self.corpus.sismos)} registros de USGS ({cobertura}) con: {descripcion}.")

        for sismo in sismos[:MAXIMO_SISMOS]:
            id_evidencia, elemento = fuentes.evidencia_de_sismo(sismo)
            respuesta["evidencia"][id_evidencia] = elemento
            respuesta["afirmaciones"].append({
                "texto": (f"USGS registró un sismo de magnitud {elemento['magnitud']} [{id_evidencia}:magnitud] "
                          f"({elemento['lugar']}) [{id_evidencia}:lugar] el {elemento['fecha_utc'][:10]} UTC "
                          f"[{id_evidencia}:fecha_utc]."),
                "tipo": "hecho",
                "citas": [{"id_evidencia": id_evidencia, "campo": campo} for campo in ("magnitud", "lugar", "fecha_utc")],
            })
        respuesta["titulo"] = "Registros del catálogo sísmico de USGS"
        respuesta["calculos"].append({"descripcion": f"Registros que cumplen ({descripcion})", "valor": str(total)})
        if total > len(respuesta["afirmaciones"]):
            respuesta["calculos"].append({"descripcion": "Mostrados", "valor": str(len(respuesta["afirmaciones"]))})
        if not anios:
            respuesta["avisos"].insert(0, f"No se indicó año: el catálogo del corpus cubre {cobertura}.")
        self._relacionar_eventos(respuesta, texto)
        return respuesta

    # -- indicadores (Banco Mundial) -----------------------------------------
    def _indicador(self, pregunta: str, texto: str, codigo: str) -> dict:
        respuesta = self._base(pregunta, "indicador")
        series = {pais: serie for (pais, c), serie in self._series.items() if c == codigo}
        nombre = next(iter(next(iter(series.values())).values()))["nombre"]
        nombre_en_frase = _inicial_minuscula(nombre)

        ajenos = [pais for pais in OTROS_PAISES if re.search(rf"\b{pais}\b", texto)]
        paises = [iso for iso, nombres in PAISES_EN_CONSULTA.items()
                  if iso in series and any(n in texto for n in nombres)]
        if not paises and ajenos:
            cubiertos = ", ".join(sorted(PAISES.get(pais, pais) for pais in series))
            return self._abstenerse(respuesta, f"El corpus no tiene ese dato para {ajenos[0].title()}",
                                    f"Los indicadores del snapshot cubren: {cubiertos}.",
                                    [f"El indicador «{nombre}» de ese país, de una fuente oficial."])
        paises = paises or ["PAN"]
        if "PAN" not in series and paises == ["PAN"]:
            paises = [sorted(series)[0]]
        respuesta["recuperacion"] = {"metodo": "consulta estructurada a indicadores del Banco Mundial",
                                     "filtros": [nombre] + [PAISES.get(pais, pais) for pais in paises]}
        if ajenos:
            respuesta["avisos"].append(f"El corpus no tiene datos de {', '.join(a.title() for a in ajenos)}.")

        subnacional = next((lugar for lugar in config.LUGARES_PANAMA
                            if lugar not in ("panama", "canal") and re.search(rf"\b{lugar}\b", texto)), None)
        if subnacional:
            return self._abstenerse(respuesta, f"El corpus no tiene «{nombre_en_frase}» para {subnacional.title()}",
                                    "Los indicadores del Banco Mundial del snapshot son nacionales: no hay desglose "
                                    "por provincia, distrito ni corregimiento.",
                                    ["Una fuente oficial con desglose territorial y su período."])

        principal = series[paises[0]]
        con_valor = sorted(anio for anio, fila in principal.items() if fila["valor"] is not None)
        if not con_valor:
            return self._abstenerse(respuesta, f"Sin dato de «{nombre_en_frase}» en el corpus",
                                    "La fuente no publica ninguna observación para ese país en el período del snapshot.")
        ultimo = con_valor[-1]

        pedidos = sorted({int(anio) for anio in re.findall(r"\b(?:19|20)\d{2}\b", texto)})
        pide_serie = bool(re.search(r"\b(evolucion|serie|tendencia|historic[oa]|ultimos anos)\b", texto)
                          or (len(pedidos) >= 2 and re.search(r"\b(entre|desde|hasta|de \d{4} a)\b", texto)))
        fuera = [anio for anio in pedidos if anio not in principal]
        sin_dato = [anio for anio in pedidos if anio in principal and principal[anio]["valor"] is None]
        etiqueta = None

        if fuera or sin_dato or (not pedidos and re.search(PATRON_ACTUAL, texto)):
            pedido = ", ".join(str(anio) for anio in fuera + sin_dato) or "el período actual"
            if sin_dato and not fuera:
                resumen = ("El Banco Mundial no publica esa observación. Se conserva como «sin dato»: "
                           "no equivale a cero.")
            else:
                resumen = (f"Los indicadores del snapshot son anuales y cubren de {min(principal)} a {max(principal)}. "
                           "No se presenta un dato anual como si fuera una medición de hoy.")
            self._abstenerse(respuesta, f"El corpus no tiene «{nombre_en_frase}» para {pedido}", resumen,
                             ["Una medición oficial del período solicitado, con su fuente, fecha y unidad."])
            anios, etiqueta = [ultimo], "Lo más reciente que sí está en el corpus"
        elif pide_serie:
            inicio = pedidos[0] if pedidos else con_valor[max(0, len(con_valor) - 5)]
            fin = pedidos[-1] if len(pedidos) >= 2 else ultimo
            en_rango = [anio for anio in con_valor if inicio <= anio <= fin] or [ultimo]
            anios = sorted({en_rango[0], en_rango[-1]})
        elif pedidos:
            anios = pedidos
        else:
            anios = [ultimo]
            respuesta["avisos"].append(f"No se indicó año: se muestra el dato anual más reciente del corpus ({ultimo}).")

        for iso in paises:
            serie = series[iso]
            for anio in anios:
                fila = serie.get(anio)
                if not fila or fila["valor"] is None:
                    continue
                id_evidencia, elemento = fuentes.evidencia_de_indicador(fila)
                respuesta["evidencia"][id_evidencia] = elemento
                respuesta["afirmaciones"].append({
                    "texto": (f"Según el Banco Mundial, el dato anual de {anio} [{id_evidencia}:anio] de "
                              f"{nombre_en_frase} en {PAISES.get(iso, iso)} fue "
                              f"{formatear_valor(fila['valor'], fila['unidad'])} ({fila['unidad']}) [{id_evidencia}:valor]."),
                    "tipo": "hecho",
                    "citas": [{"id_evidencia": id_evidencia, "campo": "valor"},
                              {"id_evidencia": id_evidencia, "campo": "anio"}],
                    "etiqueta": etiqueta,
                })
            muestra = next(iter(serie.values()))
            respuesta["series"].append({
                "pais": iso, "pais_nombre": PAISES.get(iso, iso), "indicador_id": codigo, "nombre": nombre,
                "unidad": muestra["unidad"], "fuente_url": muestra["fuente_url"], "licencia": muestra["licencia"],
                "puntos": [{"anio": anio, "valor": serie[anio]["valor"], "id_evidencia": f"WB:{iso}:{codigo}:{anio}"}
                           for anio in sorted(serie)],
                "destacados": anios,
            })

        if not respuesta["abstencion"]:
            respuesta["titulo"] = f"{nombre} · {', '.join(PAISES.get(pais, pais) for pais in paises)}"
        respuesta["avisos"].append(AVISO_ANUAL)
        self._relacionar_eventos(respuesta, texto, codigo)
        return respuesta

    def _relacionar_eventos(self, respuesta: dict, texto: str, indicador: str | None = None) -> None:
        """Casos de la bandeja que tocan lo consultado. Si traen cifras en conflicto, se muestran todas."""
        relacionados = [e for e in self.corpus.eventos
                        if indicador and any(c.get("indicador_id") == indicador for c in e.get("contexto", []))]
        consulta = [termino for termino in terminos(texto) if not termino[0].isdigit()]
        for coincidencia in self._indice.buscar(consulta, 6):
            evento = self._eventos[coincidencia.id]
            if coincidencia.cobertura >= COBERTURA_SUFICIENTE and evento not in relacionados:
                relacionados.append(evento)

        for evento in relacionados[:MAXIMO_EVENTOS]:
            respuesta["casos"].append(self.tarjeta(evento))
            if not evento["posibles_contradicciones"]:
                continue
            respuesta["versiones"] += self.versiones(evento)
            evidencia, _ = self._evidencia[evento["id_evento"]]
            for afirmacion in self._afirmaciones_de_evento(evento):
                if self._cita_titular_con_cifra(afirmacion, evidencia):
                    self._agregar(respuesta, evento, afirmacion, ETIQUETA_PRENSA)
        if respuesta["versiones"]:
            respuesta["avisos"].append(AVISO_VERSIONES)

    # -- búsqueda general ------------------------------------------------------
    def _busqueda(self, pregunta: str, texto: str) -> dict:
        respuesta = self._base(pregunta, "busqueda")
        pide_cifra = bool(re.search(PATRON_CIFRA, texto))
        consulta = [termino for termino in terminos(texto) if not termino[0].isdigit()]
        if not consulta:
            return self._ayuda(pregunta)

        candidatos = self._indice.buscar(consulta, len(self._eventos))
        respuesta["recuperacion"] = {
            "metodo": "búsqueda por palabras (BM25 con sinónimos) sobre los eventos del corpus",
            "terminos": consulta,
            "umbral_cobertura": COBERTURA_SUFICIENTE,
            "candidatos": [{"id_evento": c.id, "titulo": self._eventos[c.id]["titulo_representativo"],
                            "cobertura": c.cobertura, "puntaje": c.puntaje, "encontrados": c.encontrados,
                            "faltantes": c.faltantes} for c in candidatos[:5]],
        }
        # Entre los casos que responden igual de bien va primero el de mayor prioridad en la bandeja
        cobertura = {c.id: c.cobertura for c in candidatos}
        suficientes = sorted((self._eventos[c.id] for c in candidatos if c.cobertura >= COBERTURA_SUFICIENTE),
                             key=lambda evento: (-cobertura[evento["id_evento"]], evento["prioridad"]["posicion"]))
        parciales = [self._eventos[c.id] for c in candidatos if COBERTURA_MINIMA <= c.cobertura < COBERTURA_SUFICIENTE]

        if not suficientes and self._semantico is not None:
            # Núcleo de IA (equipo B): antes de abstenerse, buscar por significado
            rescate = self._rescate_semantico(pregunta, respuesta)
            if rescate is not None:
                return rescate
        if not suficientes:
            respuesta["relacionados"] = [self.tarjeta(evento) for evento in parciales[:MAXIMO_EVENTOS]]
            return self._abstenerse(
                respuesta, "No hay evidencia en el corpus para responder",
                "Ningún titular ni dato oficial del snapshot contiene lo que se pregunta. No se completa con "
                "conocimiento externo ni se inventa una respuesta.",
                ["Una fuente primaria o un dato oficial sobre el tema, con fecha y procedencia.",
                 "Si el hecho es reciente, puede no estar en el snapshot: su fecha de corte es fija."])

        elegidos = suficientes[:MAXIMO_EVENTOS]
        respuesta["casos"] = [self.tarjeta(evento) for evento in elegidos]
        respuesta["relacionados"] = [self.tarjeta(evento) for evento in suficientes[MAXIMO_EVENTOS:MAXIMO_EVENTOS + 3]]
        if len(suficientes) > len(elegidos):
            respuesta["calculos"].append({"descripcion": "Casos del corpus que coinciden con la consulta",
                                          "valor": f"{len(suficientes)} (se detallan {len(elegidos)})"})
        responden = sum(self._agregar_evento(respuesta, evento, pide_cifra) for evento in elegidos)

        if pide_cifra and not responden:
            respuesta["relacionados"] = respuesta["casos"] + respuesta["relacionados"]
            respuesta["casos"], respuesta["calculos"] = [], []
            return self._abstenerse(
                respuesta, "El corpus no contiene esa cifra",
                "Hay titulares sobre el tema, pero ninguno trae un número que responda la pregunta. "
                "No se deduce ni se inventa una cifra.",
                ["La nota completa o la fuente primaria que publique la cifra, con su período."])

        if respuesta["versiones"]:
            respuesta["titulo"] = "Las fuentes reportan cifras distintas"
            respuesta["resumen"] = ("Se muestran todas las versiones con su fuente. Falta verificar cuál corresponde "
                                    "y a qué período; el sistema no elige una.")
            respuesta["avisos"].append(AVISO_VERSIONES)
        elif pide_cifra:
            respuesta["titulo"] = "Cifra reportada en titulares del corpus"
            respuesta["resumen"] = ("Es lo que publica un medio en su titular, no una cifra verificada. "
                                    "Confirme el período y la fuente primaria antes de usarla.")
        else:
            respuesta["titulo"] = f"{_cuantos(len(elegidos), 'caso', 'casos')} del corpus sobre lo consultado"
            respuesta["resumen"] = ("Cada afirmación indica de dónde sale. Lo que publica un medio es una "
                                    "declaración, no un hecho probado.")

        if any(evento.get("aviso_alcance") for evento in elegidos):
            respuesta["avisos"].append(AVISO_SOLO_TITULAR)
        for evento in elegidos:
            vieja = next((n for n in evento["noticias"] if n.get("antiguedad")), None)
            if vieja:
                respuesta["avisos"].append(
                    f"{evento['id_evento']}: contenido antiguo (fecha original {(vieja.get('fecha') or '?')[:10]}). "
                    "No debe presentarse como un hecho nuevo.")
            if self._evidencia[evento["id_evento"]][1]:
                respuesta["avisos"].append(
                    f"{evento['id_evento']}: un titular intenta dar instrucciones al sistema. Se trató como "
                    "contenido no confiable y no se usó para responder.")
        if not respuesta["afirmaciones"]:
            self._abstenerse(respuesta, "No hay evidencia utilizable para responder",
                             "Lo único que coincide es contenido marcado como no confiable.")
        elif self._semantico is not None:
            # Núcleo de IA (equipo B): resumen redactado y validado, en lugar del texto genérico
            redaccion = self._redaccion_llm(pregunta, elegidos)
            if redaccion is not None:
                respuesta["resumen"] = redaccion["texto"]
                respuesta["resumen_redactado_por"] = redaccion["modelo"]
        return respuesta
