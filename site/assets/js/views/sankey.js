// sankey: flows from sources (left) through one middle node to uses (right). The two sides only balance when the data
// says so: when they don't, the caller passes an explicit «difference» part on the short side, so the diagram always
// conserves value and the gap is visible as its own band. Link widths are values; every flow is also listed in a table.
// input: {left: [Node], right: [Node], mid: string, gap: {side: "left"|"right", label, value, claim_level} | null, unit}
import { put, h, s, fill, observeSize, colorVar, valueText, decimalsFor, CLAIM_LABEL } from "./common.js";
import { fmt } from "../core/format.js";

export function renderSankey(container, input) {
  const d3 = window.d3;
  container.replaceChildren();
  const L = input.left.filter((n) => n.value > 0), R = input.right.filter((n) => n.value > 0);
  const gap = input.gap && input.gap.value > 0 ? input.gap : null;
  const left = [...L, ...(gap?.side === "left" ? [gap] : [])], right = [...R, ...(gap?.side === "right" ? [gap] : [])];
  if (!left.length || !right.length) { put(container, h("p", { class: "muted" }, "Ingen strømmer å vise.")); return { destroy() {} }; }
  const dec = decimalsFor(input.unit, [...left, ...right].map((n) => n.value));
  const midValue = left.reduce((a, n) => a + n.value, 0);
  const plot = h("div", { class: "sk-plot" });
  const readout = h("div", { class: "readout", "aria-live": "polite" }, h("span", { class: "muted" }, "Trykk på en strøm eller en boks for detaljer."));
  const rows = [...left.map((n) => [n, "inn"]), ...right.map((n) => [n, "ut"])];
  put(container, plot, readout, h("p", { class: "muted small" }, gap
    ? `Sidene er ikke like store. Differansen på ${gap.side === "left" ? "inn" : "ut"}-siden er tegnet som egen strøm (${valueText(gap.value, input.unit, dec)}), så figuren går opp. Den er regnet ut av oss.`
    : "Sidene er like store."),
    h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Post"), h("th", { scope: "col" }, "Retning"), h("th", { scope: "col" }, input.unit))),
      h("tbody", {}, rows.map(([n, dir]) => h("tr", {}, h("th", { scope: "row" }, n.label), h("td", {}, dir === "inn" ? "inn" : "ut"), h("td", { class: "num" }, fmt(n.value, dec))))))));

  function draw(width) {
    const n = Math.max(left.length, right.length);
    const H = Math.max(280, Math.min(640, 34 * n + 60)), pad = width < 520 ? 4 : 8, labelRoom = width < 520 ? 0 : 0;
    const nodes = [...left.map((x, i) => ({ id: `l${i}`, src: x })), { id: "m", src: { label: input.mid, value: midValue, claim_level: "utledet" } }, ...right.map((x, i) => ({ id: `r${i}`, src: x }))];
    const links = [...left.map((x, i) => ({ source: `l${i}`, target: "m", value: x.value })), ...right.map((x, i) => ({ source: "m", target: `r${i}`, value: x.value }))];
    const lay = d3.sankey().nodeId((d) => d.id).nodeWidth(12).nodePadding(10).nodeAlign(d3.sankeyJustify).extent([[1, 4], [width - 1, H - 4]]);
    const g = lay({ nodes: nodes.map((d) => ({ ...d })), links: links.map((d) => ({ ...d })) });
    const svg = s("svg", { viewBox: `0 0 ${width} ${H}`, width, height: H, role: "group", "aria-label": `Strøm: ${input.mid}` });
    const color = (d) => (d.id === "m" ? "var(--total)" : d.src === gap ? "var(--other)" : colorVar(d.id.startsWith("l") ? +d.id.slice(1) : +d.id.slice(1) + left.length));
    for (const l of g.links) {
      const src = l.source.id === "m" ? l.target : l.source;
      const p = s("path", { d: d3.sankeyLinkHorizontal()(l), fill: "none", stroke: color(src), "stroke-opacity": 0.4, "stroke-width": Math.max(1, l.width), class: "sk-link", tabindex: 0, role: "button", "aria-label": `${src.src.label}: ${valueText(l.value, input.unit, dec)}` });
      const show = () => fill(readout, h("strong", {}, src.src.label), ": ", h("span", { class: "num" }, valueText(l.value, input.unit, dec)),
        h("span", { class: "muted" }, ` (${fmt((100 * l.value) / midValue, 1)} % av ${input.mid}) `), src.src.claim_level ? h("span", { class: `claim claim-${src.src.claim_level}` }, CLAIM_LABEL[src.src.claim_level]) : null);
      p.addEventListener("click", show); p.addEventListener("focus", show);
      svg.append(p);
    }
    for (const d of g.nodes) {
      svg.append(s("rect", { x: d.x0, y: d.y0, width: d.x1 - d.x0, height: Math.max(1, d.y1 - d.y0), fill: color(d), "fill-opacity": d.src.claim_level === "estimat" ? 0.4 : 1 }));
      if (d.id === "m") continue;
      const isLeft = d.id.startsWith("l"), hh = d.y1 - d.y0;
      if (hh < 12) continue;
      svg.append(s("text", { class: "sk-label", x: isLeft ? d.x1 + 5 : d.x0 - 5, y: (d.y0 + d.y1) / 2 + 4, "text-anchor": isLeft ? "start" : "end" }, document.createTextNode(d.src.label)));
    }
    plot.replaceChildren(svg);
  }
  const stop = observeSize(plot, draw);
  draw(plot.clientWidth || container.clientWidth || 320);
  return { destroy() { stop(); container.replaceChildren(); } };
}
