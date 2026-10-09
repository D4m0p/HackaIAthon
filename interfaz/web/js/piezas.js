// Piezas que se repiten en varias vistas: nivel, evidencia, estado, citas, tarjetas y gráficos.

import { h, s, icono, numero, puntos, plural, tiempo, fechaHora, enUtc, soloFecha, TIPO_AFIRMACION, TIPO_FECHA, NOTA_TIPO_FECHA } from "./dom.js";

export const sesion = { meta: null };

const ICONO_ESTADO = {
  "nuevo": "nuevo", "en revisión": "ojo", "requiere evidencia": "lupa_doc",
  "aprobado como borrador": "listo", "descartado": "prohibido",
};
const NOMBRE_EVIDENCIA = {
  "insuficiente": "Insuficiente", "parcial": "Parcial", "suficiente para el borrador": "Suficiente para el borrador",
};
const MAYUSCULA = (texto) => texto.charAt(0).toUpperCase() + texto.slice(1);

export const nombreTema = (tema) => (sesion.meta?.temas?.[tema]) || tema;

export function nivel(valor) {
  return h("span", { class: "nivel", dataset: { nivel: valor }, title: `Nivel ${valor}: ordena la revisión, no mide veracidad` },
    h("span", { class: "nivel__senal", "aria-hidden": "true" }, h("i"), h("i"), h("i")), valor);
}

export function evidencia(estado, grande = false, corto = false) {
  const nombre = NOMBRE_EVIDENCIA[estado] || estado;
  return h("span", { class: grande ? "evidencia evidencia-grande" : "evidencia", dataset: { estado }, title: `Estado de evidencia: ${nombre.toLowerCase()}` },
    h("span", { class: "evidencia__pasos", "aria-hidden": "true" }, h("i"), h("i"), h("i")),
    corto ? nombre.split(" ")[0] : nombre);
}

export function estadoRevision(estado) {
  return h("span", { class: "estado", dataset: { estado } }, icono(ICONO_ESTADO[estado] || "nuevo", "icono--chico"), MAYUSCULA(estado));
}

/** Composición del puntaje: ancho = peso del componente, alto = su valor (0 a 1), área = aporte. */
export function glifo(componentes) {
  const meta = sesion.meta.reglas.componentes;
  return h("span", { class: "glifo", role: "img", "aria-label": Object.entries(componentes)
    .map(([clave, c]) => `${meta[clave].nombre} ${c.aporte} de ${c.peso}`).join(", ") },
  Object.entries(componentes).map(([clave, c]) => h("span", {
    class: "glifo__barra", estilo: { width: `${c.peso * 0.4}px` },
    title: `${clave} · ${meta[clave].nombre}: ${c.valor} × ${c.peso} = ${c.aporte}`,
  }, h("i", { estilo: { height: `${Math.round(c.valor * 100)}%` } }))));
}

export function letrasGlifo() {
  return h("span", { class: "glifo-letras", "aria-hidden": "true" },
    Object.entries(sesion.meta.reglas.pesos).map(([clave, peso]) => h("span", { estilo: { width: `${peso * 0.4}px` } }, clave)));
}

export function aviso(texto, tono = "", nombreIcono = "info") {
  return h("div", { class: `aviso ${tono ? `aviso--${tono}` : ""}`.trim() }, icono(nombreIcono, "icono--chico"), h("span", null, texto));
}

/** Tono de un aviso según lo que dice: lo crítico no debe verse igual que lo informativo. */
export function tonoDeAviso(texto) {
  if (/bloqueada|no confiable|instrucciones al sistema/i.test(texto)) return ["critico", "escudo"];
  if (/recirculada|antigua|clasificador de respaldo|plantilla/i.test(texto)) return ["alerta", "alerta"];
  if (/prioridad ordena/i.test(texto)) return ["acento", "balanza"];
  return ["", "info"];
}

// ---------- citas ----------
function resolverCita(marca, evid) {
  if (marca in evid) return { id: marca, campo: null };
  const corte = marca.lastIndexOf(":");
  if (corte > 0) {
    const id = marca.slice(0, corte);
    const campo = marca.slice(corte + 1);
    if (id in evid && campo in evid[id]) return { id, campo };
  }
  return null;
}

function rotuloCita(id, campo, elemento) {
  let corto = id;
  if (elemento.tipo === "indicador_banco_mundial") corto = `BM ${elemento.pais} ${elemento.anio}`;
  else if (elemento.tipo === "sismo_usgs") corto = `USGS ${id.replace(/^USGS:/, "")}`;
  return campo ? `${corto} · ${campo}` : corto;
}

export function chipCita(id, campo, evid, alAbrir) {
  const elemento = evid[id];
  if (!elemento) {
    return h("span", { class: "cita cita--rota", title: "Esta cita no corresponde a ningún elemento de la evidencia" }, `${id}${campo ? `:${campo}` : ""}`);
  }
  return h("button", { class: "cita", type: "button", title: `Ver la evidencia citada: ${id}${campo ? ` → ${campo}` : ""}`,
    onclick: () => alAbrir(id, campo) }, rotuloCita(id, campo, elemento));
}

/** Texto con sus [ID:campo] convertidos en citas que se pueden abrir. */
export function textoConCitas(texto, evid, alAbrir, citasExtra = []) {
  const fragmento = document.createDocumentFragment();
  const vistas = new Set();
  let ultimo = 0;
  for (const coincidencia of String(texto || "").matchAll(/\[([^\[\]]+?)\]/g)) {
    fragmento.append(texto.slice(ultimo, coincidencia.index));
    const resuelta = resolverCita(coincidencia[1], evid);
    if (resuelta) {
      vistas.add(`${resuelta.id}:${resuelta.campo}`);
      fragmento.append(chipCita(resuelta.id, resuelta.campo, evid, alAbrir));
    } else {
      fragmento.append(chipCita(coincidencia[1], null, {}, alAbrir));
    }
    ultimo = coincidencia.index + coincidencia[0].length;
  }
  fragmento.append(String(texto || "").slice(ultimo));
  for (const cita of citasExtra) {
    if (vistas.has(`${cita.id_evidencia}:${cita.campo}`)) continue;
    fragmento.append(" ", chipCita(cita.id_evidencia, cita.campo, evid, alAbrir));
  }
  return fragmento;
}

export function tipoAfirmacion(tipo) {
  const [nombre, explicacion] = TIPO_AFIRMACION[tipo] || [tipo, ""];
  return h("span", { class: "tipo", dataset: { tipo }, title: explicacion }, nombre);
}

export function listaAfirmaciones(afirmaciones, evid, alAbrir) {
  return h("ul", { class: "afirmaciones" }, afirmaciones.map((a) => h("li", { class: "afirmacion" },
    tipoAfirmacion(a.tipo),
    h("span", { class: "afirmacion__texto" }, textoConCitas(a.texto, evid, alAbrir, a.citas)))));
}

export function leyendaTipos() {
  return h("div", { class: "leyenda-tipos" }, Object.entries(TIPO_AFIRMACION).map(([tipo, [nombre, explicacion]]) =>
    h("span", null, h("span", { class: "tipo", dataset: { tipo } }, nombre), ` ${explicacion}`)));
}

// ---------- diálogo de evidencia ----------
const ROTULOS = {
  titulo: "Titular", medio: "Medio", fecha: "Fecha", tipo_fecha: "Tipo de fecha", antiguedad: "Antigüedad", url: "Enlace",
  alcance_texto: "Alcance del texto", nombre: "Indicador", pais: "País", pais_nombre: "País", anio: "Año", valor: "Valor",
  unidad: "Unidad", fuente_url: "Fuente", licencia: "Licencia", advertencia: "Advertencia", magnitud: "Magnitud",
  lugar: "Lugar", fecha_utc: "Fecha del sismo", profundidad_km: "Profundidad (km)", estado: "Estado del registro",
  indicador_id: "Código del indicador", serie: "Serie", comparacion: "Comparación",
};
const NOMBRE_TIPO = {
  noticia: "Noticia · solo titular y metadatos", indicador_banco_mundial: "Indicador del Banco Mundial · dato anual",
  sismo_usgs: "Registro sísmico de USGS",
};

function valorLegible(campo, valor) {
  if (valor === null || valor === undefined) return "sin dato";
  if (campo === "url" || campo === "fuente_url") {
    return h("a", { href: valor, target: "_blank", rel: "noopener noreferrer" }, valor, " ", icono("externo", "icono--chico"));
  }
  if (campo === "fecha" || campo === "fecha_utc") return `${fechaHora(valor)} (hora de Panamá) · ${enUtc(valor)}`;
  if (campo === "tipo_fecha") return TIPO_FECHA[valor] || valor;
  if (campo === "titulo") return h("span", { class: "titular" }, `«${valor}»`);
  if (campo === "serie") return valor.map((p) => `${p.anio}: ${numero(p.valor)}`).join(" · ");
  if (campo === "comparacion") return valor.map((p) => `${p.pais} ${p.anio}: ${numero(p.valor)}`).join(" · ");
  if (typeof valor === "object") return JSON.stringify(valor);
  return String(valor);
}

export function abrirEvidencia(id, campo, evid) {
  const elemento = evid[id];
  const dialogo = document.getElementById("dialogo");
  if (!elemento) return;
  const campos = Object.keys(elemento).filter((c) => c !== "tipo" && c !== "pais_nombre");
  dialogo.replaceChildren(
    h("div", { class: "dialogo__cabeza" },
      h("div", null, h("div", { class: "sobretitulo" }, NOMBRE_TIPO[elemento.tipo] || elemento.tipo),
        h("h2", { class: "mono" }, id)),
      h("button", { class: "icono-boton", type: "button", "aria-label": "Cerrar", onclick: () => dialogo.close() }, icono("cerrar"))),
    h("div", { class: "dialogo__cuerpo" },
      campo ? h("div", { class: "campo-citado" },
        h("small", null, `Campo citado · ${ROTULOS[campo] || campo}`), h("div", null, valorLegible(campo, elemento[campo]))) : null,
      elemento.advertencia ? aviso(elemento.advertencia, "alerta", "alerta") : null,
      elemento.tipo === "noticia" && NOTA_TIPO_FECHA[elemento.tipo_fecha] ? aviso(NOTA_TIPO_FECHA[elemento.tipo_fecha], "alerta", "reloj") : null,
      elemento.antiguedad ? aviso("Contenido antiguo: no debe presentarse como un hecho nuevo.", "alerta", "ciclo") : null,
      h("dl", { class: "pares" }, campos.filter((c) => c !== "advertencia").flatMap((c) => [
        h("dt", null, ROTULOS[c] || c),
        h("dd", { dataset: { citado: c === campo ? "si" : "no" } }, valorLegible(c, elemento[c])),
      ]))));
  dialogo.showModal();
}

// ---------- serie de un indicador ----------
/** Línea de una sola serie con los años de referencia marcados. La tabla de abajo trae los mismos valores. */
export function graficoSerie(puntosSerie, unidad, destacados = []) {
  const validos = puntosSerie.filter((p) => typeof p.valor === "number");
  if (validos.length < 2) return null;
  const ancho = 420, alto = 118, margen = { izq: 8, der: 46, arr: 18, aba: 22 };
  const valores = validos.map((p) => p.valor);
  const minimo = Math.min(...valores, 0), maximo = Math.max(...valores, 0);
  const rango = (maximo - minimo) || 1;
  const x = (i) => margen.izq + (i / (puntosSerie.length - 1)) * (ancho - margen.izq - margen.der);
  const y = (v) => margen.arr + (1 - (v - minimo) / rango) * (alto - margen.arr - margen.aba);
  const posiciones = puntosSerie.map((p, i) => ({ ...p, x: x(i), y: typeof p.valor === "number" ? y(p.valor) : null }));

  // Un año sin dato corta la línea: no se une ni se trata como cero.
  let trazo = "", pluma = false;
  for (const p of posiciones) {
    if (p.y === null) { pluma = false; continue; }
    trazo += `${pluma ? "L" : "M"}${p.x.toFixed(1)} ${p.y.toFixed(1)} `;
    pluma = true;
  }
  const marcados = new Set(destacados.length ? destacados : [validos[validos.length - 1].anio]);
  const guia = s("line", { class: "serie__guia", y1: margen.arr - 6, y2: alto - margen.aba });
  const lienzo = s("svg", { viewBox: `0 0 ${ancho} ${alto}`, role: "img",
    "aria-label": `Serie anual. ${validos.map((p) => `${p.anio}: ${numero(p.valor)}`).join("; ")}` },
    s("line", { class: "serie__base", x1: margen.izq, x2: ancho - margen.der, y1: y(0), y2: y(0) }),
    guia,
    s("path", { class: "serie__linea", d: trazo.trim() }),
    posiciones.filter((p) => p.y !== null).map((p) => s("circle", {
      class: marcados.has(p.anio) ? "serie__punto" : "serie__punto serie__punto--tenue", cx: p.x, cy: p.y, r: marcados.has(p.anio) ? 4.5 : 2.5 })),
    posiciones.filter((p) => p.y !== null && marcados.has(p.anio)).map((p) => {
      const rotulo = s("text", { class: "serie__rotulo serie__rotulo--valor", x: p.x + 8, y: p.y + 4 });
      rotulo.textContent = numero(p.valor);
      return rotulo;
    }),
    [posiciones[0], posiciones[posiciones.length - 1]].map((p, i) => {
      const rotulo = s("text", { class: "serie__rotulo", x: p.x, y: alto - 5, "text-anchor": i ? "end" : "start" });
      rotulo.textContent = p.anio;
      return rotulo;
    }));

  const globo = h("div", { class: "serie__globo" });
  const envoltura = h("div", { class: "serie" }, lienzo, globo);
  lienzo.addEventListener("pointermove", (evento) => {
    const caja = lienzo.getBoundingClientRect();
    const dentro = ((evento.clientX - caja.left) / caja.width) * ancho;
    const cercano = posiciones.reduce((a, b) => (Math.abs(b.x - dentro) < Math.abs(a.x - dentro) ? b : a));
    guia.setAttribute("x1", cercano.x); guia.setAttribute("x2", cercano.x);
    guia.style.opacity = "0.5";
    globo.replaceChildren(h("b", null, numero(cercano.valor)), `${cercano.anio}${cercano.y === null ? "" : ` · ${unidad}`}`);
    globo.style.left = `${(cercano.x / ancho) * 100}%`;
    globo.style.top = `${((cercano.y ?? margen.arr) / alto) * 100}%`;
    globo.style.opacity = "1";
  });
  lienzo.addEventListener("pointerleave", () => { guia.style.opacity = "0"; globo.style.opacity = "0"; });

  envoltura.append(h("details", { class: "tabla-serie" }, h("summary", null, "Ver los valores en tabla"),
    h("table", { class: "tabla" }, h("thead", null, h("tr", null, h("th", null, "Año"), h("th", { class: "num" }, unidad))),
      h("tbody", null, puntosSerie.map((p) => h("tr", null, h("td", null, p.anio), h("td", { class: "num" }, numero(p.valor))))))));
  return envoltura;
}

// ---------- tarjeta de un caso (respuestas y recorrido) ----------
export function tarjetaCaso(caso, compacta = false) {
  const titulo = h("a", { class: `titular tarjeta-caso__titulo ${caso.no_confiable ? "titular--no-confiable" : ""}`.trim(),
    href: `#/caso/${encodeURIComponent(caso.id_evento)}` }, caso.titulo);
  const fila = h("div", { class: "tarjeta-caso__fila" },
    h("span", { class: "chip" }, nombreTema(caso.tema)),
    h("span", null, `${plural(caso.n_noticias, "nota", "notas")} · ${plural(caso.fuentes_independientes, "procedencia", "procedencias")}`),
    evidencia(caso.estado_evidencia),
    caso.estado_revision ? estadoRevision(caso.estado_revision) : null,
    caso.contradiccion ? h("span", { class: "chip chip--alerta" }, "Cifras en conflicto") : null,
    caso.antigua ? h("span", { class: "chip chip--alerta" }, "Contenido antiguo") : null,
    caso.no_confiable ? h("span", { class: "chip chip--critico" }, "No confiable") : null);
  const cuerpo = compacta ? [titulo, fila] : [titulo, fila,
    h("dl", null,
      h("dt", null, "Por qué sube"),
      h("dd", null, caso.por_que.map((c, i) => [i ? " · " : "", h("b", null, `${c.componente} ${c.aporte}/${c.peso}`), ` ${c.explicacion}`])),
      h("dt", null, "Evidencia"),
      h("dd", null, `${caso.motivo_estado_evidencia}.`),
      h("dt", null, "Falta verificar"),
      h("dd", null, caso.vacios.length ? caso.vacios.join(" ").replace(/\s*\[[^\[\]]+?\]/g, "") : "Sin pendientes registrados.")),
    h("div", { class: "tarjeta-caso__pie" },
      h("a", { class: "boton boton--chico", href: `#/caso/${encodeURIComponent(caso.id_evento)}` }, "Abrir ficha", icono("flecha", "icono--chico")))];
  return h("article", { class: `tarjeta-caso ${compacta ? "tarjeta-caso--compacta" : ""}`.trim() },
    h("div", { class: "tarjeta-caso__puntaje" }, h("b", null, puntos(caso.puntaje)), nivel(caso.nivel), h("small", null, `N.º ${caso.posicion}`)),
    h("div", null, cuerpo));
}

export function versiones(lista) {
  return h("div", { class: "versiones" }, lista.map((v) => h("div", { class: "version" },
    h("b", null, v.cifra),
    v.fuentes.map((f) => [h("small", null, `${f.medio} · `, h("span", { class: "mono" }, f.id_noticia)),
      h("span", { class: "titular" }, `«${f.titulo}»`)]))));
}

export { tiempo, soloFecha };
