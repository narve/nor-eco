// slope: the same quantity in two years, one line per series on one common scale that starts at zero.
// Years are chosen by the reader (both pickers are exposed); labels at both ends are nudged apart so none
// overlap; a line that touches a preliminary value is dashed; «Øvrig» is grey.
import { h, s, observeSize, colorVar, isPreliminary, valueText, decimalsFor } from "./common.js";
import { fmt, periodLabel } from "../core/format.js";

const GAP = 15; // minimum vertical distance between labels, px

function spread(items, lo, hi) {
  // items: [{y}] sorted by y; push apart so neighbours are at least GAP apart, within [lo, hi]
  items.sort((a, b) => a.y - b.y);
  for (let i = 1; i < items.length; i++) items[i].ly = Math.max(items[i].y, (items[i - 1].ly ?? items[i - 1].y) + GAP);
  if (items.length) items[0].ly = items[0].y;
  const over = (items.at(-1)?.ly ?? 0) - hi;
  if (over > 0) for (let i = items.length - 1; i >= 0; i--) items[i].ly = Math.max(lo, (items[i].ly ?? items[i].y) - over);
  return items;
}

export function renderSlope(container, set, opts = {}) {
  const { from, to } = opts;
  container.replaceChildren();
  const pick = (x, p) => x.values.find((v) => v.period === p);
  const lines = set.series.map((x, i) => ({ x, i, a: pick(x, from), b: pick(x, to) })).filter((l) => l.a?.value != null && l.b?.value != null);
  const dropped = set.series.length - lines.length;
  if (!lines.length) { container.append(h("p", { class: "muted" }, "Ingen serier har tall for begge årene.")); return { destroy() {} }; }
  const vals = lines.flatMap((l) => [l.a.value, l.b.value]);
  const dec = decimalsFor(set.unit, vals);
  const holder = h("div", { class: "sl-plot" });
  container.append(holder);
  if (dropped) container.append(h("p", { class: "muted small" }, `${dropped} serie${dropped > 1 ? "r" : ""} mangler tall for ett av årene og er utelatt.`));

  function draw(width) {
    const labelW = Math.min(150, Math.max(90, width * 0.3));
    const height = Math.max(260, lines.length * 26 + 40);
    const top = 22, bot = 8, x0 = labelW, x1 = width - labelW;
    const dmin = Math.min(0, ...vals), dmax = Math.max(0, ...vals);
    const y = (v) => top + (1 - (v - dmin) / (dmax - dmin || 1)) * (height - top - bot);
    const svg = s("svg", { width, height, viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": `${set.title}: ${periodLabel(from)} mot ${periodLabel(to)}` });
    const text = (x, yy, str, anchor, cls) => { const t = s("text", { x, y: yy, "text-anchor": anchor, dy: "0.32em", class: cls }); t.textContent = str; return t; };
    svg.append(text(x0, 10, periodLabel(from), "middle", "sl-year"), text(x1, 10, periodLabel(to), "middle", "sl-year"));
    svg.append(s("line", { x1: x0, x2: x0, y1: top - 4, y2: height - bot, class: "ts-grid" }), s("line", { x1: x1, x2: x1, y1: top - 4, y2: height - bot, class: "ts-grid" }));
    if (dmin < 0) svg.append(s("line", { x1: x0, x2: x1, y1: y(0), y2: y(0), class: "ts-zero" }));
    const L = spread(lines.map((l) => ({ l, y: y(l.a.value) })), top, height - bot);
    const R = spread(lines.map((l) => ({ l, y: y(l.b.value) })), top, height - bot);
    for (const l of lines) {
      const col = colorVar(l.i, l.x.other);
      const prelim = isPreliminary(l.a.status) || isPreliminary(l.b.status);
      svg.append(s("line", { x1: x0, y1: y(l.a.value), x2: x1, y2: y(l.b.value), stroke: col, "stroke-width": 2, "stroke-dasharray": prelim ? "5 4" : null }),
                 s("circle", { cx: x0, cy: y(l.a.value), r: 3, fill: isPreliminary(l.a.status) ? "var(--bg)" : col, stroke: col }),
                 s("circle", { cx: x1, cy: y(l.b.value), r: 3, fill: isPreliminary(l.b.status) ? "var(--bg)" : col, stroke: col }));
    }
    // 11 px monospace is about 6.6 px per character: cut the name (never the number) to fit the margin
    const fit = (label, valueStr) => {
      const room = Math.max(0, Math.floor((labelW - 14) / 6.6) - valueStr.length - 1);
      return label.length <= room ? label : room > 1 ? label.slice(0, room - 1) + "…" : "";
    };
    const put = (it, side, value) => {
      const v = fmt(value, dec), name = fit(it.l.x.label, v);
      const t = text(side === "left" ? x0 - 8 : x1 + 8, it.ly, side === "left" ? `${name} ${v}`.trim() : `${v} ${name}`.trim(), side === "left" ? "end" : "start", "sl-label");
      const title = s("title"); title.textContent = `${it.l.x.label}: ${v} ${set.unit}`; t.append(title);
      return t;
    };
    for (const it of L) svg.append(put(it, "left", it.l.a.value));
    for (const it of R) svg.append(put(it, "right", it.l.b.value));
    holder.replaceChildren(svg);
  }
  const stop = observeSize(holder, draw);
  draw(holder.clientWidth || container.clientWidth || 320);
  const unit = set.unit === "prosent" ? "%" : set.unit;
  container.append(h("p", { class: "muted small" }, `Begge årene bruker samme skala fra null. Enhet: ${unit}.`));
  return { destroy() { stop(); container.replaceChildren(); } };
}
