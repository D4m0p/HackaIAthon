// Arranque y navegación. La dirección (#/bandeja, #/caso/ID…) decide qué vista se pinta.

import { h, vaciar, icono } from "./dom.js";
import { api } from "./api.js";
import { sesion, aviso } from "./piezas.js";
import { bandeja } from "./vistas/bandeja.js";
import { ficha } from "./vistas/ficha.js";
import { consulta } from "./vistas/consulta.js";
import { registro } from "./vistas/registro.js";
import { datos } from "./vistas/datos.js";
import { recorrido } from "./vistas/recorrido.js";

const VISTAS = { bandeja, consulta, registro, datos, recorrido };
const principal = document.getElementById("contenido");
let turno = 0;

function recordar(clave, valor) {
  try {
    if (valor === undefined) return localStorage.getItem(clave);
    localStorage.setItem(clave, valor);
  } catch { /* sin almacenamiento local: la preferencia dura lo que la pestaña */ }
  return valor;
}

// ---------- preferencias ----------
function temaActual() {
  return document.documentElement.dataset.theme
    || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
}

function prepararPreferencias() {
  const raiz = document.documentElement;
  const botonTema = document.getElementById("boton-tema");
  const botonPresentacion = document.getElementById("boton-presentacion");
  const campoRevisor = document.getElementById("revisor");

  const guardado = recordar("tema");
  if (guardado) raiz.dataset.theme = guardado;
  const pintarTema = () => vaciar(botonTema, icono(temaActual() === "dark" ? "sol" : "luna"));
  botonTema.addEventListener("click", () => {
    raiz.dataset.theme = recordar("tema", temaActual() === "dark" ? "light" : "dark");
    pintarTema();
  });
  pintarTema();

  const pintarPresentacion = (activa) => {
    raiz.dataset.presentacion = activa ? "si" : "no";
    botonPresentacion.setAttribute("aria-pressed", String(activa));
  };
  vaciar(botonPresentacion, icono("pantalla"));
  pintarPresentacion(recordar("presentacion") === "si");
  botonPresentacion.addEventListener("click", () => {
    const activa = raiz.dataset.presentacion !== "si";
    recordar("presentacion", activa ? "si" : "no");
    pintarPresentacion(activa);
  });

  campoRevisor.value = recordar("revisor") || "";
  campoRevisor.addEventListener("input", () => {
    recordar("revisor", campoRevisor.value.trim());
    if (campoRevisor.value.trim().length >= 3) delete campoRevisor.closest(".revisor").dataset.falta;
  });
}

function pintarMarco(meta) {
  const sello = document.getElementById("sello-datos");
  sello.hidden = false;
  sello.dataset.modo = meta.modo;
  sello.textContent = meta.modo === "ejemplo" ? "Ejemplo · datos sintéticos" : "Paquete del reto";
  sello.title = meta.modo === "ejemplo"
    ? "Datos de prueba. Las decisiones se guardan aparte del registro del reto."
    : `${meta.version_paquete || "Paquete real"} · corte ${meta.fecha_corte_panama}`;

  const franja = document.getElementById("franja");
  if (meta.modo === "ejemplo") {
    franja.hidden = false;
    vaciar(franja, icono("info", "icono--chico"),
      h("span", null, h("strong", null, "Modo ejemplo. "),
        "Datos sintéticos para practicar: lo que revise aquí se guarda aparte y no toca el registro del reto.",
        meta.avisos.length ? " Se muestran porque el núcleo de IA todavía no ha corrido sobre el paquete real." : ""));
  }
}

// ---------- navegación ----------
async function navegar() {
  const miTurno = ++turno;
  const [ruta, cola] = location.hash.replace(/^#\/?/, "").split("?");
  const partes = ruta.split("/").filter(Boolean).map(decodeURIComponent);
  const nombre = partes[0] || "bandeja";
  const parametros = new URLSearchParams(cola || "");

  for (const enlace of document.querySelectorAll(".navegacion a")) {
    const activa = enlace.dataset.vista === nombre || (nombre === "caso" && enlace.dataset.vista === "bandeja");
    if (activa) enlace.setAttribute("aria-current", "page"); else enlace.removeAttribute("aria-current");
  }
  document.getElementById("dialogo").close();

  const lienzo = h("div");
  try {
    if (nombre === "caso" && partes[1]) await ficha(lienzo, partes[1]);
    else if (VISTAS[nombre]) await VISTAS[nombre](lienzo, parametros);
    else { location.hash = "#/bandeja"; return; }
  } catch (error) {
    vaciar(lienzo, aviso(error.message || "No se pudo cargar la vista.", "critico", "alerta"),
      h("p", { estilo: { "margin-top": "1rem" } }, h("a", { class: "boton", href: "#/bandeja" }, "Volver a la bandeja")));
  }
  if (miTurno !== turno) return;
  principal.replaceChildren(lienzo);
  window.scrollTo(0, 0);
  if (nombre === "consulta") lienzo.querySelector("input[type=search]")?.focus();
}

async function iniciar() {
  prepararPreferencias();
  vaciar(principal, h("div", { class: "cargando" }, "Cargando el snapshot…"));
  try {
    sesion.meta = await api.estado();
  } catch (error) {
    vaciar(principal, aviso(error.message, "critico", "alerta"));
    return;
  }
  pintarMarco(sesion.meta);
  window.addEventListener("hashchange", navegar);
  await navegar();
}

iniciar();
