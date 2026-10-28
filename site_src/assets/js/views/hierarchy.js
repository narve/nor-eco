// Shared by the views that draw a Node tree as shapes (sunburst, icicle, rings): positive-value hierarchy,
// a readout line, and the claim / status marking for SVG shapes (hatch overlay, dotted outline).
import { h, s, fill, valueText, decimalsFor, isPreliminary, CLAIM_LABEL, STATUS_LABEL, colorVar } from "./common.js";
import { fmt } from "../core/format.js";

const kidsOf = (n) => [...(n.children ?? []), ...(n.other ? [n.other] : [])];

// d3 hierarchy of the nodes with a positive value; non-positive ones are returned in `skipped` and must be reported.
export function positiveHierarchy(node) {
  const skipped = [];
  const prune = (n) => {
    const ks = kidsOf(n).filter((k) => { if (k.value !== null && k.value > 0) return true; if (k.value !== null) skipped.push(k); return false; });
    return { node: n, children: ks.map(prune) };
  };
  const tree = prune(node);
  const root = window.d3.hierarchy(tree, (d) => (d.children.length ? d.children : null)).sum((d) => (d.children.length ? 0 : d.node.value));
  return { root, skipped };
}

// colour index of a hierarchy node: the index of its top-level ancestor; «Øvrig» is always grey
export function colorOf(d, topNode) {
  let top = d;
  while (top.depth > 1) top = top.parent;
  if (d.data.node === topNode.other || top.data.node === topNode.other) return colorVar(0, true);
  return colorVar(top.parent ? top.parent.children.indexOf(top) : 0);
}

export function hatchDefs(svg, id) {
  svg.append(s("defs", {}, s("pattern", { id, width: 6, height: 6, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" },
    s("rect", { width: 2.2, height: 6, fill: "var(--bg)", "fill-opacity": 0.55 }))));
}

// Attributes that mark a shape by claim level and status; `overlay` is the hatch shape to draw on top, or null.
export function marking(n, hatchId) {
  const hatched = n.claim_level === "utledet" || (isPreliminary(n.status) && n.claim_level !== "estimat");
  return { hatch: hatched ? `url(#${hatchId})` : null, dotted: n.claim_level === "estimat" };
}

export function readoutLine(n, rootValue, rootLabel, dec, extra = null) {
  return [h("strong", {}, n.label), ": ", h("span", { class: "num" }, valueText(n.value, n.unit, dec)),
    h("span", { class: "muted" }, ` (${fmt((100 * n.value) / rootValue, 1)} % av ${rootLabel})`), " ",
    h("span", { class: `claim claim-${n.claim_level}` }, CLAIM_LABEL[n.claim_level]),
    isPreliminary(n.status) ? h("span", { class: "muted" }, ` · ${STATUS_LABEL[n.status]}`) : null, extra];
}

export function skippedNote(skipped, dec) {
  return skipped.length ? h("p", { class: "muted small" }, `${skipped.length} post${skipped.length > 1 ? "er" : ""} med null eller negativ verdi vises ikke: `,
    skipped.map((n) => `${n.label} (${valueText(n.value, n.unit, dec)})`).join("; "), ".") : null;
}

export { kidsOf, fill, decimalsFor };
