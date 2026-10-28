// euler-upset: overlaps between groups, drawn as an UpSet plot (a bar per combination, dots below for which groups are
// in it). It is built from the leaves that declare `overlap` (a leaf that is two statuses at once). Each person is in
// exactly one combination, so the bars add up: no area has to be estimated, which is why this is not a Venn diagram.
// Combinations: every leaf with `overlap`, and the single groups that take part in an overlap.
import { put, h, s, fill, observeSize, valueText, decimalsFor, CLAIM_LABEL } from "./common.js";
import { fmt } from "../core/format.js";

function collect(node, parent, out) {
  const kids = [...(node.children ?? []), ...(node.other ? [node.other] : [])];
  if (!kids.length) out.push({ leaf: node, parent });
  for (const k of kids) collect(k, node, out);
  return out;
}
const codeOf = (n) => n.path.split("/").pop().split(":").slice(1).join(":");

export function renderUpset(container, node) {
  container.replaceChildren();
  const leaves = collect(node, null, []).filter((l) => l.leaf.value !== null);
  const overlapping = leaves.filter((l) => l.leaf.overlap?.length);
  if (!overlapping.length) { put(container, h("p", { class: "muted" }, "Dette datasettet har ingen grupper som overlapper.")); return { destroy() {} }; }
  const byCode = new Map(leaves.map((l) => [codeOf(l.leaf), l]));
  // An overlap list with several codes means «one of these» (for example AFP or old-age pension), so they form one group.
  const groupOf = (codes) => {
    const members = codes.map((c) => byCode.get(c)?.leaf).filter(Boolean);
    const rank = { offisiell: 0, utledet: 1, estimat: 2 };
    return { label: members.map((m) => m.label).join(" eller "), key: codes.join("+"),
      node: { ...members[0], label: members.map((m) => m.label).join(" eller "), value: members.reduce((a, m) => a + m.value, 0),
              claim_level: members.reduce((w, m) => (rank[m.claim_level] > rank[w] ? m.claim_level : w), "offisiell"), path: codes.join("+") } };
  };
  const combos = [], setsOf = new Set(), singles = new Map();
  for (const l of overlapping) {
    const g = groupOf(l.leaf.overlap);
    const sets = [l.parent.label, g.label];
    combos.push({ sets, node: l.leaf, label: l.leaf.label });
    sets.forEach((x) => setsOf.add(x));
    singles.set(g.key, { sets: [g.label], node: g.node, label: g.label });
    for (const sib of collect(l.parent, null, []).map((x) => x.leaf)) if (!sib.overlap?.length) singles.set(sib.path, { sets: [l.parent.label], node: sib, label: sib.label });
  }
  combos.push(...singles.values());
  combos.sort((a, b) => b.node.value - a.node.value);
  const sets = [...setsOf];
  const dec = decimalsFor(node.unit, combos.map((c) => c.node.value));
  const maxV = Math.max(...combos.map((c) => c.node.value));
  const plot = h("div", { class: "up-plot" });
  const readout = h("div", { class: "readout", "aria-live": "polite" }, h("span", { class: "muted" }, "Trykk på en søyle for detaljer."));
  put(container, plot, readout, h("p", { class: "muted small" }, "Hver person er med i nøyaktig én kombinasjon, så søylene overlapper ikke. Bare grupper som inngår i en overlapp er med; resten av befolkningen er utelatt her."),
    h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Kombinasjon"), h("th", { scope: "col" }, "Grupper"), h("th", { scope: "col" }, node.unit))),
      h("tbody", {}, combos.map((c) => h("tr", {}, h("th", { scope: "row" }, c.label), h("td", {}, c.sets.join(" + ")), h("td", { class: "num" }, fmt(c.node.value, dec))))))));

  function draw(width) {
    const L = width > 520 ? 210 : 120, colW = Math.max(26, Math.min(64, Math.floor((width - L - 4) / combos.length))), W = L + colW * combos.length;
    const barH = 160, row = 22, H = barH + 28 + sets.length * row;
    const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "group", "aria-label": "Overlapp mellom grupper" });
    const fit = (t) => { const room = Math.floor((L - 14) / 6.4); return t.length > room ? `${t.slice(0, room - 1)}…` : t; };
    sets.forEach((set, j) => {
      const t = s("text", { class: "up-set", x: L - 8, y: 20 + barH + 18 + j * row, "text-anchor": "end" }, document.createTextNode(fit(set)));
      t.append(s("title", {}, document.createTextNode(set)));
      svg.append(t);
    });
    combos.forEach((c, i) => {
      const x = L + i * colW + colW / 2, bh = Math.max(2, (c.node.value / maxV) * barH), dotted = c.node.claim_level === "estimat";
      const g = s("g", { tabindex: 0, role: "button", class: "up-col", "aria-label": `${c.sets.join(" og ")}: ${valueText(c.node.value, c.node.unit, dec)}` });
      g.append(s("rect", { x: x - colW * 0.3, y: 20 + barH - bh, width: colW * 0.6, height: bh, fill: c.sets.length > 1 ? "var(--c2)" : "var(--c1)", "fill-opacity": dotted ? 0.3 : 1 }));
      g.append(s("text", { class: "up-val", x, y: 16 + barH - bh, "text-anchor": "middle" }, document.createTextNode(fmt(c.node.value, dec))));
      sets.forEach((set, j) => g.append(s("circle", { cx: x, cy: 20 + barH + 14 + j * row, r: 5, fill: c.sets.includes(set) ? "var(--text)" : "var(--line)" })));
      const ins = sets.map((x2, j) => (c.sets.includes(x2) ? j : -1)).filter((j) => j >= 0);
      if (ins.length > 1) g.append(s("line", { x1: x, x2: x, y1: 20 + barH + 14 + ins[0] * row, y2: 20 + barH + 14 + ins[ins.length - 1] * row, stroke: "var(--text)", "stroke-width": 2 }));
      const show = () => fill(readout, h("strong", {}, c.label), ": ", h("span", { class: "num" }, valueText(c.node.value, c.node.unit, dec)), " ", h("span", { class: "muted" }, `(${c.sets.join(" + ")}) `),
        h("span", { class: `claim claim-${c.node.claim_level}` }, CLAIM_LABEL[c.node.claim_level]));
      g.addEventListener("click", show); g.addEventListener("focus", show);
      svg.append(g);
    });
    plot.replaceChildren(h("div", { class: "up-scroll" }, svg));
  }
  const stop = observeSize(plot, draw);
  draw(plot.clientWidth || container.clientWidth || 320);
  return { destroy() { stop(); container.replaceChildren(); } };
}
