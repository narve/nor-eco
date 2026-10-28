// rings: concentric circles, area proportional to the running total of the parts. The outermost circle is the sum of
// everything shown, each circle inside it leaves out the last part. The parts are listed with their own value, so
// nothing has to be read from the areas. Parts keep the order of the data (the order is the order of the rings).
import { put, h, s, fill, observeSize, colorVar, valueText, decimalsFor, CLAIM_LABEL } from "./common.js";
import { kidsOf } from "./hierarchy.js";
import { fmt } from "../core/format.js";

export function renderRings(container, node, opts = {}) {
  const { onDrill = () => {}, canDrill = () => false } = opts;
  container.replaceChildren();
  const all = kidsOf(node);
  const parts = all.filter((n) => n.value !== null && n.value > 0);
  const skipped = all.filter((n) => n.value !== null && n.value <= 0);
  if (!parts.length) { put(container, h("p", { class: "muted" }, "Ingen undernivå som kan vises som ringer.")); return { destroy() {} }; }
  const dec = decimalsFor(node.unit, parts.map((n) => n.value));
  let run = 0;
  const cum = parts.map((n) => { run += n.value; return run; });
  const total = run;
  const plot = h("div", { class: "rg-plot" });
  const list = h("ol", { class: "rg-list" }, parts.map((n, i) => h("li", { class: `rg-item rg-${n.claim_level}` },
    h("span", { class: "rg-sw", style: `background:${colorVar(i, n === node.other)}` }),
    h("span", { class: "rg-name" }, n.label, canDrill(n) ? h("button", { type: "button", class: "btn", onclick: () => onDrill(n.path) }, "Åpne ›") : null),
    h("span", { class: "num rg-val" }, valueText(n.value, n.unit, dec)),
    h("span", { class: "muted rg-cum" }, `til og med denne: ${valueText(cum[i], node.unit, dec)}`),
    h("span", { class: `claim claim-${n.claim_level}` }, CLAIM_LABEL[n.claim_level]))));
  put(container, plot, list,
    h("p", { class: "muted small" }, `Arealet av hver ring er summen av delene til og med den ringen; ytterste ring er alt: ${valueText(total, node.unit, dec)}. Rekkefølgen er rekkefølgen i dataene.`),
    skipped.length ? h("p", { class: "muted small" }, "Ikke tegnet (null eller negativ): ", skipped.map((n) => n.label).join("; "), ".") : null);

  function draw(width) {
    const size = Math.max(240, Math.min(440, width)), R = size / 2 - 2;
    const svg = s("svg", { viewBox: `0 0 ${size} ${size}`, width: size, height: size, role: "img", "aria-label": `Ringer: ${node.label}, ${parts.map((n) => `${n.label} ${fmt((100 * n.value) / total, 1)} prosent`).join("; ")}` });
    // largest circle first so smaller ones sit on top, all sharing the bottom edge so the nesting reads as containment
    for (let i = parts.length - 1; i >= 0; i--) {
      const r = R * Math.sqrt(cum[i] / total), n = parts[i], dotted = n.claim_level === "estimat";
      svg.append(s("circle", { cx: size / 2, cy: size - 2 - r, r, fill: colorVar(i, n === node.other), "fill-opacity": dotted ? 0.3 : 0.85, stroke: "var(--bg)", "stroke-width": 1.5, "stroke-dasharray": dotted ? "2 2" : null }));
    }
    plot.replaceChildren(svg);
  }
  const stop = observeSize(plot, draw);
  draw(plot.clientWidth || container.clientWidth || 320);
  return { destroy() { stop(); container.replaceChildren(); } };
}
