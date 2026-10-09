// Utilidades de pantalla. Todo texto que viene de una fuente se inserta como texto,
// nunca como HTML: un titular es un dato, no código.

const SVG = "http://www.w3.org/2000/svg";

export function h(etiqueta, atributos, ...hijos) {
  const nodo = document.createElement(etiqueta);
  for (const [clave, valor] of Object.entries(atributos || {})) {
    if (valor === null || valor === undefined || valor === false) continue;
    if (clave === "class") nodo.className = valor;
    else if (clave === "dataset") Object.assign(nodo.dataset, valor);
    else if (clave.startsWith("on")) nodo.addEventListener(clave.slice(2), valor);
    else if (clave === "estilo") for (const [p, v] of Object.entries(valor)) nodo.style.setProperty(p, v);
    else if (valor === true) nodo.setAttribute(clave, "");
    else nodo.setAttribute(clave, valor);
  }
  agregar(nodo, hijos);
  return nodo;
}

export function agregar(nodo, hijos) {
  for (const hijo of hijos.flat(Infinity)) {
    if (hijo === null || hijo === undefined || hijo === false) continue;
    nodo.append(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
  }
  return nodo;
}

export function vaciar(nodo, ...hijos) {
  nodo.replaceChildren();
  return agregar(nodo, hijos);
}

export function s(etiqueta, atributos, ...hijos) {
  const nodo = document.createElementNS(SVG, etiqueta);
  for (const [clave, valor] of Object.entries(atributos || {})) {
    if (valor !== null && valor !== undefined && valor !== false) nodo.setAttribute(clave, valor);
  }
  for (const hijo of hijos.flat()) if (hijo) nodo.append(hijo);
  return nodo;
}

// Trazos propios de los iconos (caja de 24, línea de 1.7).
const TRAZOS = {
  buscar: ["M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z", "M20 20l-3.6-3.6"],
  flecha: ["M5 12h14", "M13 6l6 6-6 6"],
  atras: ["M19 12H5", "M11 6l-6 6 6 6"],
  arriba: ["M6 15l6-6 6 6"],
  abajo: ["M6 9l6 6 6-6"],
  externo: ["M14 5h5v5", "M19 5l-8 8", "M18 14v4a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h4"],
  copiar: ["M9 9h10v11H9z", "M5 15V4h10"],
  descargar: ["M12 4v11", "M7 11l5 5 5-5", "M5 20h14"],
  enviar: ["M4 12l16-7-6 16-2.5-6.5z"],
  listo: ["M5 12.5l4.5 4.5L19 7.5"],
  cerrar: ["M6 6l12 12", "M18 6L6 18"],
  alerta: ["M12 4l9 16H3z", "M12 10v4.5", "M12 17.4v.1"],
  info: ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z", "M12 11v5.5", "M12 7.6v.1"],
  escudo: ["M12 3l7.5 3v5.5c0 4.7-3.2 8.2-7.5 9.5-4.3-1.3-7.5-4.8-7.5-9.5V6z", "M9 12l2.2 2.2L15.2 10"],
  reloj: ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z", "M12 7.5V12l3 2"],
  lapiz: ["M4 20l.8-4L16 4.8a1.6 1.6 0 0 1 2.3 0l.9.9a1.6 1.6 0 0 1 0 2.3L8 19.2z", "M14.5 6.5l3 3"],
  ojo: ["M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z", "M12 9.3a2.7 2.7 0 1 0 0 5.4 2.7 2.7 0 0 0 0-5.4z"],
  lupa_doc: ["M7 3h7l4 4v6", "M14 3v4h4", "M7 3v18h5", "M16.5 14a3 3 0 1 0 0 6 3 3 0 0 0 0-6z", "M21 22l-2.3-2.3"],
  prohibido: ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z", "M5.7 5.7l12.6 12.6"],
  ciclo: ["M4 12a8 8 0 0 1 13.7-5.6L20 8.5", "M20 4v4.5h-4.5", "M20 12a8 8 0 0 1-13.7 5.6L4 15.5", "M4 20v-4.5h4.5"],
  balanza: ["M12 4v16", "M7 20h10", "M5 8h14", "M5 8l-2.5 6a2.5 2.5 0 0 0 5 0z", "M19 8l-2.5 6a2.5 2.5 0 0 0 5 0z"],
  dato: ["M4 6.5C4 5 7.6 4 12 4s8 1 8 2.5S16.4 9 12 9 4 8 4 6.5z", "M4 6.5V12c0 1.5 3.6 2.5 8 2.5s8-1 8-2.5V6.5", "M4 12v5.5C4 19 7.6 20 12 20s8-1 8-2.5V12"],
  sol: ["M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z", "M12 2.5v2", "M12 19.5v2", "M2.5 12h2", "M19.5 12h2", "M5.3 5.3l1.4 1.4", "M17.3 17.3l1.4 1.4", "M5.3 18.7l1.4-1.4", "M17.3 6.7l1.4-1.4"],
  luna: ["M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5z"],
  pantalla: ["M3 5h18v11H3z", "M9 20h6", "M12 16v4"],
  persona: ["M12 4a4 4 0 1 0 0 8 4 4 0 0 0 0-8z", "M4.5 20.5a7.5 7.5 0 0 1 15 0"],
  nuevo: ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z"],
  documento: ["M7 3h7l4 4v14H7z", "M14 3v4h4", "M10 12h5", "M10 16h5"],
  rayo: ["M13 3L5 13.5h6L10 21l8-10.5h-6z"],
};

export function icono(nombre, clase = "") {
  return s("svg", { class: `icono ${clase}`.trim(), viewBox: "0 0 24 24", "aria-hidden": "true" },
    (TRAZOS[nombre] || TRAZOS.info).map((d) => s("path", { d })));
}

// ---------- formato ----------
const ZONA = "America/Panama";
const FECHA_HORA = new Intl.DateTimeFormat("es-PA", { timeZone: ZONA, day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
const FECHA = new Intl.DateTimeFormat("es-PA", { timeZone: ZONA, day: "numeric", month: "short", year: "numeric" });
const UTC = new Intl.DateTimeFormat("es-PA", { timeZone: "UTC", day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });

function aFecha(iso) {
  if (!iso) return null;
  const fecha = new Date(iso);
  return Number.isNaN(fecha.getTime()) ? null : fecha;
}

/** La interfaz muestra hora de Panamá; el dato guardado está en UTC. */
export function fechaHora(iso) {
  const fecha = aFecha(iso);
  return fecha ? FECHA_HORA.format(fecha) : "sin fecha";
}
export function soloFecha(iso) {
  const fecha = aFecha(iso);
  return fecha ? FECHA.format(fecha) : "sin fecha";
}
export function enUtc(iso) {
  const fecha = aFecha(iso);
  return fecha ? `${UTC.format(fecha)} UTC` : "";
}

/** Marca de tiempo con la hora de Panamá a la vista y el UTC original al pasar el cursor. */
export function tiempo(iso, conHora = true) {
  return h("time", { datetime: iso || "", title: iso ? `${enUtc(iso)} · se muestra en hora de Panamá` : "" },
    conHora ? fechaHora(iso) : soloFecha(iso));
}

const NUMERO = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
export function numero(valor) {
  if (valor === null || valor === undefined || valor === "sin dato") return "sin dato";
  return typeof valor === "number" ? NUMERO.format(valor) : String(valor);
}
export const puntos = (valor) => Number(valor).toFixed(1);
export const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;

export const TIPO_FECHA = { publicacion: "Publicada", deteccion: "Detectada", primera_aparicion: "Primera aparición" };
export const NOTA_TIPO_FECHA = {
  deteccion: "Fecha en que se detectó la nota, no la de su publicación.",
  primera_aparicion: "Primera vez que este titular apareció en el paquete.",
};
export const TIPO_AFIRMACION = {
  hecho: ["Hecho", "Lo respalda un dato oficial o fuentes independientes."],
  declaracion: ["Declaración", "Lo que un medio o una fuente dice, atribuido."],
  inferencia: ["Inferencia", "Conclusión razonable a partir de la evidencia."],
  hipotesis: ["Hipótesis", "Posibilidad por investigar, no confirmada."],
};

export function tostada(mensaje, tipo = "ok") {
  const nodo = h("div", { class: "tostada", dataset: { tipo } }, mensaje);
  document.getElementById("tostadas").append(nodo);
  setTimeout(() => nodo.remove(), tipo === "error" ? 6500 : 3200);
}

export async function copiar(texto) {
  try {
    await navigator.clipboard.writeText(texto);
    return true;
  } catch {
    const area = h("textarea", { class: "solo-lectores" });
    area.value = texto;
    document.body.append(area);
    area.select();
    const hecho = document.execCommand("copy");
    area.remove();
    return hecho;
  }
}
