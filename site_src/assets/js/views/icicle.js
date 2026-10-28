// icicle: like a sunburst, but straight: one row per level, width = value. Widths are easier to compare than angles,
// and labels fit better. A tap selects a block, a second tap on a node with children opens it.
import { put, h, s, fill, observeSize } from "./common.js";
import { positiveHierarchy, colorOf, hatchDefs, marking, readoutLine, skippedNote, decimalsFor } from "./hierarchy.js";

export function renderIcicle(container, node, opts = {}) {
  const d3 = window.d3;
  const { onDrill = () => {}, canDrill = () => false } = opts;
  container.replaceChildren();
  const { root, skipped } = positiveHierarchy(node);
  if (!root.children) { put(container, h("p", { class: "muted" }, "Ingen undernivå som kan vises.")); return { destroy() {} }; }
  const dec = decimalsFor(node.unit, root.leaves().map((l) => l.data.node.value));
  const total = root.value;
  const plot = h("div", { class: "ic-plot" });
  const readout = h("div", { class: "readout", "aria-live": "polite" });
  put(container, plot, readout, skippedNote(skipped, dec));
  let sel = opts.selected ?? null;
  const hid = `hatch-${Math.random().toString(36).slice(2, 8)}`;
  const show = (d) => { const n = d.data.node; fill(readout, readoutLine(n, total, node.label, dec, canDrill(n) ? h("button", { type: "button", class: "btn", onclick: () => onDrill(n.path) }, "Åpne ›") : null)); };
  const select = (d) => {
    const n = d.data.node;
    if (sel === n.path && canDrill(n)) { onDrill(n.path); return; }
    sel = n.path;
    plot.querySelectorAll("[data-path]").forEach((e) => e.setAttribute("aria-pressed", String(e.dataset.path === sel)));
    show(d);
  };
  function draw(width) {
    const row = 44, levels = root.height + 1, height = levels * row;
    d3.partition().size([width, height]).padding(0)(root);
    const svg = s("svg", { viewBox: `0 0 ${width} ${height}`, width, height, role: "group", "aria-label": `Istapp: ${node.label}` });
    hatchDefs(svg, hid);
    for (const d of root.descendants()) {
      const n = d.data.node, m = marking(n, hid), w = d.x1 - d.x0 - 1, c = d.depth === 0 ? "var(--total)" : colorOf(d, node);
      const g = s("g", { class: `ic-block${n === node.other ? " is-other" : ""}`, tabindex: 0, role: "button", "data-path": n.path, "aria-pressed": String(sel === n.path), "aria-label": `${n.label}` });
      g.append(s("rect", { x: d.x0, y: d.y0, width: Math.max(w, 0), height: row - 2, fill: c, "fill-opacity": m.dotted ? 0.3 : 1, stroke: m.dotted ? c : "none", "stroke-dasharray": m.dotted ? "2 2" : null }));
      if (m.hatch) g.append(s("rect", { x: d.x0, y: d.y0, width: Math.max(w, 0), height: row - 2, fill: m.hatch }));
      if (w > 46) {
        const room = Math.floor((w - 8) / 6.6);
        const text = n.label.length > room ? `${n.label.slice(0, Math.max(room - 1, 1))}…` : n.label;
        g.append(s("text", { class: "ic-label", x: d.x0 + 5, y: d.y0 + 24 }, document.createTextNode(text)));
      }
      g.addEventListener("click", () => select(d));
      g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(d); } });
      svg.append(g);
    }
    plot.replaceChildren(svg);
  }
  const stop = observeSize(plot, draw);
  draw(plot.clientWidth || container.clientWidth || 320);
  const cur = root.descendants().find((d) => d.data.node.path === sel);
  if (cur) show(cur); else readout.append(h("span", { class: "muted" }, "Trykk på en blokk for detaljer."));
  return { destroy() { stop(); container.replaceChildren(); } };
}
