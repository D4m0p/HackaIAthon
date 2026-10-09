// Etapa 7 · Revisar: la bitácora de decisiones y el uso del sistema, listos para Notion.

import { h, vaciar, icono, tostada } from "../dom.js";
import { api } from "../api.js";
import { sesion, estadoRevision, aviso } from "../piezas.js";

function dato(valor, etiqueta, detalle) {
  return h("div", { class: "tarjeta dato" }, h("b", null, valor ?? "—"), h("span", null, etiqueta), detalle ? h("small", null, detalle) : null);
}

export async function registro(raiz) {
  const r = await api.registro();
  const c = r.consultas;
  const ejemplo = sesion.meta.modo === "ejemplo";

  async function reiniciar() {
    try {
      await api.reiniciarEjemplo();
      tostada("Registro de ejemplo reiniciado.");
      await registro(raiz);
    } catch (error) {
      tostada(error.message, "error");
    }
  }

  vaciar(raiz,
    h("div", { class: "encabezado" },
      h("div", null,
        h("div", { class: "sobretitulo" }, "Etapa 7 · Revisar"),
        h("h1", null, "Registro de revisión"),
        h("p", null, "Cada decisión la firma una persona y queda con fecha, estado anterior, estado nuevo y nota. La bitácora solo crece: nada se borra ni se reescribe.")),
      h("div", { estilo: { display: "flex", gap: ".5rem", "flex-wrap": "wrap" } },
        h("a", { class: "boton", href: "/api/exportar/fichas_revisadas.jsonl", download: "fichas_revisadas.jsonl",
          title: "Fichas en el formato del contrato de datos, con la decisión humana incorporada" }, icono("descargar", "icono--chico"), "fichas_revisadas.jsonl"),
        ejemplo ? h("button", { class: "boton boton--peligro", type: "button", onclick: reiniciar }, icono("ciclo", "icono--chico"), "Reiniciar el ejemplo") : null)),

    h("h2", { class: "sobretitulo", estilo: { margin: "0 0 .6rem" } }, "Casos por estado de revisión"),
    h("div", { class: "rejilla" }, Object.entries(r.por_estado).map(([estado, cantidad]) =>
      h("div", { class: "tarjeta dato" }, h("b", null, cantidad), estadoRevision(estado)))),

    h("h2", { class: "sobretitulo", estilo: { margin: "1.6rem 0 .6rem" } }, "Consultas atendidas en esta máquina"),
    h("div", { class: "rejilla" },
      dato(c.total, "consultas"),
      dato(c.abstenciones, "abstenciones y rechazos", c.total ? `${Math.round((c.abstenciones / c.total) * 100)} % de las consultas` : null),
      dato(c.afirmaciones, "afirmaciones emitidas", "todas con cita verificada"),
      dato(c.descartadas, "descartadas por la verificación", "no se mostraron como respuesta"),
      dato(c.mediana_ms === null ? null : `${c.mediana_ms} ms`, "tiempo mediano"),
      dato(c.p95_ms === null ? null : `${c.p95_ms} ms`, "percentil 95")),

    h("h2", { class: "sobretitulo", estilo: { margin: "1.6rem 0 .6rem" } }, `Bitácora de decisiones · ${r.decisiones.length}`),
    h("div", { class: "tarjeta" }, r.decisiones.length
      ? h("div", { class: "tabla-envoltura" }, h("table", { class: "tabla" },
        h("thead", null, h("tr", null, ["Fecha (hora de Panamá)", "Caso", "Acción", "Estado", "Persona", "Nota"].map((t) => h("th", null, t)))),
        h("tbody", null, r.decisiones.map((d) => h("tr", null,
          h("td", { class: "mono" }, (d.fecha_panama || "").replace(" (hora de Panamá)", "")),
          h("td", null, h("a", { href: `#/caso/${encodeURIComponent(d.id_evento)}` }, h("span", { class: "titular" }, d.titulo || d.id_evento)),
            h("div", { class: "mono tenue" }, `${d.id_caso} · puntaje ${d.puntaje} · evidencia ${d.estado_evidencia}`)),
          h("td", null, d.accion),
          h("td", null, d.estado_nuevo ? [h("span", { class: "tenue" }, `${d.estado_anterior} → `), estadoRevision(d.estado_nuevo)] : h("span", { class: "tenue" }, "sin cambio")),
          h("td", null, d.revisor),
          h("td", null, d.nota || h("span", { class: "tenue" }, "—")))))))
      : h("div", { class: "vacio" }, h("strong", null, "Aún no hay decisiones"), "Abra un caso de la bandeja y tome una decisión: quedará registrada aquí.")),

    c.recientes.length ? [
      h("h2", { class: "sobretitulo", estilo: { margin: "1.6rem 0 .6rem" } }, "Últimas consultas"),
      h("div", { class: "tarjeta" }, h("div", { class: "tabla-envoltura" }, h("table", { class: "tabla" },
        h("thead", null, h("tr", null, h("th", null, "Pregunta"), h("th", null, "Resultado"), h("th", { class: "num" }, "Citas"), h("th", { class: "num" }, "Tiempo"))),
        h("tbody", null, c.recientes.map((q) => h("tr", null,
          h("td", null, h("a", { href: `#/consulta?q=${encodeURIComponent(q.pregunta)}` }, q.pregunta)),
          h("td", null, h("span", { class: `chip ${q.abstencion ? "chip--serio" : "chip--bien"}` }, q.tipo.replaceAll("_", " "))),
          h("td", { class: "num" }, q.afirmaciones),
          h("td", { class: "num" }, `${q.tiempo_ms} ms`))))))),
    ] : null,

    h("div", { estilo: { "margin-top": "1.4rem" } },
      aviso(ejemplo
        ? "Este registro corresponde a los datos de ejemplo y se guarda aparte: no se mezcla con las decisiones sobre el paquete del reto."
        : "Este es el registro de trabajo sobre el paquete del reto. Para dejarlo en Notion use «Copiar para Notion» en cada ficha.", "", "info")));
}
