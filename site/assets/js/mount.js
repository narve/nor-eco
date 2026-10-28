// Mounts every <div class="chart-mount" data-config='{...}'> on the page. One controller per chart:
// loads data, holds the view state {view, year, unit, status, path, dim}, keeps it in the URL, draws controls
// (breadcrumb with a dimension switch per node, «Vis som», year, unit) and the chosen view module.
//
// config: {id, kind: "dataset"|"series"|"waterfall"|"flow" (urls left/right, mid, gapLeft, gapRight), url | urls[] | steps[], title, views[], defaultView, units[],
//          unitDefs[], denominators: {seriesId: url}}
// waterfall steps: [{label, url, period, mult?, role: "start"|"delta"|"total", claim?, expected?: {url, period, mult?}, note?}]
import { fmt, periodLabel } from "./core/format.js";
import { readState, writeState, formatPath, parsePath } from "./core/url.js";
import { BUILTIN_UNITS, STATUS_ORDER, statusFor, createDataset, nodeFor, timeline, breadcrumb, splittableDims, seriesSet, unitDisabledReason } from "./core/engine.js";
import { h } from "./views/common.js";
import { renderHierBars } from "./views/hier-bars.js";
import { renderTimeseries } from "./views/timeseries.js";
import { renderTreemap } from "./views/treemap.js";
import { renderSlope } from "./views/slope.js";
import { renderWaterfall } from "./views/waterfall.js";
import { renderWaffle } from "./views/waffle.js";
import { renderSunburst } from "./views/sunburst.js";
import { renderIcicle } from "./views/icicle.js";
import { renderRings } from "./views/rings.js";
import { renderReceipt } from "./views/receipt.js";
import { renderMarimekko } from "./views/marimekko.js";
import { renderSankey } from "./views/sankey.js";
import { renderUpset } from "./views/euler-upset.js";

const STATUS_UI = { regnskap: "Regnskap", budsjett: "Budsjett", saldert: "Saldert", vedtatt: "Vedtatt", forslag: "Forslag", anslag: "Anslag", foreløpig: "Foreløpig" };

const VIEWS = {
  "hier-bars": { label: "Søyler", snapshot: true },
  treemap: { label: "Flisekart", snapshot: true },
  waffle: { label: "Rutenett", snapshot: true },
  sunburst: { label: "Solstråle", snapshot: true },
  icicle: { label: "Istapp", snapshot: true },
  rings: { label: "Ringer", snapshot: true },
  receipt: { label: "Kvittering", snapshot: true },
  marimekko: { label: "Marimekko", snapshot: true },
  "euler-upset": { label: "Overlapp", snapshot: true },
  sankey: { label: "Strøm", snapshot: true },
  slope: { label: "Før og nå", snapshot: false, compare: true },
  waterfall: { label: "Trinn for trinn", snapshot: false, steps: true },
  "timeseries-lines": { label: "Linjer", snapshot: false, mode: "lines" },
  "timeseries-stacked": { label: "Stablet", snapshot: false, mode: "stacked" },
  "timeseries-bars": { label: "Søyler over tid", snapshot: false, mode: "bars" },
};

const json = async (url) => {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
};

async function init(el) {
  const cfg = JSON.parse(el.dataset.config);
  const root = h("div", { class: "chart-ui" });
  el.replaceChildren(root);
  let ds = null, ds2 = null, lines = null, steps = null, denominators = {};

  try {
    if (cfg.kind === "dataset") ds = createDataset(await json(cfg.url));
    else if (cfg.kind === "flow") { ds = createDataset(await json(cfg.left)); ds2 = createDataset(await json(cfg.right)); }
    else if (cfg.kind === "waterfall") {
      const urls = [...new Set(cfg.steps.flatMap((st) => [st.url, st.expected?.url]).filter(Boolean))];
      const loaded = Object.fromEntries(await Promise.all(urls.map(async (u) => [u, await json(u)])));
      const at = (u, period) => loaded[u].values.find((v) => v.period === period);
      steps = cfg.steps.map((st) => {
        const v = at(st.url, st.period);
        if (!v) throw new Error(`no value for ${st.url} ${st.period}`);
        const mult = st.mult ?? 1;
        const e = st.expected ? at(st.expected.url, st.expected.period) : null;
        return { label: st.label, role: st.role, value: v.value * mult, status: v.status ?? null, claim: st.claim ?? loaded[st.url].claim_level,
                 expected: e ? e.value * (st.expected.mult ?? 1) : undefined, note: st.note };
      });
    } else lines = await Promise.all(cfg.urls.map(json));
    for (const [id, url] of Object.entries(cfg.denominators ?? {})) {
      denominators[id] = Object.fromEntries((await json(url)).values.map((v) => [v.period, v.value]));
    }
  } catch (e) {
    root.append(h("p", { class: "muted" }, "Kunne ikke laste dataene til visningen. Tabellen under viser de samme tallene."));
    console.error(e);
    return;
  }

  const unitDefs = [...Object.values(BUILTIN_UNITS), ...(cfg.unitDefs ?? []).map((u) => ({ ...u }))].filter((u) => u.id === "raw" || (cfg.units ?? []).includes(u.id));
  const unitById = Object.fromEntries(unitDefs.map((u) => [u.id, u]));
  const views = cfg.views.filter((v) => VIEWS[v]);
  const periods = ds ? ds.periods : lines ? seriesSet(cfg.title, lines).periods : [];
  const defaultStatus = ds?.statuses[0];
  // default year: the latest one that has the default status (accounts), so the first view is not a budget year
  // «foreløpig» counts as actual data (it is the latest measurement); budget, proposal and forecast statuses do not.
  const ACTUAL = ["regnskap", "foreløpig"];
  const defaultYear = ds ? [...periods].reverse().find((p) => ACTUAL.some((a) => ds.statusesByPeriod[p].has(a))) ?? periods[periods.length - 1] : undefined;
  const defaults = { view: cfg.defaultView ?? views[0], year: defaultYear ?? periods[periods.length - 1], year2: periods[0], unit: "raw", path: "", dim: ds?.meta.default_dimension, status: defaultStatus };
  let state = { ...defaults, ...readState(cfg.id) };
  if (!views.includes(state.view)) state.view = defaults.view;
  if (periods.length && !periods.includes(state.year)) state.year = defaults.year;
  if (periods.length && !periods.includes(state.year2)) state.year2 = defaults.year2;
  if (ds && !ds.statuses.includes(state.status)) state.status = defaults.status;
  if (!unitById[state.unit] || (ds && unitDisabledReason(ds, unitById[state.unit]))) state.unit = "raw";

  const crumbs = h("nav", { class: "crumbs", "aria-label": "Sti" });
  const settings = h("details", { class: "settings" });
  const chips = h("span", { class: "chips" });
  const body = h("div", { class: "chart-body" });
  const status = h("p", { class: "chart-note muted small" });
  root.append(crumbs, settings, body, status);
  settings.open = window.matchMedia("(min-width: 640px)").matches;

  const push = (next, { replace = false } = {}) => {
    state = { ...state, ...next };
    writeState(cfg.id, state, { replace });
    render();
  };
  window.addEventListener("popstate", () => {
    state = { ...defaults, ...readState(cfg.id) };
    if (!views.includes(state.view)) state.view = defaults.view;
    render();
  });

  const select = (label, value, options, onchange, id) =>
    h("label", { class: "ctl" }, h("span", { class: "mono" }, label),
      h("select", { id, onchange: (e) => onchange(e.target.value) },
        options.map((o) => h("option", { value: o.value, selected: o.value === value, disabled: o.disabled, title: o.title }, o.label))));

  function controls() {
    const view = VIEWS[state.view];
    const parts = [];
    if (views.length > 1) {
      parts.push(h("div", { class: "ctl" }, h("span", { class: "mono" }, "Vis som"),
        h("div", { class: "seg", role: "group", "aria-label": "Vis som" },
          views.map((v) => h("button", { type: "button", "aria-pressed": String(v === state.view), onclick: () => push({ view: v }) }, VIEWS[v].label)))));
    }
    if (ds && view.snapshot) {
      parts.push(select("År", state.year, [...periods].reverse().map((p) => ({ value: p, label: periodLabel(p) + (statusFor(ds, p, state.status) === "foreløpig" ? " (foreløpig)" : "") })), (v) => push({ year: v })));
    }
    if (view.compare) {
      const opts = [...periods].map((p) => ({ value: p, label: periodLabel(p) }));
      parts.push(select("Fra år", state.year2, opts, (v) => push({ year2: v })), select("Til år", state.year, opts, (v) => push({ year: v })));
    }
    if (ds && ds.statuses.length > 1) {
      parts.push(h("div", { class: "ctl" }, h("span", { class: "mono" }, "Tall"),
        h("div", { class: "seg", role: "group", "aria-label": "Tall" },
          ds.statuses.map((st) => h("button", { type: "button", "aria-pressed": String(st === state.status), onclick: () => push({ status: st }) }, STATUS_UI[st] ?? st)))));
    }
    if (ds && unitDefs.length > 1) {
      parts.push(select("Enhet", state.unit, unitDefs.map((u) => {
        const why = unitDisabledReason(ds, u);
        return { value: u.id, label: u.id === "raw" ? ds.meta.unit : u.label, disabled: !!why, title: why ?? "" };
      }), (v) => push({ unit: v })));
    }
    parts.push(h("button", { type: "button", class: "btn", onclick: copyLink }, "Kopier lenke"));
    if (document.fullscreenEnabled) parts.push(h("button", { type: "button", class: "btn", onclick: toggleFullscreen }, document.fullscreenElement === root ? "Avslutt fullskjerm" : "Fullskjerm"));
    const active = [VIEWS[state.view].label, ds && view.snapshot ? periodLabel(state.year) : null, view.compare ? `${periodLabel(state.year2)} → ${periodLabel(state.year)}` : null, ds && ds.statuses.length > 1 ? (STATUS_UI[state.status] ?? state.status) : null, ds ? (state.unit === "raw" ? ds.meta.unit : unitById[state.unit].label) : null].filter(Boolean);
    chips.replaceChildren(...active.map((a) => h("span", { class: "chip" }, a)));
    settings.replaceChildren(h("summary", { class: "mono" }, "Innstillinger ", chips), h("div", { class: "ctl-row" }, parts));
  }

  async function copyLink() {
    try { await navigator.clipboard.writeText(location.href); status.textContent = "Lenken er kopiert."; }
    catch { status.textContent = "Kunne ikke kopiere. Kopier adressen fra nettleseren."; }
  }

  function toggleFullscreen() {
    if (document.fullscreenElement === root) document.exitFullscreen();
    else root.requestFullscreen?.().catch(() => { status.textContent = "Nettleseren tillot ikke fullskjerm."; });
  }
  document.addEventListener("fullscreenchange", () => { if (document.fullscreenElement === root || !document.fullscreenElement) controls(); });

  function crumbsUI() {
    if (!ds || cfg.kind === "flow") { crumbs.hidden = true; return; }
    crumbs.hidden = false;
    const trail = breadcrumb(ds, state);
    const dims = splittableDims(ds, state);
    const items = trail.map((c, i) => h("button", { type: "button", class: "crumb", "aria-current": i === trail.length - 1 ? "true" : null,
      onclick: () => push({ path: c.path }) }, c.label));
    const seq = [];
    items.forEach((b, i) => { if (i) seq.push(h("span", { class: "sep", "aria-hidden": "true" }, "›")); seq.push(b); });
    // dimension switch at the current node
    if (dims.length > 1) {
      seq.push(h("label", { class: "ctl inline" }, h("span", { class: "mono" }, "del etter"),
        h("select", { onchange: (e) => push({ dim: e.target.value }) },
          dims.map((d) => h("option", { value: d.id, selected: d.id === (state.dim ?? ds.meta.default_dimension) }, d.label)))));
    }
    crumbs.replaceChildren(...seq);
  }

  let current = null;
  function render() {
    current?.destroy?.();
    const view = VIEWS[state.view];
    controls();
    crumbsUI();
    body.replaceChildren();
    const unit = ds ? unitById[state.unit] : null;
    const base = ds ? { path: state.path, dim: state.dim, unit, denominators, period: state.year, status: state.status } : null;
    if (cfg.kind === "waterfall") {
      current = renderWaterfall(body, steps, { unit: cfg.unit ?? "mrd. kr", tol: cfg.tol });
      return;
    }
    if (cfg.kind === "flow") {
      const at = (d) => nodeFor(d, { ...base, depth: 1, unit: BUILTIN_UNITS.raw });
      const l = at(ds), r = at(ds2);
      const kids = (n) => [...(n.children ?? []), ...(n.other ? [n.other] : [])];
      const diff = r.value - l.value;
      const gap = Math.abs(diff) < 1e-9 ? null
        : diff > 0 ? { side: "left", label: cfg.gapLeft, value: diff, claim_level: "utledet" } : { side: "right", label: cfg.gapRight, value: -diff, claim_level: "utledet" };
      current = renderSankey(body, { left: kids(l), right: kids(r), mid: cfg.mid, gap, unit: l.unit });
      status.textContent = l.status === "foreløpig" ? "Foreløpige tall." : "";
      return;
    }
    if (state.view === "sunburst" || state.view === "icicle" || state.view === "rings" || state.view === "receipt") {
      const node = nodeFor(ds, { ...base, depth: state.view === "sunburst" || state.view === "icicle" ? 3 : 1 });
      const canDrill = (r) => {
        const sel = parsePath(r.path);
        const last = sel[sel.length - 1];
        return ds.dims[last.dim]?.byCode.get(last.code)?.children.length > 0;
      };
      const draw = { sunburst: renderSunburst, icicle: renderIcicle, rings: renderRings, receipt: renderReceipt }[state.view];
      current = draw(body, node, { canDrill, onDrill: (path) => push({ path }) });
      status.textContent = node.status === "foreløpig" ? "Foreløpige tall." : "";
      return;
    }
    if (state.view === "euler-upset") {
      const node = nodeFor(ds, { ...base, unit: BUILTIN_UNITS.raw, depth: 6 });
      current = renderUpset(body, node);
      status.textContent = node.status === "foreløpig" ? "Foreløpige tall." : "";
      return;
    }
    if (state.view === "marimekko") {
      const first = nodeFor(ds, { ...base, depth: 1 });
      const dimA = first.dim;
      const other = (cfg.dim2 && ds.dimIds.includes(cfg.dim2) ? cfg.dim2 : ds.dimIds.find((d) => d !== dimA));
      if (!other) { body.append(h("p", { class: "muted" }, "Datasettet har bare én dimensjon.")); current = null; return; }
      const cols = [...(first.children ?? []), ...(first.other ? [first.other] : [])].map((c) => ({ node: c, parts: nodeFor(ds, { ...base, path: c.path, dim: other, depth: 1 }) }));
      current = renderMarimekko(body, cols, { dimLabels: [ds.dims[dimA].label, ds.dims[other].label], unit: first.unit });
      status.textContent = first.status === "foreløpig" ? "Foreløpige tall." : "";
      return;
    }
    if (state.view === "waffle") {
      const node = nodeFor(ds, { ...base, unit: BUILTIN_UNITS.raw, depth: 6 });
      current = renderWaffle(body, node, { groups: cfg.groups });
      status.textContent = node.status === "foreløpig" ? "Foreløpige tall." : "";
    } else if (state.view === "hier-bars" || state.view === "treemap") {
      const node = nodeFor(ds, base);
      const dimNow = node.dim;
      const canDrill = (r) => {
        const sel = parsePath(r.path);
        return ds.dims[dimNow]?.byCode.get(sel[sel.length - 1].code)?.children.length > 0;
      };
      const draw = state.view === "treemap" ? renderTreemap : renderHierBars;
      current = draw(body, node, { canDrill, onDrill: (path) => push({ path }) });
      status.textContent = node.status !== state.status && ds.statuses.length > 1 && node.status !== "foreløpig"
        ? `${STATUS_UI[state.status] ?? state.status} finnes ikke for ${periodLabel(state.year)}. Viser ${STATUS_UI[node.status] ?? node.status}.`
        : node.status === "foreløpig" ? "Foreløpige tall." : "";
    } else if (state.view === "slope") {
      const set = ds ? timeline(ds, base) : seriesSet(cfg.title, lines, { labels: cfg.labels, unit: cfg.unit });
      current = renderSlope(body, set, { from: state.year2, to: state.year });
    } else if (ds) {
      current = renderTimeseries(body, timeline(ds, base), { mode: view.mode, period: state.year, onPeriod: (p) => { state.year = p; } });
    } else {
      current = renderTimeseries(body, seriesSet(cfg.title, lines, { labels: cfg.labels, unit: cfg.unit }), { mode: view.mode });
    }
  }
  render();
}

for (const el of document.querySelectorAll(".chart-mount[data-config]")) init(el);
