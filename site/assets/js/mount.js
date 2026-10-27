// Mounts every <div class="chart-mount" data-config='{...}'> on the page. One controller per chart:
// loads data, holds the view state {view, year, unit, status, path, dim}, keeps it in the URL, draws controls
// (breadcrumb with a dimension switch per node, «Vis som», year, unit) and the chosen view module.
//
// config: {id, kind: "dataset"|"series", url | urls[], title, views[], defaultView, units[], unitDefs[],
//          denominators: {seriesId: url}}
import { fmt, periodLabel } from "./core/format.js";
import { readState, writeState, formatPath, parsePath } from "./core/url.js";
import { BUILTIN_UNITS, createDataset, nodeFor, timeline, breadcrumb, splittableDims, seriesSet, unitDisabledReason } from "./core/engine.js";
import { h } from "./views/common.js";
import { renderHierBars } from "./views/hier-bars.js";
import { renderTimeseries } from "./views/timeseries.js";

const VIEWS = {
  "hier-bars": { label: "Søyler", snapshot: true },
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
  let ds = null, lines = null, denominators = {};

  try {
    if (cfg.kind === "dataset") ds = createDataset(await json(cfg.url));
    else lines = await Promise.all(cfg.urls.map(json));
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
  const periods = ds ? ds.periods : [];
  const defaults = { view: cfg.defaultView ?? views[0], year: periods[periods.length - 1], unit: "raw", path: "", dim: ds?.meta.default_dimension };
  let state = { ...defaults, ...readState(cfg.id) };
  if (!views.includes(state.view)) state.view = defaults.view;
  if (ds && !periods.includes(state.year)) state.year = defaults.year;
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
      parts.push(select("År", state.year, [...periods].reverse().map((p) => ({ value: p, label: periodLabel(p) + (ds.statusByPeriod[p] === "foreløpig" ? " (foreløpig)" : "") })), (v) => push({ year: v })));
    }
    if (ds && unitDefs.length > 1) {
      parts.push(select("Enhet", state.unit, unitDefs.map((u) => {
        const why = unitDisabledReason(ds, u);
        return { value: u.id, label: u.id === "raw" ? ds.meta.unit : u.label, disabled: !!why, title: why ?? "" };
      }), (v) => push({ unit: v })));
    }
    parts.push(h("button", { type: "button", class: "btn", onclick: copyLink }, "Kopier lenke"));
    const active = [VIEWS[state.view].label, ds && view.snapshot ? periodLabel(state.year) : null, ds ? (state.unit === "raw" ? ds.meta.unit : unitById[state.unit].label) : null].filter(Boolean);
    chips.replaceChildren(...active.map((a) => h("span", { class: "chip" }, a)));
    settings.replaceChildren(h("summary", { class: "mono" }, "Innstillinger ", chips), h("div", { class: "ctl-row" }, parts));
  }

  async function copyLink() {
    try { await navigator.clipboard.writeText(location.href); status.textContent = "Lenken er kopiert."; }
    catch { status.textContent = "Kunne ikke kopiere. Kopier adressen fra nettleseren."; }
  }

  function crumbsUI() {
    if (!ds) { crumbs.hidden = true; return; }
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
    const base = ds ? { path: state.path, dim: state.dim, unit, denominators, period: state.year } : null;
    if (state.view === "hier-bars") {
      const node = nodeFor(ds, base);
      const dimNow = node.dim;
      const canDrill = (r) => {
        const sel = parsePath(r.path);
        return ds.dims[dimNow]?.byCode.get(sel[sel.length - 1].code)?.children.length > 0;
      };
      current = renderHierBars(body, node, { canDrill, onDrill: (path) => push({ path }) });
      status.textContent = node.status === "foreløpig" ? "Foreløpige tall." : "";
    } else if (ds) {
      current = renderTimeseries(body, timeline(ds, base), { mode: view.mode, period: state.year, onPeriod: (p) => { state.year = p; } });
    } else {
      current = renderTimeseries(body, seriesSet(cfg.title, lines, { labels: cfg.labels }), { mode: view.mode });
    }
  }
  render();
}

for (const el of document.querySelectorAll(".chart-mount[data-config]")) init(el);
