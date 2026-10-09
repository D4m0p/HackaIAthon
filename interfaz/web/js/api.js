// Llamadas al servidor local. No hay ninguna otra dirección a la que la pantalla pueda hablar.

export class ErrorApi extends Error {
  constructor(mensaje, estado) {
    super(mensaje);
    this.estado = estado;
  }
}

async function pedir(ruta, opciones) {
  let respuesta;
  try {
    respuesta = await fetch(ruta, opciones);
  } catch {
    throw new ErrorApi("No se pudo hablar con el servidor local. ¿Sigue abierto «python -m interfaz»?", 0);
  }
  const esJson = (respuesta.headers.get("Content-Type") || "").includes("json");
  const cuerpo = esJson ? await respuesta.json() : await respuesta.text();
  if (!respuesta.ok) throw new ErrorApi((esJson && cuerpo.error) || `Error ${respuesta.status}`, respuesta.status);
  return cuerpo;
}

const leer = (ruta) => pedir(ruta);
const enviar = (ruta, datos) => pedir(ruta, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos || {}),
});
const caso = (id) => `/api/casos/${encodeURIComponent(id)}`;

export const api = {
  estado: () => leer("/api/estado"),
  bandeja: () => leer("/api/bandeja"),
  caso: (id) => leer(caso(id)),
  markdown: (id) => leer(`${caso(id)}/markdown`),
  registro: () => leer("/api/registro"),
  datos: () => leer("/api/datos"),
  consultar: (pregunta) => enviar("/api/consulta", { pregunta }),
  revisar: (id, estado, revisor, nota) => enviar(`${caso(id)}/revision`, { estado, revisor, nota }),
  corregir: (id, cambios, revisor, nota) => enviar(`${caso(id)}/borrador`, { cambios, revisor, nota }),
  generarFicha: (id) => enviar(`${caso(id)}/ficha`),
  notion: (id, revisor) => enviar(`${caso(id)}/notion`, { revisor }),
  reiniciarEjemplo: () => enviar("/api/ejemplo/reiniciar"),
};
