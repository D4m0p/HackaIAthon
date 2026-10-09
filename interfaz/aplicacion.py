"""Lo que la pantalla necesita, armado a partir del corpus y de la bitácora de revisión."""

from __future__ import annotations

import json
import statistics
import threading

from . import exportar, fuentes, notion, puente, revision, rutas
from .consulta import COMPONENTES, Motor
from .fuentes import Corpus, hora_panama
from .puente import config
from .texto import NOMBRE_TEMA

from ingesta import cargar_paquete  # noqa: E402
from ingesta.comun import a_iso_utc, ahora_utc  # noqa: E402
from nucleo.plantilla import redaccion_por_plantilla  # noqa: E402

AVISO_SIN_FICHA = ("El núcleo genera en lote solo las primeras fichas del ranking. Esta vista se arma "
                   "con la evidencia del evento y la plantilla, sin borrador.")


class CasoInexistente(KeyError):
    pass


class Aplicacion:
    def __init__(self, corpus: Corpus):
        self.corpus = corpus
        self.bitacora = revision.Bitacora(corpus.carpeta_estado)
        self._evidencia = {e["id_evento"]: fuentes.evidencia_de_evento(e) for e in corpus.eventos}
        self.motor = Motor(corpus, self._estado_de)
        self._ruta_consultas = corpus.carpeta_estado / "consultas.jsonl"
        self._candado = threading.Lock()

    # -- acceso ----------------------------------------------------------------
    def _evento(self, id_evento: str) -> dict:
        evento = self.corpus.evento(id_evento)
        if evento is None:
            raise CasoInexistente(id_evento)
        return evento

    def _ficha(self, id_evento: str) -> dict | None:
        return self.corpus.fichas.get(id_evento)

    def _estado_de(self, evento: dict) -> str:
        return self.bitacora.estado(evento["id_evento"], revision.estado_inicial(evento, self._ficha(evento["id_evento"])))

    # -- estado general --------------------------------------------------------
    def estado(self) -> dict:
        corpus = self.corpus
        return {
            "modo": corpus.modo,
            "avisos": corpus.avisos,
            "fecha_corte_utc": corpus.fecha_corte,
            "fecha_corte_panama": hora_panama(corpus.fecha_corte),
            "version_paquete": (corpus.manifest or {}).get("version"),
            "paquete_integro": not corpus.incidencias if corpus.manifest else None,
            "eventos": len(corpus.eventos),
            "fichas": len(corpus.fichas),
            "noticias": sum(e["n_noticias"] for e in corpus.eventos),
            "indicadores": len(corpus.indicadores),
            "sismos": len(corpus.sismos),
            "excluidas_idioma": len(corpus.excluidas_idioma),
            "modalidad": config.MODALIDAD,
            "reglas": {
                "version": config.VERSION_REGLAS,
                "formula": "P = " + " + ".join(f"{peso}{clave}" for clave, peso in config.PESOS.items()),
                "pesos": config.PESOS,
                "niveles": [{"nivel": nombre, "desde": minimo} for minimo, nombre in config.NIVELES],
                "componentes": {clave: {"nombre": nombre, "mide": mide} for clave, (nombre, mide) in COMPONENTES.items()},
                "limites": {"brief": config.LIMITE_PALABRAS_BRIEF, "copy_digital": config.LIMITE_PALABRAS_COPY,
                            "guion_45_60s": list(config.RANGO_PALABRAS_GUION)},
            },
            "estados_revision": list(revision.ESTADOS),
            "temas": NOMBRE_TEMA,
            "capacidades": {
                "generar_fichas": puente.nucleo_completo(),
                "llm": puente.llm_disponible(),
                "notion": notion.configuracion() is not None,
            },
        }


    # -- bandeja ---------------------------------------------------------------
    def bandeja(self) -> list[dict]:
        filas = []
        for evento in self.corpus.eventos:
            id_evento = evento["id_evento"]
            ficha = self._ficha(id_evento)
            prioridad = evento["prioridad"]
            evidencia, no_confiable = self._evidencia[id_evento]
            decisiones = [r for r in self.bitacora.registros(id_evento) if r.get("estado_nuevo")]
            reciente = max(evento["noticias"], key=lambda n: n.get("fecha") or "")
            filas.append({
                "id_evento": id_evento,
                "id_caso": f"CASO-{id_evento}",
                "posicion": prioridad["posicion"],
                "puntaje": prioridad["puntaje"],
                "nivel": prioridad["nivel"],
                "ajuste": bool(prioridad.get("ajuste")),
                "componentes": {clave: {"valor": c["valor"], "aporte": c["aporte"], "peso": c["peso"]}
                                for clave, c in prioridad["componentes"].items()},
                "titulo": evento["titulo_representativo"],
                "tema": evento["tema"],
                "n_noticias": evento["n_noticias"],
                "fuentes_independientes": evento["n_fuentes_independientes"],
                "medios": evento["medios"],
                "fecha": reciente.get("fecha"),
                "tipo_fecha": reciente.get("tipo_fecha"),
                "estado_evidencia": evento["estado_evidencia"],
                "motivo_estado_evidencia": evento["motivo_estado_evidencia"],
                "contradiccion": bool(evento["posibles_contradicciones"]),
                "dato_oficial": sorted({c["tipo"] for c in evento.get("contexto", [])}),
                "antigua": next((n["antiguedad"] for n in evento["noticias"] if n.get("antiguedad")), None),
                "no_confiable": bool(no_confiable),
                "sin_evidencia_utilizable": not evidencia,
                "tiene_ficha": ficha is not None,
                "tiene_borrador": bool(ficha and ficha.get("borrador")),
                "bloqueada": bool(ficha and ficha["validacion"]["bloqueada"]),
                "metodo": ficha["generado"]["metodo"] if ficha else None,
                "estado_revision": self._estado_de(evento),
                "revisor": decisiones[-1]["revisor"] if decisiones else None,
            })
        return filas

    # -- un caso ---------------------------------------------------------------
    def caso(self, id_evento: str) -> dict:
        evento = self._evento(id_evento)
        ficha = self._ficha(id_evento)
        evidencia, no_confiable = self._evidencia[id_evento]
        prioridad = evento["prioridad"]
        sospechosos = {n["id_noticia"] for n in no_confiable}
        procedencia_de = {id_noticia: indice for indice, grupo in enumerate(evento["procedencias"]) for id_noticia in grupo}

        noticias = [{
            **noticia,
            "fecha_panama": hora_panama(noticia.get("fecha")),
            "deteccion_panama": hora_panama(noticia.get("fecha_deteccion")),
            "no_confiable": noticia["id_noticia"] in sospechosos,
            "procedencia": procedencia_de.get(noticia["id_noticia"]),
        } for noticia in evento["noticias"]]

        vista_previa = None
        if ficha:
            avisos = ficha["avisos"]
        else:
            avisos = [prioridad["aviso"]]
            avisos += [evento["aviso_alcance"]] if evento.get("aviso_alcance") else []
            avisos += [c["advertencia"] for c in evento.get("contexto", [])]
            avisos += [prioridad["ajuste"]] if prioridad.get("ajuste") else []
            if no_confiable:
                avisos.append("Uno o más titulares contienen texto que intenta dar instrucciones al sistema; "
                              "se trataron como contenido no confiable.")
            avisos.append(AVISO_SIN_FICHA)
            if evidencia:
                vista_previa = redaccion_por_plantilla(evento, evidencia, False)

        posiciones = [e["id_evento"] for e in self.corpus.eventos]
        indice = posiciones.index(id_evento)
        return {
            "id_evento": id_evento,
            "id_caso": f"CASO-{id_evento}",
            "titulo": evento["titulo_representativo"],
            "titulo_no_confiable": bool(no_confiable) and not evidencia,
            "tema": evento["tema"],
            "tema_por_respaldo": evento.get("tema_por_respaldo", False),
            "modalidad": config.MODALIDAD,
            "prioridad": prioridad,
            "estado_evidencia": evento["estado_evidencia"],
            "motivo_estado_evidencia": evento["motivo_estado_evidencia"],
            "noticias": noticias,
            "procedencias": evento["procedencias"],
            "n_noticias": evento["n_noticias"],
            "fuentes_independientes": evento["n_fuentes_independientes"],
            "contexto": evento.get("contexto", []),
            "sin_contexto_motivo": evento.get("sin_contexto_motivo"),
            "contradicciones": self.motor.versiones(evento),
            "evidencia": evidencia,
            "no_confiable": no_confiable,
            "ficha": ficha,
            "vista_previa": vista_previa,
            "avisos": avisos,
            "revision": revision.resumen(self.bitacora, evento, ficha, evidencia),
            "puede_generar_ficha": ficha is None and bool(evidencia) and puente.nucleo_completo(),
            "navegacion": {
                "anterior": posiciones[indice - 1] if indice > 0 else None,
                "siguiente": posiciones[indice + 1] if indice + 1 < len(posiciones) else None,
                "total": len(posiciones),
            },
        }

    def cambiar_estado(self, id_evento: str, estado: str, revisor: str, nota: str | None) -> dict:
        evento = self._evento(id_evento)
        revision.cambiar_estado(self.bitacora, evento, self._ficha(id_evento), self._evidencia[id_evento][0],
                                estado, revisor, nota)
        return self.caso(id_evento)

    def corregir(self, id_evento: str, cambios: dict, revisor: str, nota: str | None) -> dict:
        evento = self._evento(id_evento)
        revision.corregir_borrador(self.bitacora, evento, self._ficha(id_evento), self._evidencia[id_evento][0],
                                   cambios, revisor, nota)
        return self.caso(id_evento)

    def generar_ficha(self, id_evento: str) -> dict:
        evento = self._evento(id_evento)
        if self._ficha(id_evento) is None:
            fuentes.guardar_ficha_a_pedido(self.corpus, puente.generar_ficha(evento))
        return self.caso(id_evento)

    # -- registro en Notion ---------------------------------------------------
    def markdown(self, id_evento: str) -> str:
        return exportar.a_markdown(exportar.documento(self.caso(id_evento)))

    def enviar_a_notion(self, id_evento: str, revisor: str) -> dict:
        evento = self._evento(id_evento)
        vista = self.caso(id_evento)
        previas = [r["notion_pagina"] for r in self.bitacora.registros(id_evento) if r.get("notion_pagina")]
        resultado = notion.sincronizar(exportar.propiedades(vista), exportar.documento(vista),
                                       previas[-1] if previas else None)
        revision.anotar(self.bitacora, evento, self._ficha(id_evento), "enviar a Notion", revisor,
                        {"nota": f"Página {resultado['accion']} en Notion", "notion_pagina": resultado["id"],
                         "notion_url": resultado["url"]})
        return {"notion": resultado, "caso": self.caso(id_evento)}

    # -- consulta --------------------------------------------------------------
    def consultar(self, pregunta: str) -> dict:
        respuesta = self.motor.responder(pregunta)
        registro = {
            "fecha_utc": a_iso_utc(ahora_utc()), "pregunta": respuesta["pregunta"], "tipo": respuesta["tipo"],
            "abstencion": respuesta["abstencion"], "afirmaciones": len(respuesta["afirmaciones"]),
            "descartadas": len(respuesta["descartadas"]), "tiempo_ms": respuesta["tiempo_ms"],
        }
        with self._candado:
            self._ruta_consultas.parent.mkdir(parents=True, exist_ok=True)
            with open(self._ruta_consultas, "a", encoding="utf-8") as archivo:
                archivo.write(json.dumps(registro, ensure_ascii=False) + "\n")
        return respuesta

    def _consultas(self) -> list[dict]:
        if not self._ruta_consultas.exists():
            return []
        return [json.loads(linea) for linea in self._ruta_consultas.read_text(encoding="utf-8").splitlines() if linea.strip()]

    # -- registro --------------------------------------------------------------
    def registro(self) -> dict:
        """Bitácora de revisión y métricas de uso, para la página de pruebas de Notion."""
        titulos = {e["id_evento"]: e["titulo_representativo"] for e in self.corpus.eventos}
        decisiones = [{**r, "titulo": titulos.get(r["id_evento"]), "fecha_panama": hora_panama(r["fecha_utc"])}
                      for r in reversed(self.bitacora.registros())]
        estados = [self._estado_de(evento) for evento in self.corpus.eventos]
        consultas = self._consultas()
        tiempos = sorted(c["tiempo_ms"] for c in consultas)
        return {
            "decisiones": decisiones,
            "por_estado": {estado: estados.count(estado) for estado in revision.ESTADOS},
            "consultas": {
                "total": len(consultas),
                "abstenciones": sum(1 for c in consultas if c["abstencion"]),
                "afirmaciones": sum(c["afirmaciones"] for c in consultas),
                "descartadas": sum(c["descartadas"] for c in consultas),
                "mediana_ms": round(statistics.median(tiempos), 1) if tiempos else None,
                "p95_ms": tiempos[min(len(tiempos) - 1, int(len(tiempos) * 0.95))] if tiempos else None,
                "recientes": list(reversed(consultas[-12:])),
            },
        }

    def fichas_revisadas(self) -> list[dict]:
        salida = []
        for evento in self.corpus.eventos:
            ficha = self._ficha(evento["id_evento"])
            if ficha:
                salida.append(revision.ficha_revisada(self.bitacora, evento, ficha, self._evidencia[evento["id_evento"]][0]))
        return salida

    def reiniciar_ejemplo(self) -> None:
        """Borra las decisiones de prueba. Solo existe para los datos de ejemplo."""
        if self.corpus.modo != "ejemplo":
            raise PermissionError("Solo se puede reiniciar el registro de los datos de ejemplo.")
        self.bitacora.vaciar()
        if self._ruta_consultas.exists():
            self._ruta_consultas.unlink()

    # -- etapa 1: el paquete de datos -----------------------------------------
    def datos(self) -> dict:
        """Verificación en vivo del paquete congelado (equipo A): integridad, calidad y condiciones de uso."""
        if not (rutas.DATOS_REAL / "manifest.json").exists():
            return {"disponible": False}
        paquete = cargar_paquete(rutas.DATOS_REAL)
        manifest = paquete.manifest or {}
        ruta_fuentes = rutas.DATOS_REAL / "fuentes.json"
        # Cuántas URL repetidas se fusionaron solo se sabe al extraer: lo dejó escrito el equipo A.
        ruta_calidad = rutas.DATOS_REAL / "reporte_calidad.json"
        al_extraer = json.loads(ruta_calidad.read_text(encoding="utf-8")) if ruta_calidad.exists() else {}
        return {
            "disponible": True,
            "alimenta_la_bandeja": self.corpus.modo == "real",
            "version": manifest.get("version"),
            "fecha_corte_utc": paquete.fecha_corte,
            "fecha_corte_panama": hora_panama(paquete.fecha_corte),
            "integro": paquete.integro,
            "incidencias": paquete.incidencias,
            "archivos": [{"archivo": nombre, **datos} for nombre, datos in manifest.get("archivos", {}).items()],
            "reporte": paquete.reporte,
            "duplicados_fusionados": al_extraer.get("noticias", {}).get("duplicados_por_url_fusionados"),
            "rechazados": {clave: len(valor) for clave, valor in paquete.rechazados.items()},
            "excluidos": manifest.get("registros_excluidos", {}),
            "transformaciones": manifest.get("transformaciones", []),
            "descargas_fallidas": [c for c in manifest.get("consultas", []) if c.get("estado") != "ok"],
            "fuentes": json.loads(ruta_fuentes.read_text(encoding="utf-8")) if ruta_fuentes.exists() else [],
            "excluidas_idioma": len(self.corpus.excluidas_idioma) if self.corpus.modo == "real" else None,
        }
