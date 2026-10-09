// Etapa 1 · Cargar: el paquete congelado, verificado en el momento y sin conexión.

import { h, vaciar, plural, soloFecha } from "../dom.js";
import { api } from "../api.js";
import { aviso } from "../piezas.js";

const NUMERO = new Intl.NumberFormat("es-PA");

function dato(valor, etiqueta, detalle) {
  return h("div", { class: "tarjeta dato" }, h("b", null, typeof valor === "number" ? NUMERO.format(valor) : valor),
    h("span", null, etiqueta), detalle ? h("small", null, detalle) : null);
}

/** Barras de un solo tono: comparan magnitudes, no identidades. Las mayores primero y el resto agrupado. */
function barras(titulo, pares, maximoFilas = 6) {
  const orden = Object.entries(pares).sort((a, b) => b[1] - a[1]);
  const filas = orden.slice(0, maximoFilas);
  const resto = orden.slice(maximoFilas).reduce((suma, [, n]) => suma + n, 0);
  if (resto) filas.push([`otros (${orden.length - maximoFilas})`, resto]);
  const mayor = Math.max(...filas.map(([, n]) => n), 1);
  return h("section", { class: "tarjeta" }, h("div", { class: "tarjeta__cuerpo" }, h("h2", null, titulo),
    h("div", { class: "barras" }, filas.map(([nombre, n]) => h("div", { class: "barras__fila" },
      h("span", null, nombre), h("span", { class: "barras__pista" }, h("i", { estilo: { width: `${(n / mayor) * 100}%` } })),
      h("span", null, NUMERO.format(n)))))));
}

export async function datos(raiz) {
  const d = await api.datos();
  if (!d.disponible) {
    vaciar(raiz, h("div", { class: "tarjeta vacio" }, h("strong", null, "No se encontró el paquete de datos"), "Falta la carpeta datos/ con su manifest."));
    return;
  }
  const n = d.reporte.noticias, ind = d.reporte.indicadores, sis = d.reporte.eventos;
  const excluidas = d.excluidos.por_decision_del_equipo || [];

  vaciar(raiz,
    h("div", { class: "encabezado" }, h("div", null,
      h("div", { class: "sobretitulo" }, "Etapa 1 · Cargar"),
      h("h1", null, "Paquete de datos"),
      h("p", null, `${d.version} · corte `, h("strong", null, d.fecha_corte_panama), ". Se lee del disco, se valida y se compara con su manifest cada vez que se abre esta página: no usa internet."))),

    h("div", { class: "avisos", estilo: { "margin-bottom": "1.1rem" } },
      d.integro
        ? aviso(`Paquete íntegro: los ${d.archivos.length} archivos coinciden con la huella SHA-256 registrada en el manifest.`, "bien", "escudo")
        : d.incidencias.map((incidencia) => aviso(incidencia, "critico", "alerta")),
      d.alimenta_la_bandeja ? null
        : aviso("La bandeja está mostrando los datos de ejemplo sintéticos: este paquete todavía no tiene una corrida del núcleo de IA (backend/artefactos/eventos.json).", "alerta", "alerta")),

    h("div", { class: "rejilla rejilla--cuatro" },
      dato(n.validas, "noticias válidas", `${n.rechazadas} apartadas por validación`),
      dato(n.de_tvn, "de TVN", "mínimo del reto: 20"),
      dato(n.medios_distintos, "medios distintos"),
      dato(d.duplicados_fusionados ?? "—", "duplicados fusionados", "misma URL, al extraer"),
      dato(n.recirculadas, "marcadas como antiguas", "no se presentan como hechos nuevos"),
      dato(n.sin_fecha_de_publicacion, "sin fecha de publicación", "solo se conoce la detección"),
      dato(ind.con_valor, "datos del Banco Mundial", `${ind.sin_valor} sin valor: se conservan vacíos, nunca cero`),
      dato(sis.validas, "sismos de USGS", `magnitud ${sis.magnitud.minimo} a ${sis.magnitud.maximo}`)),

    h("h2", { class: "sobretitulo", estilo: { margin: "1.6rem 0 .6rem" } }, "Archivos y huellas"),
    h("div", { class: "tarjeta" }, h("div", { class: "tabla-envoltura" }, h("table", { class: "tabla" },
      h("thead", null, h("tr", null, h("th", null, "Archivo"), h("th", { class: "num" }, "Registros"), h("th", { class: "num" }, "Bytes"),
        h("th", null, "SHA-256"), h("th", null, "Condiciones de uso"))),
      h("tbody", null, d.archivos.map((a) => h("tr", null,
        h("td", { class: "mono" }, a.archivo), h("td", { class: "num" }, NUMERO.format(a.registros)), h("td", { class: "num" }, NUMERO.format(a.bytes)),
        h("td", null, h("span", { class: "huella", title: a.sha256 }, `${a.sha256.slice(0, 16)}…`)),
        h("td", { class: "secundario" }, a.licencia_condiciones))))))),

    h("h2", { class: "sobretitulo", estilo: { margin: "1.6rem 0 .6rem" } }, "Composición de las noticias"),
    h("div", { class: "columnas" },
      barras("Por origen", n.por_origen),
      barras("Por idioma", n.por_idioma),
      barras("Por consulta de extracción", n.por_tema_de_consulta)),
    h("p", { class: "tenue", estilo: { "margin-top": ".6rem", "font-size": ".86rem" } },
      `Cobertura de detección: ${soloFecha(n.cobertura_deteccion.minimo)} a ${soloFecha(n.cobertura_deteccion.maximo)}. `,
      d.excluidas_idioma !== null ? `El panel muestra solo español e inglés: ${plural(d.excluidas_idioma, "nota queda", "notas quedan")} fuera por idioma, registradas con su motivo.` : ""),

    h("h2", { class: "sobretitulo", estilo: { margin: "1.6rem 0 .6rem" } }, "Fuentes y condiciones"),
    h("div", { class: "columnas" }, d.fuentes.map((f) => h("section", { class: "tarjeta" }, h("div", { class: "tarjeta__cuerpo" },
      h("h2", null, f.fuente),
      h("p", null, f.cobertura),
      h("p", { class: "secundario", estilo: { "margin-top": ".5rem", "font-size": ".88rem" } }, f.licencia_condiciones),
      h("p", { class: "tenue mono", estilo: { "margin-top": ".5rem" } }, f.campos.join(" · ")))))),

    h("h2", { class: "sobretitulo", estilo: { margin: "1.6rem 0 .6rem" } }, "Lo que no entró, a la vista"),
    h("div", { class: "columnas" },
      h("section", { class: "tarjeta" }, h("div", { class: "tarjeta__cuerpo" },
        h("h2", null, "Descargas que fallaron", h("span", { class: "conteo" }, `· ${d.descargas_fallidas.length}`)),
        d.descargas_fallidas.length
          ? h("ul", { class: "lista-simple lista-simple--puntos" }, d.descargas_fallidas.map((c) =>
            h("li", null, h("span", { class: "mono" }, c.archivo), h("span", { class: "tenue" }, ` · ${c.fuente}${c.tema ? ` · ${c.tema}` : ""}`))))
          : h("p", { class: "secundario" }, "Ninguna."),
        h("p", { class: "tenue", estilo: { "margin-top": ".6rem", "font-size": ".84rem" } }, "La fuente limitó las consultas durante la extracción. Quedan registradas como pendientes; no se rellenan."))),
      h("section", { class: "tarjeta" }, h("div", { class: "tarjeta__cuerpo" },
        h("h2", null, "Retiradas por decisión del equipo", h("span", { class: "conteo" }, `· ${excluidas.length}`)),
        excluidas.length ? h("ul", { class: "lista-simple lista-simple--puntos" }, excluidas.map((e) =>
          h("li", null, h("span", { class: "mono" }, e.id_noticia), ` ${e.motivo}`))) : h("p", { class: "secundario" }, "Ninguna."),
        h("h2", { estilo: { "margin-top": "1.1rem" } }, "Apartadas por validación"),
        h("p", { class: "secundario" }, `${d.rechazados.noticias} noticias · ${d.rechazados.indicadores} indicadores · ${d.rechazados.eventos} sismos. Una fila defectuosa se aparta con su motivo y la carga continúa.`)))),

    h("details", { class: "tarjeta", estilo: { "margin-top": "1.1rem" } },
      h("summary", { class: "tarjeta__cuerpo", estilo: { cursor: "pointer", "font-weight": "650" } }, `Transformaciones aplicadas (${d.transformaciones.length})`),
      h("ul", { class: "lista-simple lista-simple--puntos", estilo: { padding: "0 1.25rem 1.2rem" } }, d.transformaciones.map((t) => h("li", null, t)))));
}
