// sunburst: angle = value, rings = levels of the hierarchy (the node shown plus the levels below it). Angles are hard to
// compare, so the readout prints value and share, and the sorted list of the first level sits under the figure.
// A tap selects an arc, a second tap on a node with children opens it. «Øvrig» is always grey.
import { put, h, s, fill, observeSize } from "./common.js";
import { positiveHierarchy, colorOf, hatchDefs, marking, readoutLine, skippedNote, decimalsFor } from "./hierarchy.js";

export function renderSunburst(container, node, opts = {}) {
  const d3 = window.d3;
  const { onDrill = () => {}, canDrill = () => false } = opts;
  container.replaceChildren();
  const { root, skipped } = positiveHierarchy(node);
  if (!root.children) { put(container, h("p", { class: "muted" }, "Ingen undernivå som kan vises.")); return { destroy() {} }; }
  const dec = decimalsFor(node.unit, root.leaves().map((l) => l.data.node.value));
  const total = root.value;
  const plot = h("div", { class: "sb-plot" });
  const readout = h("div", { class: "readout", "aria-live": "polite" });
  put(container, plot, readout, skippedNote(skipped, dec), h("p", { class: "muted small" }, "Vinkler er vanskelige å sammenligne. Bytt til søyler for å lese tallene nøyaktig."));
  let sel = opts.selected ?? null;
  const hid = `hatch-${Math.random().toString(36).slice(2, 8)}`;

  const show = (d) => {
    const n = d.data.node;
    fill(readout, readoutLine(n, total, node.label, dec, canDrill(n) ? h("button", { type: "button", class: "btn", onclick: () => onDrill(n.path) }, "Åpne ›") : null));
  };
  const select = (d) => {
    const n = d.data.node;
    if (sel === n.path && canDrill(n)) { onDrill(n.path); return; }
    sel = n.path;
    plot.querySelectorAll("[data-path]").forEach((e) => e.setAttribute("aria-pressed", String(e.dataset.path === sel)));
    show(d);
  };

  function draw(width) {
    const size = Math.max(260, Math.min(560, width));
    const r = size / 2, levels = root.height;
    d3.partition().size([2 * Math.PI, 1])(root);
    const ring = r / (levels + 1);
    const arc = d3.arc().startAngle((d) => d.x0).endAngle((d) => d.x1).padAngle(0.004).innerRadius((d) => d.depth * ring).outerRadius((d) => (d.depth + 1) * ring - 1);
    const svg = s("svg", { viewBox: `${-r} ${-r} ${size} ${size}`, width: size, height: size, role: "group", "aria-label": `Solstråle: ${node.label}` });
    hatchDefs(svg, hid);
    for (const d of root.descendants().filter((x) => x.depth > 0)) {
      const n = d.data.node, m = marking(n, hid);
      const g = s("g", { class: `sb-arc${n === node.other ? " is-other" : ""}`, tabindex: 0, role: "button", "data-path": n.path, "aria-pressed": String(sel === n.path),
        "aria-label": `${n.label}: ${fmtShare(d.value, total)} prosent`, onclick: null });
      const path = arc(d);
      g.append(s("path", { d: path, fill: colorOf(d, node), "fill-opacity": m.dotted ? 0.3 : 1, stroke: m.dotted ? colorOf(d, node) : "var(--bg)", "stroke-dasharray": m.dotted ? "2 2" : null, "stroke-width": m.dotted ? 1.5 : 0.5 }));
      if (m.hatch) g.append(s("path", { d: path, fill: m.hatch }));
      g.addEventListener("click", () => select(d));
      g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(d); } });
      svg.append(g);
    }
    svg.append(s("text", { class: "sb-center", "text-anchor": "middle", y: 4 }, document.createTextNode(node.label.length > 22 ? `${node.label.slice(0, 21)}…` : node.label)));
    plot.replaceChildren(svg);
  }
  const fmtShare = (v, t) => (Math.round((1000 * v) / t) / 10).toString().replace(".", ",");
  const stop = observeSize(plot, draw);
  draw(plot.clientWidth || container.clientWidth || 320);
  const cur = root.descendants().find((d) => d.data.node.path === sel);
  if (cur) show(cur); else readout.append(h("span", { class: "muted" }, "Trykk på en del for detaljer."));
  return { destroy() { stop(); container.replaceChildren(); } };
}
