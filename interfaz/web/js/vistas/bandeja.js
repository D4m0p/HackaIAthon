// Etapa 4 · Priorizar: la lista ordenada, con el porqué de cada posición a la vista.

import { h, vaciar, icono, puntos, plural, soloFecha, TIPO_FECHA } from "../dom.js";
import { api } from "../api.js";
import { sesion, nivel, evidencia, estadoRevision, glifo, letrasGlifo, aviso, nombreTema } from "../piezas.js";

const POR_TANDA = 40;
const filtros = { texto: "", tema: "", nivel: "", evidencia: "", revision: "", senal: "" };
let visibles = POR_TANDA;

const SENALES = {
  contradiccion: ["Cifras en conflicto", (f) => f.contradiccion],
  oficial: ["Con dato oficial", (f) => f.dato_oficial.length > 0],
  antigua: ["Contenido antiguo", (f) => Boolean(f.antigua)],
  no_confiable: ["Contenido no confiable", (f) => f.no_confiable],
  borrador: ["Con borrador", (f) => f.tiene_borrador],
  sin_ficha: ["Sin ficha generada", (f) => !f.tiene_ficha],
};
const GRUPOS_REVISION = {
  por_revisar: ["Por revisar", (f) => f.estado_revision === "nuevo" || f.estado_revision === "en revisión"],
  requiere: ["Piden evidencia", (f) => f.estado_revision === "requiere evidencia"],
  aprobado: ["Aprobados", (f) => f.estado_revision === "aprobado como borrador"],
  descartado: ["Descartados", (f) => f.estado_revision === "descartado"],
};

function cumple(fila) {
  if (filtros.tema && fila.tema !== filtros.tema) return false;
  if (filtros.nivel && fila.nivel !== filtros.nivel) return false;
  if (filtros.evidencia && fila.estado_evidencia !== filtros.evidencia) return false;
  if (filtros.revision && !GRUPOS_REVISION[filtros.revision][1](fila)) return false;
  if (filtros.senal && !SENALES[filtros.senal][1](fila)) return false;
  if (filtros.texto) {
    const pajar = `${fila.titulo} ${fila.medios.join(" ")} ${fila.id_evento} ${nombreTema(fila.tema)}`.toLowerCase();
    return filtros.texto.toLowerCase().split(/\s+/).every((palabra) => pajar.includes(palabra));
  }
  return true;
}

function filaCaso(fila) {
  const oficial = { indicador_banco_mundial: "Banco Mundial", sismo_usgs: "USGS" };
  return h("a", { class: "caso", href: `#/caso/${encodeURIComponent(fila.id_evento)}` },
    h("span", { class: "caso__posicion" }, fila.posicion),
    h("span", { class: "caso__puntaje" }, h("b", null, puntos(fila.puntaje)), nivel(fila.nivel)),
    glifo(fila.componentes),
    h("span", null,
      h("span", { class: `titular caso__titulo ${fila.sin_evidencia_utilizable ? "titular--no-confiable" : ""}`.trim() }, fila.titulo),
      h("span", { class: "caso__meta" },
        h("span", { class: "chip" }, nombreTema(fila.tema)),
        h("span", null, `${plural(fila.n_noticias, "nota", "notas")} · ${plural(fila.fuentes_independientes, "procedencia", "procedencias")}`),
        fila.fecha ? h("span", { class: "punto" }, `${(TIPO_FECHA[fila.tipo_fecha] || "Fecha").toLowerCase()} ${soloFecha(fila.fecha)}`) : null,
        fila.contradiccion ? h("span", { class: "chip chip--alerta" }, "Cifras en conflicto") : null,
        fila.dato_oficial.map((tipo) => h("span", { class: "chip chip--acento" }, `Dato oficial · ${oficial[tipo] || tipo}`)),
        fila.antigua ? h("span", { class: "chip chip--alerta" }, fila.antigua === "recirculada" ? "Recirculada" : "Antigua en el feed") : null,
        fila.no_confiable ? h("span", { class: "chip chip--critico" }, "Contenido no confiable") : null,
        fila.bloqueada ? h("span", { class: "chip chip--critico" }, "Bloqueada por el validador") : null,
        !fila.tiene_ficha ? h("span", { class: "chip chip--contorno" }, "Sin ficha") : null)),
    h("span", { class: "caso__columna" }, evidencia(fila.estado_evidencia, false, true), h("small", null, fila.motivo_estado_evidencia)),
    h("span", { class: "caso__columna" }, estadoRevision(fila.estado_revision), fila.revisor ? h("small", null, `por ${fila.revisor}`) : null));
}

export async function bandeja(raiz) {
  const filas = await api.bandeja();
  const meta = sesion.meta;
  const temas = [...new Set(filas.map((f) => f.tema))];
  const zonaResumen = h("div", { class: "resumenes" });
  const zonaLista = h("div", { class: "tarjeta lista" });
  const cuenta = h("span", { class: "filtros__cuenta" });
  const limpiar = h("button", { class: "boton boton--fantasma boton--chico", type: "button", onclick: () => {
    Object.keys(filtros).forEach((clave) => { filtros[clave] = ""; });
    campoTexto.value = ""; selectorTema.value = ""; selectorSenal.value = "";
    pintar();
  } }, icono("cerrar", "icono--chico"), "Quitar filtros");

  const campoTexto = h("input", { class: "campo", type: "search", placeholder: "Filtrar por titular, medio, tema o ID", value: filtros.texto,
    "aria-label": "Filtrar la bandeja", oninput: (e) => { filtros.texto = e.target.value.trim(); visibles = POR_TANDA; pintar(); } });
  const selectorTema = h("select", { class: "campo", "aria-label": "Tema", onchange: (e) => { filtros.tema = e.target.value; pintar(); } },
    h("option", { value: "" }, "Todos los temas"), temas.map((t) => h("option", { value: t, selected: filtros.tema === t }, nombreTema(t))));
  const selectorSenal = h("select", { class: "campo", "aria-label": "Señales", onchange: (e) => { filtros.senal = e.target.value; pintar(); } },
    h("option", { value: "" }, "Todas las señales"),
    Object.entries(SENALES).map(([clave, [nombre]]) => h("option", { value: clave, selected: filtros.senal === clave }, nombre)));

  function cifra(grupo, valor, etiqueta, cantidad, marca) {
    return h("button", { class: "cifra", type: "button", "aria-pressed": String(filtros[grupo] === valor),
      title: filtros[grupo] === valor ? "Quitar este filtro" : "Filtrar la bandeja",
      onclick: () => { filtros[grupo] = filtros[grupo] === valor ? "" : valor; visibles = POR_TANDA; pintar(); } },
    h("b", null, cantidad), h("span", null, marca, etiqueta));
  }

  function pintar() {
    const contar = (prueba) => filas.filter(prueba).length;
    vaciar(zonaResumen,
      h("section", { class: "tarjeta resumen" }, h("h2", null, "Puntaje de atención"), h("div", { class: "resumen__cifras" },
        ["alto", "medio", "bajo"].map((n) => cifra("nivel", n, null, contar((f) => f.nivel === n), nivel(n))))),
      h("section", { class: "tarjeta resumen" }, h("h2", null, "Estado de evidencia", h("span", { class: "conteo" }, "· independiente del puntaje")),
        h("div", { class: "resumen__cifras" }, ["insuficiente", "parcial", "suficiente para el borrador"].map((e) =>
          cifra("evidencia", e, null, contar((f) => f.estado_evidencia === e), evidencia(e, false, true))))),
      h("section", { class: "tarjeta resumen" }, h("h2", null, "Revisión humana"), h("div", { class: "resumen__cifras" },
        Object.entries(GRUPOS_REVISION).map(([clave, [nombre, prueba]]) => cifra("revision", clave, nombre, contar(prueba))))));

    const elegidas = filas.filter(cumple);
    const hayFiltros = Object.values(filtros).some(Boolean);
    limpiar.hidden = !hayFiltros;
    cuenta.textContent = hayFiltros ? `${elegidas.length} de ${filas.length} casos` : `${filas.length} casos`;

    vaciar(zonaLista,
      h("div", { class: "lista__cabecera" }, h("span", null, "N.º"), h("span", null, "Puntaje"),
        h("span", { title: "Ancho = peso del componente · alto = su valor · área = lo que aporta al puntaje" }, letrasGlifo()),
        h("span", null, "Caso"), h("span", null, "Evidencia"), h("span", null, "Revisión")),
      elegidas.length ? elegidas.slice(0, visibles).map(filaCaso)
        : h("div", { class: "vacio" }, h("strong", null, "Ningún caso cumple esos filtros"), "Quite un filtro para ver más casos."),
      elegidas.length > visibles ? h("div", { class: "lista__pie" },
        h("button", { class: "boton", type: "button", onclick: () => { visibles += POR_TANDA; pintar(); } },
          `Mostrar ${Math.min(POR_TANDA, elegidas.length - visibles)} más`, icono("abajo", "icono--chico"))) : null);
  }

  vaciar(raiz,
    h("div", { class: "encabezado" },
      h("div", null,
        h("div", { class: "sobretitulo" }, "Etapa 4 · Priorizar"),
        h("h1", null, "Bandeja priorizada"),
        h("p", null, `${plural(meta.eventos, "evento", "eventos")} a partir de ${plural(meta.noticias, "nota", "notas")} · corte del snapshot `,
          h("strong", null, meta.fecha_corte_panama || "sin fecha de corte"), ` · ${meta.reglas.version}`)),
      h("div", null,
        h("a", { class: "boton boton--chico", href: `#/consulta?q=${encodeURIComponent("¿Cómo se calcula el puntaje de atención?")}`,
          title: "Ver la regla completa" }, h("span", { class: "mono" }, meta.reglas.formula)))),
    aviso("La prioridad ordena la revisión: no confirma la noticia ni habilita su publicación. El estado de evidencia se evalúa aparte, y la decisión es de una persona.", "acento", "balanza"),
    h("div", { estilo: { height: "1rem" } }),
    zonaResumen,
    h("div", { class: "filtros" }, h("label", { class: "buscador" }, icono("buscar", "icono--chico"), campoTexto), selectorTema, selectorSenal, limpiar, cuenta),
    zonaLista);
  pintar();
}
