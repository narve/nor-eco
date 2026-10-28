// marimekko: two dimensions in one figure. Column width = the share of the first split, the stack inside a column =
// the second split of that column (each column adds up to 100 %). Column totals and every segment's value are listed
// below, so nothing has to be read from the areas. `cols` = [{node, parts: Node}] built by the controller.
import { put, h, s, fill, observeSize, colorVar, valueText, decimalsFor, CLAIM_LABEL } from "./common.js";
import { kidsOf } from "./hierarchy.js";
import { fmt } from "../core/format.js";

export function renderMarimekko(container, cols, opts = {}) {
  const { dimLabels = ["", ""], unit = "" } = opts;
  container.replaceChildren();
  const cs = cols.filter((c) => c.node.value > 0 && kidsOf(c.parts).some((k) => k.value > 0));
  if (!cs.length) { put(container, h("p", { class: "muted" }, "Datasettet har ikke to dimensjoner å dele etter her.")); return { destroy() {} }; }
  const total = cs.reduce((a, c) => a + c.node.value, 0);
  const segLabels = [];
  for (const c of cs) for (const k of kidsOf(c.parts)) { const code = k.path.split("/").pop(); if (!segLabels.find((x) => x.code === code)) segLabels.push({ code, label: k.label, other: false }); }
  const idx = (k) => segLabels.findIndex((x) => x.code === k.path.split("/").pop());
  const dec = decimalsFor(unit, cs.map((c) => c.node.value));
  const plot = h("div", { class: "mk-plot" });
  const readout = h("div", { class: "readout", "aria-live": "polite" }, h("span", { class: "muted" }, "Trykk på en del for detaljer."));
  const legend = h("ul", { class: "mk-legend", role: "list" }, segLabels.map((x, i) => h("li", {}, h("span", { class: "wf-sw", style: `background:${colorVar(i)}` }), x.label)));
  const table = h("table", {}, h("thead", {}, h("tr", {}, h("th", { scope: "col" }, `${dimLabels[0]}`), h("th", { scope: "col" }, "Sum"), segLabels.map((x) => h("th", { scope: "col" }, x.label)))),
    h("tbody", {}, cs.map((c) => h("tr", {}, h("th", { scope: "row" }, c.node.label), h("td", { class: "num" }, fmt(c.node.value, dec)),
      segLabels.map((x) => { const k = kidsOf(c.parts).find((q) => q.path.split("/").pop() === x.code); return h("td", { class: "num" }, k ? fmt(k.value, dec) : "–"); })))));
  put(container, h("p", { class: "muted small" }, `Bredde: ${dimLabels[0]}. Høyde: ${dimLabels[1]}.`), plot, readout, legend, h("div", { class: "table-wrap" }, table));

  function draw(width) {
    const H = Math.max(240, Math.min(440, Math.round(width * 0.6))), gap = 2, foot = 20;
    const usable = width - gap * (cs.length - 1);
    const svg = s("svg", { viewBox: `0 0 ${width} ${H + foot}`, width, height: H + foot, role: "group", "aria-label": `Marimekko: ${dimLabels[0]} og ${dimLabels[1]}` });
    let x = 0;
    for (const c of cs) {
      const w = (c.node.value / total) * usable;
      let y = 0;
      const ks = kidsOf(c.parts).filter((k) => k.value > 0), sum = ks.reduce((a, k) => a + k.value, 0);
      for (const k of ks) {
        const hh = (k.value / sum) * H, dotted = k.claim_level === "estimat";
        const g = s("g", { tabindex: 0, role: "button", class: "mk-seg", "aria-label": `${c.node.label}, ${k.label}: ${valueText(k.value, k.unit, dec)}` });
        g.append(s("rect", { x, y, width: Math.max(w - 0, 0), height: Math.max(hh - 1, 0), fill: colorVar(idx(k)), "fill-opacity": dotted ? 0.3 : 1, stroke: dotted ? colorVar(idx(k)) : "var(--bg)", "stroke-dasharray": dotted ? "2 2" : null }));
        const show = () => fill(readout, h("strong", {}, `${c.node.label}, ${k.label}`), ": ", h("span", { class: "num" }, valueText(k.value, k.unit, dec)),
          h("span", { class: "muted" }, ` (${fmt((100 * k.value) / sum, 1)} % av ${c.node.label}, ${fmt((100 * k.value) / total, 1)} % av alt) `), h("span", { class: `claim claim-${k.claim_level}` }, CLAIM_LABEL[k.claim_level]));
        g.addEventListener("click", show); g.addEventListener("focus", show);
        svg.append(g);
        if (w > 60 && hh > 20) svg.append(s("text", { class: "mk-label", x: x + 5, y: y + 15 }, document.createTextNode(`${fmt((100 * k.value) / sum, 0)} %`)));
        y += hh;
      }
      if (w > 30) {
        const room = Math.floor((w - 6) / 6.4), t = c.node.label.length > room ? `${c.node.label.slice(0, Math.max(room - 1, 1))}…` : c.node.label;
        const el = s("text", { class: "mk-col", x: x + 3, y: H + 14 }, document.createTextNode(t));
        el.append(s("title", {}, document.createTextNode(`${c.node.label}: ${fmt(c.node.value, dec)}`)));
        svg.append(el);
      }
      x += w + gap;
    }
    plot.replaceChildren(svg);
  }
  const stop = observeSize(plot, draw);
  draw(plot.clientWidth || container.clientWidth || 320);
  return { destroy() { stop(); container.replaceChildren(); } };
}
