// timeseries: lines, stacked, 100 % stacked or bars (diverging, zero line) over time, drawn with d3 scales.
// Honest by construction: zero baseline, gaps stay gaps (never interpolated), preliminary values are dashed or
// hatched, series breaks are vertical dashed lines, «Øvrig» is always the same grey. A readout below the chart
// (not a tooltip following the finger) lists every value for the selected period; arrow keys move it.
import { h, s, observeSize, colorVar, isPreliminary, valueText, decimalsFor, CLAIM_LABEL, STATUS_LABEL } from "./common.js";
import { fmt, periodLabel } from "../core/format.js";

const M = { top: 20, right: 14, bottom: 26, left: 54 };
const yearOf = (p) => +p.slice(0, 4) + (p.length > 4 ? (+p.slice(5, 7) - 0.5) / 12 : 0);

export function renderTimeseries(container, set, opts = {}) {
  const d3 = window.d3;
  const { mode = "lines", onPeriod = () => {} } = opts;
  container.replaceChildren();
  const periods = set.periods;
  if (!periods.length) { container.append(h("p", { class: "muted" }, "Ingen data.")); return { destroy() {} }; }
  let selected = opts.period ?? periods[periods.length - 1];

  const series = set.series;
  const allVals = series.flatMap((x) => x.values.map((v) => v.value)).filter((v) => v !== null);
  const dec = decimalsFor(set.unit, allVals);
  const stacked = mode === "stacked" || mode === "stacked100";
  const isBars = mode === "bars" || stacked;

  const legend = h("ul", { class: "ts-legend", role: "list" });
  const readout = h("div", { class: "readout", "aria-live": "polite" });
  const holder = h("div", { class: "ts-plot" });
  container.append(holder, legend, readout);
  let focus = null; // series id isolated by legend hover/focus

  const worst = (x) => x.values.reduce((w, v) => ({ offisiell: 0, utledet: 1, estimat: 2 }[v.claim] > ({ offisiell: 0, utledet: 1, estimat: 2 }[w]) ? v.claim : w), "offisiell");
  const mark = (x) => ({ utledet: "ƒ ", estimat: "≈ " }[worst(x)] ?? "");
  series.forEach((x, i) => {
    const item = h("li", {}, h("button", { type: "button", class: "ts-key",
      onmouseenter: () => { focus = x.id; draw(); }, onmouseleave: () => { focus = null; draw(); },
      onfocus: () => { focus = x.id; draw(); }, onblur: () => { focus = null; draw(); } },
      h("span", { class: "ts-swatch", style: `--bar:${colorVar(i, x.other)}` }), mark(x) + x.label));
    legend.append(item);
  });

  function showReadout() {
    const rows = series.map((x, i) => {
      const v = x.values.find((q) => q.period === selected);
      return h("li", {},
        h("span", { class: "ts-swatch", style: `--bar:${colorVar(i, x.other)}` }),
        h("span", { class: "ro-label" }, mark(x) + x.label),
        h("span", { class: "num" }, valueText(v?.value ?? null, set.unit, dec)),
        v && v.claim !== "offisiell" ? h("span", { class: `claim claim-${v.claim}` }, CLAIM_LABEL[v.claim]) : null,
        v && isPreliminary(v.status) ? h("span", { class: "muted small" }, STATUS_LABEL[v.status]) : null);
    });
    const brk = (set.breaks ?? []).filter((b) => b.period === selected);
    readout.replaceChildren(h("strong", {}, periodLabel(selected)), h("ul", { class: "ro-list", role: "list" }, rows),
      ...brk.map((b) => h("p", { class: "muted small" }, `Brudd i serien: ${b.note}`)));
  }

  function draw() {
    const width = holder.clientWidth || container.clientWidth || 320;
    const height = Math.max(220, Math.min(380, Math.round(width * 0.55)));
    const iw = width - M.left - M.right, ih = height - M.top - M.bottom;

    // data prepared per mode
    let layers = null;
    let yMin = 0, yMax = 0;
    if (stacked) {
      const keys = series.map((x) => x.id);
      const rows = periods.map((p) => Object.fromEntries([["period", p], ...series.map((x) => [x.id, x.values.find((v) => v.period === p)?.value ?? 0])]));
      const stack = d3.stack().keys(keys).offset(mode === "stacked100" ? d3.stackOffsetExpand : d3.stackOffsetDiverging);
      layers = stack(rows);
      yMin = d3.min(layers, (l) => d3.min(l, (d) => d[0])); yMax = d3.max(layers, (l) => d3.max(l, (d) => d[1]));
    } else {
      yMin = Math.min(0, d3.min(allVals) ?? 0); yMax = Math.max(0, d3.max(allVals) ?? 1);
    }
    const y = d3.scaleLinear().domain([yMin, yMax]).nice().range([ih, 0]);
    const xBand = d3.scaleBand().domain(periods).range([0, iw]).paddingInner(0.15);
    const xLin = d3.scaleLinear().domain(d3.extent(periods, yearOf)).range([isBars ? xBand.bandwidth() / 2 : 0, iw - (isBars ? xBand.bandwidth() / 2 : 0)]);
    const xAt = (p) => (isBars ? xBand(p) + xBand.bandwidth() / 2 : xLin(yearOf(p)));

    const svg = s("svg", { width, height, viewBox: `0 0 ${width} ${height}`, role: "img", tabindex: "0",
      "aria-label": `${set.title}. Bruk piltastene for å velge periode.` });
    svg.append(s("defs", {},
      s("pattern", { id: "ts-hatch", width: 6, height: 6, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" },
        s("line", { x1: 0, y1: 0, x2: 0, y2: 6, stroke: "var(--bg)", "stroke-width": 2.5 })),
      // utledet: thin stripes the other way round, so it is never confused with a preliminary (wide stripes) value
      s("pattern", { id: "ts-derived", width: 4, height: 4, patternUnits: "userSpaceOnUse", patternTransform: "rotate(-45)" },
        s("line", { x1: 0, y1: 0, x2: 0, y2: 4, stroke: "var(--bg)", "stroke-width": 1.3 }))));
    const g = s("g", { transform: `translate(${M.left},${M.top})` });
    svg.append(g);

    // grid + y axis
    const yAxis = s("g", { class: "ts-axis" });
    for (const t of y.ticks(5)) {
      yAxis.append(s("line", { x1: 0, x2: iw, y1: y(t), y2: y(t), class: t === 0 ? "ts-zero" : "ts-grid" }));
      const label = s("text", { x: -8, y: y(t), dy: "0.32em", "text-anchor": "end" });
      label.textContent = mode === "stacked100" ? `${fmt(t * 100, 0)} %` : fmt(t, set.unit === "prosent" ? 0 : dec > 1 ? 0 : dec);
      yAxis.append(label);
    }
    g.append(yAxis);
    const unitText = s("text", { x: -M.left + 2, y: -8, class: "ts-unit" });
    unitText.textContent = mode === "stacked100" ? "% av totalen" : set.unit;
    g.append(unitText);
    // x axis: as many labels as fit
    const step = Math.max(1, Math.ceil(periods.length / Math.max(2, Math.floor(iw / 46))));
    const xAxis = s("g", { class: "ts-axis", transform: `translate(0,${ih + 6})` });
    // labels counted back from the latest period, so the newest one is always shown and never collides
    periods.forEach((p, i) => { if ((periods.length - 1 - i) % step === 0) { const t = s("text", { x: xAt(p), "text-anchor": "middle", dy: "0.8em" }); t.textContent = p.slice(0, 4); xAxis.append(t); } });
    g.append(xAxis);

    // series breaks: vertical dashed lines, never smoothed over
    for (const b of set.breaks ?? []) if (periods.includes(b.period)) g.append(s("line", { x1: xAt(b.period), x2: xAt(b.period), y1: 0, y2: ih, class: "ts-break" }));

    const dim = (id) => (focus && focus !== id ? 0.18 : 1);
    // claim-level marks on bars: utledet = thin counter-stripes, estimat = dotted outline (offisiell stays solid)
    const claimMarks = (grp, v, x0, w, yTop, hh) => {
      if (!v) return;
      if (v.claim === "utledet") grp.append(s("rect", { x: x0, width: w, y: yTop, height: hh, fill: "url(#ts-derived)" }));
      if (v.claim === "estimat") grp.append(s("rect", { x: x0, width: w, y: yTop, height: hh, fill: "none", stroke: "var(--bg)", "stroke-dasharray": "2 2" }));
    };
    if (stacked) {
      layers.forEach((layer, i) => {
        const x = series[i];
        const grp = s("g", { fill: colorVar(i, x.other), opacity: dim(x.id) });
        layer.forEach((d, j) => {
          const v = x.values[j];
          const r = s("rect", { x: xBand(periods[j]), width: xBand.bandwidth(), y: y(d[1]), height: Math.max(0, y(d[0]) - y(d[1])) });
          grp.append(r);
          if (v && isPreliminary(v.status)) grp.append(s("rect", { x: xBand(periods[j]), width: xBand.bandwidth(), y: y(d[1]), height: Math.max(0, y(d[0]) - y(d[1])), fill: "url(#ts-hatch)" }));
          claimMarks(grp, v, xBand(periods[j]), xBand.bandwidth(), y(d[1]), Math.max(0, y(d[0]) - y(d[1])));
        });
        g.append(grp);
      });
    } else if (mode === "bars") {
      const n = series.length, bw = xBand.bandwidth() / n;
      series.forEach((x, i) => {
        const grp = s("g", { fill: colorVar(i, x.other), opacity: dim(x.id) });
        x.values.forEach((v) => {
          if (v.value === null) return;
          const bx = xBand(v.period) + i * bw;
          grp.append(s("rect", { x: bx, width: bw, y: Math.min(y(0), y(v.value)), height: Math.abs(y(v.value) - y(0)) }));
          if (isPreliminary(v.status)) grp.append(s("rect", { x: bx, width: bw, y: Math.min(y(0), y(v.value)), height: Math.abs(y(v.value) - y(0)), fill: "url(#ts-hatch)" }));
          claimMarks(grp, v, bx, bw, Math.min(y(0), y(v.value)), Math.abs(y(v.value) - y(0)));
        });
        g.append(grp);
      });
    } else {
      series.forEach((x, i) => {
        const col = colorVar(i, x.other);
        const grp = s("g", { stroke: col, fill: "none", "stroke-width": 2, opacity: dim(x.id) });
        let run = [];
        const flush = () => {
          if (run.length > 1) {
            // a segment that ends in a preliminary value is dashed
            for (let k = 1; k < run.length; k++) {
              grp.append(s("line", { x1: xAt(run[k - 1].period), y1: y(run[k - 1].value), x2: xAt(run[k].period), y2: y(run[k].value),
                "stroke-dasharray": isPreliminary(run[k].status) ? "4 3" : null }));
            }
          }
          for (const v of run) grp.append(s("circle", { cx: xAt(v.period), cy: y(v.value), r: 2.4, fill: isPreliminary(v.status) ? "var(--bg)" : col }));
          run = [];
        };
        for (const v of x.values) { if (v.value === null) flush(); else run.push(v); }
        flush();
        g.append(grp);
      });
    }

    // selection cursor + pointer handling (nearest period; works for mouse, touch and keyboard)
    const cursor = s("line", { class: "ts-cursor", y1: 0, y2: ih, x1: xAt(selected), x2: xAt(selected) });
    g.append(cursor);
    const nearest = (px) => periods.reduce((best, p) => (Math.abs(xAt(p) - px) < Math.abs(xAt(best) - px) ? p : best), periods[0]);
    const pick = (ev) => {
      const r = svg.getBoundingClientRect();
      select(nearest(ev.clientX - r.left - M.left));
    };
    svg.addEventListener("pointerdown", pick);
    svg.addEventListener("pointermove", (ev) => { if (ev.pointerType === "mouse") pick(ev); });
    svg.addEventListener("keydown", (ev) => {
      const i = periods.indexOf(selected);
      const next = { ArrowLeft: i - 1, ArrowRight: i + 1, Home: 0, End: periods.length - 1 }[ev.key];
      if (next !== undefined && periods[next]) { ev.preventDefault(); select(periods[next]); }
    });
    holder.replaceChildren(svg);
    drawn = { cursor, xAt };
  }

  let drawn = null;
  function select(p) {
    if (p === selected) return;
    selected = p;
    if (drawn) { drawn.cursor.setAttribute("x1", drawn.xAt(p)); drawn.cursor.setAttribute("x2", drawn.xAt(p)); }
    showReadout();
    onPeriod(p);
  }

  const stop = observeSize(holder, draw);
  draw();
  showReadout();
  return { destroy() { stop(); container.replaceChildren(); }, select };
}
