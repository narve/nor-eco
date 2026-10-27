// treemap: area = value, squarified tiles for the children of the current node. Honest limits are built in:
// areas are hard to compare, so every tile with room prints its value and share, and a sorted list of the same
// numbers sits in the readout; negative values cannot be drawn as area and are reported, never silently dropped;
// «Øvrig / ikke fordelt» is always grey. A tap selects a tile, a second tap drills.
import { h, fill, observeSize, colorVar, isPreliminary, valueText, decimalsFor, CLAIM_LABEL, STATUS_LABEL } from "./common.js";
import { fmt } from "../core/format.js";

export function renderTreemap(container, node, opts = {}) {
  const d3 = window.d3;
  const { onDrill = () => {}, canDrill = () => false } = opts;
  container.replaceChildren();
  const all = [...(node.children ?? []), ...(node.other ? [node.other] : [])];
  const drawable = all.filter((n) => n.value !== null && n.value > 0);
  const skipped = all.filter((n) => n.value !== null && n.value <= 0);
  if (!drawable.length) { container.append(h("p", { class: "muted" }, "Ingen undernivå som kan vises som flater.")); return { destroy() {} }; }
  const dec = decimalsFor(node.unit, drawable.map((n) => n.value));
  const total = drawable.reduce((a, n) => a + n.value, 0);
  let sel = opts.selected ?? null;

  const plot = h("div", { class: "tm-plot", role: "group", "aria-label": `Flisekart: ${node.label}` });
  const readout = h("div", { class: "readout", "aria-live": "polite" });
  const notes = [];
  if (skipped.length) {
    notes.push(h("p", { class: "muted small" }, `${skipped.length} post${skipped.length > 1 ? "er" : ""} med null eller negativ verdi vises ikke som flate: `,
      skipped.map((n) => `${n.label} (${valueText(n.value, n.unit, dec)})`).join("; "), "."));
  }
  container.append(plot, readout, ...notes, h("p", { class: "muted small" }, "Flatene er vanskelige å sammenligne når forskjellen er liten. Bytt til søyler for å lese tallene nøyaktig."));

  const show = (n) => {
    fill(readout, 
      h("strong", {}, n.label), ": ", h("span", { class: "num" }, valueText(n.value, n.unit, dec)),
      h("span", { class: "muted" }, ` (${fmt((100 * n.value) / total, 1)} % av ${node.label})`), " ",
      h("span", { class: `claim claim-${n.claim_level}` }, CLAIM_LABEL[n.claim_level]),
      isPreliminary(n.status) ? h("span", { class: "muted" }, ` · ${STATUS_LABEL[n.status]}`) : null,
      canDrill(n) ? h("button", { type: "button", class: "btn", onclick: () => onDrill(n.path) }, "Åpne ›") : null);
  };

  function draw(width) {
    const height = Math.max(260, Math.min(520, Math.round(width * 0.62)));
    plot.style.height = `${height}px`;
    const root = d3.hierarchy({ children: drawable }).sum((d) => d.value ?? 0).sort((a, b) => b.value - a.value);
    d3.treemap().size([width, height]).paddingInner(2).tile(d3.treemapSquarify.ratio(1.6))(root);
    plot.replaceChildren(...root.leaves().map((leaf) => {
      const n = leaf.data, w = leaf.x1 - leaf.x0, hh = leaf.y1 - leaf.y0;
      const idx = drawable.indexOf(n), other = n === node.other;
      const roomy = w > 70 && hh > 38, medium = w > 40 && hh > 22;
      return h("button", {
        type: "button",
        class: `tm-tile claim-${n.claim_level}${isPreliminary(n.status) ? " is-prelim" : ""}${other ? " is-other" : ""}`,
        style: `left:${leaf.x0}px;top:${leaf.y0}px;width:${w}px;height:${hh}px;--bar:${colorVar(idx, other)}`,
        "data-path": n.path,
        "aria-pressed": String(sel === n.path),
        "aria-label": `${n.label}: ${valueText(n.value, n.unit, dec)}, ${fmt((100 * n.value) / total, 1)} prosent.${canDrill(n) ? " Trykk to ganger for å åpne." : ""}`,
        onclick: () => {
          if (sel === n.path && canDrill(n)) { onDrill(n.path); return; }
          sel = n.path;
          plot.querySelectorAll(".tm-tile").forEach((t) => t.setAttribute("aria-pressed", String(t.dataset.path === sel)));
          show(n);
        },
      }, medium ? h("span", { class: "tm-label" }, n.label) : null,
         roomy ? h("span", { class: "tm-val num" }, `${fmt(n.value, dec)} · ${fmt((100 * n.value) / total, 0)} %`) : null);
    }));
  }

  const stop = observeSize(plot, draw);
  draw(plot.clientWidth || container.clientWidth || 320);
  const cur = drawable.find((n) => n.path === sel);
  if (cur) show(cur); else readout.append(h("span", { class: "muted" }, "Trykk på en flate for detaljer."));
  return { destroy() { stop(); container.replaceChildren(); } };
}
