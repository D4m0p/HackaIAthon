// Etapas 5, 6 y 7 · Explicar, Producir y Revisar: la ficha de un caso.

import { h, vaciar, icono, numero, puntos, plural, tiempo, fechaHora, enUtc, tostada, copiar, TIPO_FECHA, NOTA_TIPO_FECHA } from "../dom.js";
import { api } from "../api.js";
import {
  sesion, nivel, evidencia, estadoRevision, aviso, tonoDeAviso, nombreTema, textoConCitas, chipCita,
  listaAfirmaciones, leyendaTipos, abrirEvidencia, graficoSerie, versiones,
} from "../piezas.js";

const PAISES = { PAN: "Panamá", CRI: "Costa Rica", COL: "Colombia", DOM: "República Dominicana", MEX: "México", GTM: "Guatemala" };
const PIEZAS = [
  ["titulo_propuesto", "Título propuesto", null],
  ["enfoque_interes_publico", "Enfoque de interés público", null],
  ["brief", "Brief", "brief"],
  ["guion_45_60s", "Guion de 45 a 60 segundos", "guion_45_60s"],
  ["copy_digital", "Copy digital", "copy_digital"],
];
const ETIQUETA_ACCION = {
  "en revisión": ["Tomar para revisión", "ojo"],
  "requiere evidencia": ["Pedir más evidencia", "lupa_doc"],
  "aprobado como borrador": ["Aprobar como borrador", "listo"],
  "descartado": ["Descartar", "prohibido"],
};
const METODO = {
  llm: "Redactada por el modelo y validada contra la evidencia",
  plantilla: "Armada por plantilla, sin modelo: solo repite lo que dicen las fuentes",
  sin_evidencia_utilizable: "Sin evidencia utilizable",
};

const contarPalabras = (texto) => String(texto || "").replace(/\[[^\[\]]+?\]/g, " ").split(/\s+/).filter((t) => /[\p{L}\p{N}]/u.test(t)).length;

function revisorActual() {
  const campo = document.getElementById("revisor");
  const nombre = campo.value.trim();
  if (nombre.length < 3) {
    campo.closest(".revisor").dataset.falta = "si";
    campo.focus();
    tostada("Escriba su nombre arriba: cada decisión la firma una persona responsable.", "error");
    return null;
  }
  return nombre;
}

// ---------- secciones de la ficha ----------
function seccion(titulo, ...contenido) {
  return h("section", { class: "seccion" }, h("h2", null, titulo), contenido);
}

function nota(noticia) {
  const etiqueta = TIPO_FECHA[noticia.tipo_fecha] || "Fecha";
  return h("div", { class: "nota" },
    noticia.no_confiable
      ? h("span", { class: "titular titular--no-confiable nota__titulo" }, noticia.titulo)
      : h("span", { class: "titular nota__titulo" }, `«${noticia.titulo}»`),
    h("a", { class: "boton boton--fantasma boton--chico", href: noticia.url, target: "_blank", rel: "noopener noreferrer",
      title: "Abrir la nota en el sitio del medio (necesita internet)" }, "Fuente", icono("externo", "icono--chico")),
    h("div", { class: "nota__meta" },
      h("b", null, noticia.medio), h("span", { class: "mono tenue" }, noticia.id_noticia),
      noticia.fecha ? h("span", { title: NOTA_TIPO_FECHA[noticia.tipo_fecha] || "" }, `${etiqueta} `, tiempo(noticia.fecha)) : h("span", null, "Sin fecha conocida"),
      noticia.tipo_fecha === "deteccion" ? h("span", { class: "chip chip--contorno", title: NOTA_TIPO_FECHA.deteccion }, "No es fecha de publicación") : null,
      noticia.antiguedad === "recirculada" ? h("span", { class: "chip chip--alerta" }, "Recirculada: no es un hecho nuevo") : null,
      noticia.antiguedad === "antigua_en_feed" ? h("span", { class: "chip chip--alerta" }, "Nota antigua que sigue en el feed") : null,
      noticia.no_confiable ? h("span", { class: "chip chip--critico" }, "Contenido no confiable") : null,
      h("span", { class: "chip chip--contorno", title: noticia.motivo_tema || "" }, `Solo titular y metadatos`)));
}

function quienLoReporta(v) {
  const porId = Object.fromEntries(v.noticias.map((n) => [n.id_noticia, n]));
  return [
    h("div", { class: "procedencias" }, v.procedencias.map((ids, i) => h("div", { class: "procedencia" },
      h("div", { class: "procedencia__cabeza" }, `Procedencia ${i + 1}`,
        ids.length > 1 ? h("span", { class: "chip chip--alerta" }, `Mismo titular en ${ids.length} medios: cuenta como una`) : null),
      ids.map((id) => nota(porId[id]))))),
    h("p", { class: "suma-procedencias" }, h("b", null, plural(v.fuentes_independientes, "fuente independiente", "fuentes independientes")),
      ` de ${plural(v.n_noticias, "nota", "notas")}. Repetir un titular no lo corrobora ni sube la prioridad.`),
  ];
}

function tarjetaContexto(c, v, alAbrir) {
  const cita = chipCita(c.id_evidencia, null, v.evidencia, alAbrir);
  if (c.tipo === "indicador_banco_mundial") {
    const serie = (c.serie || []).map((p) => ({ anio: p.anio, valor: typeof p.valor === "number" ? p.valor : null }));
    return h("article", { class: "contexto" },
      h("div", { class: "contexto__cabeza" },
        h("span", { class: "contexto__nombre" }, `${c.nombre} · ${PAISES[c.pais] || c.pais}`),
        h("span", { class: "chip chip--alerta" }, `Dato anual ${c.anio}: no es de hoy`)),
      h("div", { class: "contexto__dato" }, h("b", null, numero(c.valor)), h("span", { class: "secundario" }, `${c.unidad} · ${c.anio}`)),
      graficoSerie(serie, c.unidad, [c.anio]),
      c.comparacion?.length ? h("div", { class: "comparacion" }, h("span", { class: "tenue" }, `Mismo año en otros países:`),
        c.comparacion.map((p) => h("span", { class: "chip" }, `${PAISES[p.pais] || p.pais} ${numero(p.valor)}`))) : null,
      h("div", { class: "contexto__pie" }, h("span", null, "Banco Mundial · ", c.licencia), h("span", null, `Vínculo: ${c.motivo_vinculo}`), cita,
        h("a", { href: c.fuente_url, target: "_blank", rel: "noopener noreferrer" }, "Fuente")));
  }
  return h("article", { class: "contexto" },
    h("div", { class: "contexto__cabeza" }, h("span", { class: "contexto__nombre" }, "Registro sísmico · USGS"),
      h("span", { class: "chip" }, c.estado === "reviewed" ? "Revisado por USGS" : (c.estado || "sin estado"))),
    h("div", { class: "contexto__dato" }, h("b", null, `M ${c.magnitud}`), h("span", { class: "secundario" }, c.lugar)),
    h("p", { class: "secundario" }, `${fechaHora(c.fecha_utc)} (hora de Panamá) · ${enUtc(c.fecha_utc)}`,
      c.profundidad_km != null ? ` · profundidad ${c.profundidad_km} km` : ""),
    h("div", { class: "contexto__pie" }, h("span", null, "Solo respalda hechos sísmicos, no daños ni pérdidas"),
      h("span", null, `Vínculo: ${c.motivo_vinculo}`), cita,
      h("a", { href: c.fuente_url, target: "_blank", rel: "noopener noreferrer" }, "Fuente")));
}

// ---------- borrador ----------
function conteo(campo, texto) {
  const limites = sesion.meta.reglas.limites;
  const n = contarPalabras(texto);
  let maximo = limites[campo], fuera = false, rotulo;
  if (Array.isArray(maximo)) {
    fuera = n < maximo[0] || n > maximo[1];
    rotulo = `${n} palabras · entre ${maximo[0]} y ${maximo[1]}`;
    maximo = maximo[1];
  } else {
    fuera = n > maximo;
    rotulo = `${n} de ${maximo} palabras`;
  }
  return h("span", { class: "conteo-palabras", dataset: { fuera: fuera ? "si" : "no" } },
    h("i", { estilo: { "--avance": `${Math.min(100, Math.round((n / maximo) * 100))}%` } }), rotulo);
}

function borradorLectura(v, alAbrir, alEditar) {
  const r = v.revision;
  const b = r.borrador;
  return h("div", { class: "borrador" },
    r.borrador_corregido ? aviso(`Texto corregido por la persona revisora en: ${r.campos_corregidos.map((c) => PIEZAS.find((p) => p[0] === c)[1].toLowerCase()).join(", ")}.`, "acento", "lapiz") : null,
    PIEZAS.map(([campo, nombre, limite]) => h("div", null,
      h("div", { class: "pieza__cabeza" }, h("span", { class: "pieza__nombre" }, nombre), limite ? conteo(limite, b[campo]) : null),
      h("div", { class: `pieza__texto ${campo === "titulo_propuesto" ? "pieza__texto--titulo" : ""}`.trim() }, textoConCitas(b[campo], v.evidencia, alAbrir)))),
    b.verificaciones_pendientes?.length ? h("div", null,
      h("div", { class: "pieza__cabeza" }, h("span", { class: "pieza__nombre" }, "Verificaciones pendientes antes de usarlo")),
      h("ul", { class: "lista-simple" }, b.verificaciones_pendientes.map((p) => h("li", null, textoConCitas(p, v.evidencia, alAbrir))))) : null,
    h("div", { class: "borrador__acciones" },
      h("button", { class: "boton boton--chico", type: "button", onclick: alEditar }, icono("lapiz", "icono--chico"), "Corregir el borrador"),
      h("span", { class: "tenue" }, "Las citas [ID:campo] deben conservarse: el validador las comprueba al guardar.")));
}

function borradorEdicion(v, alGuardar, alCancelar) {
  const b = v.revision.borrador;
  const campos = {};
  const notaCorreccion = h("input", { class: "campo", type: "text", maxlength: "300", placeholder: "Qué se corrigió y por qué (opcional)" });
  return h("form", { class: "borrador", onsubmit: (e) => {
    e.preventDefault();
    const cambios = Object.fromEntries(Object.entries(campos).map(([campo, area]) => [campo, area.value]));
    alGuardar(cambios, notaCorreccion.value);
  } },
    aviso("Corrija el texto conservando una cita [ID:campo] junto a cada cifra o fecha. Al guardar se vuelve a validar contra la evidencia.", "acento", "lapiz"),
    PIEZAS.map(([campo, nombre, limite]) => {
      const zonaConteo = h("span", null, limite ? conteo(limite, b[campo]) : null);
      const area = h("textarea", { class: "campo", rows: campo === "brief" || campo === "guion_45_60s" ? 7 : 3,
        oninput: () => { if (limite) vaciar(zonaConteo, conteo(limite, area.value)); } });
      area.value = b[campo] || "";
      campos[campo] = area;
      return h("label", null, h("div", { class: "pieza__cabeza" }, h("span", { class: "pieza__nombre" }, nombre), zonaConteo), area);
    }),
    h("label", null, h("span", { class: "rotulo" }, "Nota de la corrección"), notaCorreccion),
    h("div", { class: "borrador__acciones" },
      h("button", { class: "boton boton--primario", type: "submit" }, icono("listo", "icono--chico"), "Guardar corrección"),
      h("button", { class: "boton boton--fantasma", type: "button", onclick: alCancelar }, "Cancelar")));
}

function validacion(v) {
  const propia = v.revision.validacion;
  const delNucleo = v.ficha?.validacion;
  const descartadas = delNucleo?.afirmaciones_descartadas || [];
  if (!propia.motivos_bloqueo.length && !propia.advertencias.length && !descartadas.length) {
    return aviso("Sin observaciones: cada cifra y cada cita del borrador están en la evidencia.", "bien", "escudo");
  }
  return h("div", { class: "avisos" },
    propia.motivos_bloqueo.map((m) => aviso(`Bloqueo · ${m}`, "critico", "prohibido")),
    propia.advertencias.map((a) => aviso(a, "alerta", "alerta")),
    descartadas.map((d) => aviso(`Afirmación descartada por el validador (${d.motivo_descarte}): «${d.texto}»`, "critico", "prohibido")));
}

// ---------- columna lateral ----------
function tarjetaPuntaje(v) {
  const p = v.prioridad;
  const meta = sesion.meta.reglas.componentes;
  const pesoMaximo = Math.max(...Object.values(p.componentes).map((c) => c.peso));
  return h("section", { class: "tarjeta" }, h("div", { class: "tarjeta__cuerpo" },
    h("h2", null, "Puntaje de atención"),
    h("div", { class: "puntaje__cifra" }, h("b", null, puntos(p.puntaje)), h("span", null, "de 100"), nivel(p.nivel)),
    h("div", { class: "formula" }, `${p.formula} · ${p.version_reglas}`),
    p.ajuste ? h("div", { estilo: { "margin-top": ".7rem" } }, aviso(`${p.ajuste}.`, "alerta", "ciclo")) : null,
    h("div", { class: "componentes" }, Object.entries(p.componentes).map(([clave, c]) => h("div", { class: "componente" },
      h("div", { class: "componente__cabeza" }, h("b", null, `${clave} · ${meta[clave].nombre}`),
        h("span", { title: `valor ${c.valor} × peso ${c.peso}` }, `${c.aporte} de ${c.peso}`)),
      h("div", { class: "componente__pista", estilo: { width: `${(c.peso / pesoMaximo) * 100}%` },
        title: `${meta[clave].mide} Valor ${c.valor} (de 0 a 1) × peso ${c.peso} = ${c.aporte}` },
      h("i", { estilo: { width: `${Math.round(c.valor * 100)}%` } })),
      h("p", null, c.explicacion)))),
    h("div", { class: "no-publica" }, icono("balanza", "icono--chico"),
      h("span", null, "Ordena la revisión. No es una probabilidad de verdad ni habilita publicar."))));
}

function tarjetaEvidencia(v) {
  return h("section", { class: "tarjeta" }, h("div", { class: "tarjeta__cuerpo" },
    h("h2", null, "Estado de evidencia", h("span", { class: "conteo" }, "· independiente del puntaje")),
    evidencia(v.estado_evidencia, true),
    h("p", { class: "secundario", estilo: { "margin-top": ".35rem" } }, `${v.motivo_estado_evidencia.charAt(0).toUpperCase()}${v.motivo_estado_evidencia.slice(1)}.`),
    h("div", { class: "datos-evidencia" },
      h("div", null, h("b", null, v.fuentes_independientes), h("span", null, v.fuentes_independientes === 1 ? "fuente independiente" : "fuentes independientes")),
      h("div", null, h("b", null, v.contexto.length), h("span", null, v.contexto.length === 1 ? "dato oficial vinculado" : "datos oficiales vinculados"))),
    v.estado_evidencia === "insuficiente" && v.prioridad.nivel === "alto"
      ? h("div", { estilo: { "margin-top": ".7rem" } }, aviso("Prioridad alta con evidencia insuficiente: requiere investigación, no producción.", "serio", "lupa_doc")) : null));
}

function tarjetaRevision(v, alActuar) {
  const r = v.revision;
  const campoNota = h("textarea", { class: "campo", rows: 2, maxlength: "600", placeholder: "Nota: qué se verificó, por qué se descarta o se reabre…" });
  return h("section", { class: "tarjeta" }, h("div", { class: "tarjeta__cuerpo" },
    h("h2", null, "Revisión humana"),
    h("div", { estilo: { display: "flex", "align-items": "center", gap: ".6rem", "flex-wrap": "wrap" } },
      estadoRevision(r.estado),
      r.revisor ? h("span", { class: "secundario", estilo: { "font-size": ".86rem" } }, `${r.revisor} · `, tiempo(r.fecha_utc)) : h("span", { class: "tenue", estilo: { "font-size": ".86rem" } }, "asignado por el sistema")),
    r.desactualizada ? h("div", { estilo: { "margin-top": ".7rem" } }, aviso("La ficha cambió después de la última decisión. Hay que revisarla de nuevo.", "serio", "ciclo")) : null,
    r.aviso_aprobacion ? h("div", { estilo: { "margin-top": ".7rem" } }, aviso(r.aviso_aprobacion, "bien", "listo")) : null,
    h("label", { estilo: { display: "block", "margin-top": ".9rem" } }, h("span", { class: "rotulo" }, "Nota de la persona revisora"), campoNota),
    h("div", { class: "acciones" }, r.acciones.map((a) => {
      const [nombre, nombreIcono] = a.accion === "reabrir" ? ["Reabrir el caso", "ciclo"] : ETIQUETA_ACCION[a.estado];
      const principal = a.estado === "aprobado como borrador";
      return h("div", { class: "accion" },
        h("button", { class: `boton ${principal && a.permitido ? "boton--primario" : ""} ${a.estado === "descartado" ? "boton--peligro" : ""}`.trim(),
          type: "button", disabled: !a.permitido, onclick: () => alActuar(a, campoNota) }, icono(nombreIcono, "icono--chico"), nombre),
        !a.permitido ? h("small", null, a.impedimento)
          : (a.nota_obligatoria ? h("small", { class: "tenue" }, `Pide nota. ${a.nota_obligatoria}`) : null));
    })),
    h("div", { class: "no-publica" }, icono("prohibido", "icono--chico"),
      h("span", null, "Aprobar un borrador no lo publica. No existe un estado para publicar.")),
    r.historial.length ? [
      h("h2", { estilo: { "margin-top": "1.2rem" } }, "Bitácora del caso"),
      h("ol", { class: "historial" }, [...r.historial].reverse().map((reg) => h("li", null,
        h("time", { datetime: reg.fecha_utc }, `${fechaHora(reg.fecha_utc)} · hora de Panamá`),
        h("b", null, reg.revisor), ` · ${reg.accion}`,
        reg.estado_nuevo ? h("div", { class: "secundario" }, `${reg.estado_anterior} → ${reg.estado_nuevo}`) : null,
        reg.cambios ? h("div", { class: "secundario" }, `Corrigió: ${Object.keys(reg.cambios).map((c) => PIEZAS.find((p) => p[0] === c)?.[1] || c).join(", ")}`) : null,
        reg.notion_url ? h("a", { href: reg.notion_url, target: "_blank", rel: "noopener noreferrer" }, "Abrir en Notion") : null,
        reg.nota ? h("q", null, reg.nota) : null))),
    ] : null));
}

// ---------- la vista ----------
export async function ficha(raiz, id) {
  let v = await api.caso(id);
  let editando = false;
  const alAbrir = (idEvidencia, campo) => abrirEvidencia(idEvidencia, campo, v.evidencia);

  async function conAviso(tarea, exito) {
    try {
      const resultado = await tarea();
      if (exito) tostada(exito);
      return resultado;
    } catch (error) {
      tostada(error.message, "error");
      return null;
    }
  }

  async function actuar(accion, campoNota) {
    const revisor = revisorActual();
    if (!revisor) return;
    if (accion.nota_obligatoria && campoNota.value.trim().length < 10) {
      campoNota.focus();
      tostada(`Falta la nota. ${accion.nota_obligatoria}`, "error");
      return;
    }
    const nueva = await conAviso(() => api.revisar(id, accion.estado, revisor, campoNota.value), `Registrado: ${accion.estado}.`);
    if (nueva) { v = nueva; pintar(); }
  }

  async function guardarCorreccion(cambios, notaCorreccion) {
    const revisor = revisorActual();
    if (!revisor) return;
    const nueva = await conAviso(() => api.corregir(id, cambios, revisor, notaCorreccion), "Corrección guardada y validada.");
    if (nueva) { v = nueva; editando = false; pintar(); }
  }

  async function copiarParaNotion() {
    const markdown = await conAviso(() => api.markdown(id));
    if (!markdown) return;
    if (await copiar(markdown)) tostada("Ficha copiada. Péguela en la página «Casos y evidencias» de Notion.");
    else mostrarMarkdown(markdown);
  }

  function mostrarMarkdown(markdown) {
    const dialogo = document.getElementById("dialogo");
    const area = h("textarea", { class: "campo mono", rows: 18, readonly: true });
    area.value = markdown;
    vaciar(dialogo,
      h("div", { class: "dialogo__cabeza" }, h("div", null, h("div", { class: "sobretitulo" }, "Para pegar en Notion"), h("h2", null, v.id_caso)),
        h("button", { class: "icono-boton", type: "button", "aria-label": "Cerrar", onclick: () => dialogo.close() }, icono("cerrar"))),
      h("div", { class: "dialogo__cuerpo" }, area),
      h("div", { class: "dialogo__pie" }, h("button", { class: "boton boton--primario", type: "button",
        onclick: async () => { area.select(); if (await copiar(markdown)) tostada("Copiado."); } }, icono("copiar", "icono--chico"), "Copiar todo")));
    dialogo.showModal();
  }

  async function enviarANotion() {
    const revisor = revisorActual();
    if (!revisor) return;
    const resultado = await conAviso(() => api.notion(id, revisor));
    if (resultado) { v = resultado.caso; tostada(`Página ${resultado.notion.accion} en Notion.`); pintar(); }
  }

  async function generar() {
    const nueva = await conAviso(() => api.generarFicha(id), "Ficha generada por el núcleo.");
    if (nueva) { v = nueva; pintar(); }
  }

  function pintar() {
    const contenido = v.ficha || v.vista_previa || {};
    const afirmaciones = contenido.afirmaciones || [];
    const ultima = v.noticias.filter((n) => n.fecha).sort((a, b) => a.fecha.localeCompare(b.fecha)).pop();
    const capacidades = sesion.meta.capacidades;

    vaciar(raiz,
      h("div", { class: "migas" },
        h("a", { class: "boton boton--fantasma boton--chico", href: "#/bandeja" }, icono("atras", "icono--chico"), "Bandeja"),
        h("span", { class: "tenue" }, `Caso ${v.prioridad.posicion} de ${v.navegacion.total}`),
        v.navegacion.anterior ? h("a", { class: "icono-boton", href: `#/caso/${encodeURIComponent(v.navegacion.anterior)}`, title: "Caso anterior" }, icono("arriba")) : null,
        v.navegacion.siguiente ? h("a", { class: "icono-boton", href: `#/caso/${encodeURIComponent(v.navegacion.siguiente)}`, title: "Caso siguiente" }, icono("abajo")) : null,
        h("span", { class: "migas__espacio" }),
        h("button", { class: "boton boton--chico", type: "button", onclick: async () => { const m = await conAviso(() => api.markdown(id)); if (m) mostrarMarkdown(m); } },
          icono("documento", "icono--chico"), "Ver como documento"),
        h("button", { class: "boton boton--chico", type: "button", onclick: copiarParaNotion }, icono("copiar", "icono--chico"), "Copiar para Notion"),
        capacidades.notion
          ? h("button", { class: "boton boton--chico boton--acento", type: "button", onclick: enviarANotion }, icono("enviar", "icono--chico"), "Enviar a Notion")
          : null),

      h("header", { class: "ficha__cabeza" },
        h("div", { class: "ficha__etiquetas" },
          h("span", { class: "chip" }, nombreTema(v.tema)),
          v.tema_por_respaldo ? h("span", { class: "chip chip--alerta", title: "El tema lo asignó el clasificador de respaldo, sin el modelo" }, "Tema por confirmar") : null,
          h("span", { class: "mono tenue" }, v.id_caso),
          h("span", { class: "chip chip--contorno" }, "Editorial · TVN Media")),
        h("h1", { class: `titular ficha__titulo ${v.titulo_no_confiable ? "titular--no-confiable" : ""}`.trim() }, v.titulo),
        h("p", { class: "ficha__meta" },
          `${plural(v.n_noticias, "nota", "notas")} · ${plural(v.fuentes_independientes, "procedencia independiente", "procedencias independientes")}`,
          ultima ? [` · más reciente: ${(TIPO_FECHA[ultima.tipo_fecha] || "fecha").toLowerCase()} `, tiempo(ultima.fecha), " (hora de Panamá)"] : null),
        h("div", { class: "avisos ficha__avisos" }, v.avisos.map((texto) => { const [tono, nombreIcono] = tonoDeAviso(texto); return aviso(texto, tono, nombreIcono); }))),

      h("div", { class: "ficha" },
        h("div", { estilo: { display: "grid", gap: "1.25rem" } },
          h("article", { class: "tarjeta" },
            contenido.que_se_reporta ? seccion("Qué se reporta", h("p", { class: "texto-sistema" }, contenido.que_se_reporta)) : null,
            seccion(["Quién lo reporta"], quienLoReporta(v)),
            seccion(["Qué está respaldado", h("span", { class: "conteo" }, `· ${plural(afirmaciones.length, "afirmación con cita", "afirmaciones con cita")}`)],
              afirmaciones.length ? [listaAfirmaciones(afirmaciones, v.evidencia, alAbrir), leyendaTipos()]
                : h("p", { class: "secundario" }, "Ninguna afirmación tiene respaldo utilizable en el corpus.")),
            v.contradicciones.length ? seccion("Cifras en conflicto", versiones(v.contradicciones),
              h("div", { estilo: { "margin-top": ".7rem" } }, aviso("Se muestran todas las versiones con su fuente. Falta verificar cuál corresponde y a qué período: el sistema no elige una.", "alerta", "alerta"))) : null,
            seccion("Contexto oficial", v.contexto.length
              ? h("div", { class: "contextos" }, v.contexto.map((c) => tarjetaContexto(c, v, alAbrir)))
              : h("p", { class: "secundario" }, v.sin_contexto_motivo || "Sin datos oficiales vinculados.")),
            contenido.que_falta_verificar?.length ? seccion("Qué falta verificar",
              h("ul", { class: "lista-simple" }, contenido.que_falta_verificar.map((p) => h("li", null, textoConCitas(p, v.evidencia, alAbrir))))) : null,
            contenido.accion_recomendada ? seccion("Acción recomendada", aviso(contenido.accion_recomendada, "acento", "flecha")) : null,
            contenido.preguntas_investigacion?.length ? seccion("Preguntas de investigación",
              h("ol", { class: "lista-numerada" }, contenido.preguntas_investigacion.map((p) => h("li", null, p)))) : null,
            v.no_confiable.length ? seccion("Contenido no confiable", v.no_confiable.map((n) => h("div", { class: "sospechoso" },
              h("b", null, `${n.medio} · `, h("span", { class: "mono" }, n.id_noticia)),
              h("code", null, n.titulo),
              h("span", { class: "secundario" }, "El titular intenta dar instrucciones al sistema. Se trató como dato no confiable: no se envió al modelo, no se usó para redactar y no cambió el puntaje.")))) : null),

          h("article", { class: "tarjeta" },
            seccion(["Borrador · paquete editorial", v.ficha ? h("span", { class: "conteo" }, `· ${METODO[v.ficha.generado.metodo] || v.ficha.generado.metodo}${v.ficha.generado.modelo ? ` (${v.ficha.generado.modelo})` : ""}`) : null],
              v.revision.borrador
                ? (editando ? borradorEdicion(v, guardarCorreccion, () => { editando = false; pintar(); }) : borradorLectura(v, alAbrir, () => { editando = true; pintar(); }))
                : h("div", { class: "vacio" }, h("strong", null, "Sin borrador"),
                  v.ficha ? "La evidencia no alcanza para redactar. El caso requiere investigación antes de producir."
                    : "Este caso no tiene ficha del núcleo todavía.",
                  v.puede_generar_ficha ? h("div", { estilo: { "margin-top": ".9rem" } },
                    h("button", { class: "boton", type: "button", onclick: generar }, icono("rayo", "icono--chico"), "Generar ficha con el núcleo")) : null)),
            v.revision.borrador ? seccion("Validación automática", validacion(v)) : null)),

        h("aside", { class: "ficha__lateral" }, tarjetaPuntaje(v), tarjetaEvidencia(v), tarjetaRevision(v, actuar))));
  }

  pintar();
}
