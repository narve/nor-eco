// waffle: the whole population as a grid of equal squares (20 x 20 = 400, each 0.25 %), one colour per group.
// Square counts use the largest-remainder method, so they always sum to exactly 400; the legend prints the
// exact numbers and shares, and a group too small for one square is still listed (never dropped).
// A group that combines two statuses («sysselsatt og mottar uføretrygd») is drawn with striped squares:
// the colour of its main status and the colour of the second. Hovering or focusing a legend row isolates it.
import { h, valueText, isPreliminary, CLAIM_LABEL } from "./common.js";
import { fmt } from "../core/format.js";

export const CELLS = 400;

// Largest remainder: floor each share of `cells`, then give the leftover squares to the largest fractional parts.
export function allocate(values, cells = CELLS) {
  const total = values.reduce((a, v) => a + v, 0);
  if (total <= 0) return values.map(() => 0);
  const exact = values.map((v) => (v / total) * cells);
  const out = exact.map(Math.floor);
  let left = cells - out.reduce((a, v) => a + v, 0);
  exact.map((e, i) => [e - Math.floor(e), i]).sort((a, b) => b[0] - a[0] || a[1] - b[1]).forEach(([, i]) => { if (left > 0) { out[i]++; left--; } });
  return out;
}

function leavesOf(node) {
  const kids = [...(node.children ?? []), ...(node.other ? [node.other] : [])];
  return kids.length ? kids.flatMap(leavesOf) : [node];
}

// groups: [{label, codes: [leaf codes], color: 1..8 | "other", stripe?: 1..8 | "other"}] (codes match the end of the leaf path)
export function renderWaffle(container, node, opts = {}) {
  const { groups: cfgGroups, cells = CELLS } = opts;
  container.replaceChildren();
  const leaves = leavesOf(node).filter((l) => l.value !== null);
  const codeOf = (l) => l.path.split("/").pop().split(":").slice(1).join(":");
  const defs = cfgGroups ?? leaves.map((l, i) => ({ label: l.label, codes: [codeOf(l)], color: (i % 8) + 1 }));
  const groups = defs.map((g) => {
    const members = leaves.filter((l) => g.codes.includes(codeOf(l)));
    return { ...g, value: members.reduce((a, l) => a + l.value, 0), claim: members.some((l) => l.claim_level !== "offisiell") ? "utledet" : "offisiell", prelim: members.some((l) => isPreliminary(l.status)) };
  });
  const covered = new Set(defs.flatMap((g) => g.codes));
  const missing = leaves.filter((l) => !covered.has(codeOf(l)));
  if (missing.length) throw new Error(`waffle groups do not cover: ${missing.map(codeOf).join(", ")}`);
  const total = groups.reduce((a, g) => a + g.value, 0);
  const counts = allocate(groups.map((g) => g.value), cells);
  const colorOf = (c) => (c === "other" ? "var(--other)" : `var(--c${c})`);
  const swatch = (g) => (g.stripe ? `repeating-linear-gradient(45deg, ${colorOf(g.color)} 0 3px, ${colorOf(g.stripe)} 3px 6px)` : colorOf(g.color));

  const grid = h("div", { class: "wf-grid", role: "img", style: `--cols:${Math.round(Math.sqrt(cells))}`,
    "aria-label": `${node.label}: ${groups.filter((g) => g.value).map((g) => `${g.label} ${fmt((100 * g.value) / total, 1)} prosent`).join("; ")}` });
  groups.forEach((g, gi) => { for (let i = 0; i < counts[gi]; i++) grid.append(h("span", { class: "wf-cell", "data-g": gi, style: `background:${swatch(g)}` })); });

  const focus = (gi) => grid.querySelectorAll(".wf-cell").forEach((c) => c.classList.toggle("is-dim", gi !== null && +c.dataset.g !== gi));
  const legend = h("ul", { class: "wf-legend", role: "list" }, groups.map((g, gi) => h("li", {},
    h("button", { type: "button", class: "wf-key", onmouseenter: () => focus(gi), onmouseleave: () => focus(null), onfocus: () => focus(gi), onblur: () => focus(null) },
      h("span", { class: "wf-sw", style: `background:${swatch(g)}` }),
      h("span", { class: "wf-name" }, g.label, g.stripe ? h("span", { class: "muted small" }, " (to statuser)") : null),
      h("span", { class: "num wf-num" }, valueText(g.value, node.unit, 0)),
      h("span", { class: "num wf-pct" }, `${fmt((100 * g.value) / total, 1)} %`),
      g.value && counts[groups.indexOf(g)] === 0 ? h("span", { class: "muted small" }, " under én rute") : null))));
  const per = total / cells;
  container.append(grid,
    h("p", { class: "muted small" }, `Hver rute er ${fmt(100 / cells, 2)} % av ${node.label.toLowerCase()}, om lag ${fmt(Math.round(per), 0)} ${node.unit}. Antall ruter er avrundet; de nøyaktige tallene står i listen.`),
    legend);
  return { destroy() { container.replaceChildren(); }, counts, groups };
}
