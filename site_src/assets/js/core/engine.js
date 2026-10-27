// Dimension engine: turns a published dataset bundle (site/data/<topic>/<dataset>.json) into the Node tree
// of schema/node.schema.json, and into time series for the timeline views.
//
// Facts are fully specified leaf rows, so every node of every dimension sums to its parent and every
// dimension gives the same total. A view state is {path, dim}: `path` selects (dimension:code) filters in
// order (the last code per dimension wins), `dim` is the dimension the next level is split by.
import { parsePath, formatPath } from "./url.js";

export function createDataset(bundle) {
  const { meta, dimensions, columns, rows } = bundle;
  const col = Object.fromEntries(columns.map((c, i) => [c, i]));
  const dims = {};
  for (const id of meta.dimensions) {
    const byCode = new Map(dimensions[id].nodes.map((n) => [n.code, { ...n, children: [] }]));
    let root = null;
    for (const n of byCode.values()) (n.parent == null ? (root = n) : byCode.get(n.parent).children.push(n));
    const leaves = new Map();
    const walk = (n) => (n.children.length ? n.children.flatMap(walk) : [n.code]);
    for (const n of byCode.values()) leaves.set(n.code, new Set(walk(n)));
    dims[id] = { id, label: dimensions[id].label, byCode, root, leaves };
  }
  const facts = rows.map((r) => ({
    period: r[col.period], value: r[col.value], status: r[col.status], claim: r[col.claim_level], source: r[col.source_id],
    codes: Object.fromEntries(meta.dimensions.map((d) => [d, r[col[d]]])),
  }));
  const periods = [...new Set(facts.map((f) => f.period))].sort();
  const statusByPeriod = {};
  for (const f of facts) statusByPeriod[f.period] ??= f.status;
  return { meta, dims, dimIds: meta.dimensions, facts, periods, statusByPeriod };
}

// ---- unit definitions -------------------------------------------------------------------------------
// kind 'raw'          the dataset's own unit
//      'pct-parent'   share of the node being shown (children sum to 100)
//      'pct-total'    share of the dataset total for the period
//      'ratio'        value * scale / denominator[period] (denominator: a processed series)
export const BUILTIN_UNITS = {
  raw: { id: "raw", kind: "raw", label: null },
  "pct-parent": { id: "pct-parent", kind: "pct-parent", label: "% av overordnet", unit: "prosent" },
  "pct-total": { id: "pct-total", kind: "pct-total", label: "% av totalen", unit: "prosent" },
};

// Is this unit meaningful for this dataset? Returns null if yes, otherwise a short reason.
export function unitDisabledReason(ds, unit) {
  if (unit.kind === "ratio" && unit.price_basis && ds.meta.price_basis !== unit.price_basis) {
    return `krever ${unit.price_basis} priser`;
  }
  return null;
}

// denominators: { [seriesId]: { [period]: number } }
export function toUnit(raw, unit, ctx) {
  if (raw === null) return null;
  switch (unit.kind) {
    case "raw": return raw;
    case "pct-parent": return ctx.parentValue ? (100 * raw) / ctx.parentValue : null;
    case "pct-total": return ctx.totalValue ? (100 * raw) / ctx.totalValue : null;
    case "ratio": {
      const d = ctx.denominators?.[unit.series]?.[ctx.period];
      return d ? (raw * unit.scale) / d : null;
    }
    default: throw new Error(`unknown unit kind ${unit.kind}`);
  }
}

export function unitLabel(ds, unit) {
  return unit.kind === "raw" ? ds.meta.unit : unit.unit;
}

// ---- aggregation ------------------------------------------------------------------------------------
function selection(ds, segments) {
  const sel = {};
  for (const { dim, code } of segments) {
    if (!ds.dims[dim]?.byCode.has(code)) throw new Error(`unknown ${dim}:${code}`);
    sel[dim] = code;
  }
  return sel;
}

function aggregate(ds, sel, period) {
  let sum = 0, n = 0, claim = "offisiell", status = null;
  const sources = new Set();
  const rank = { offisiell: 0, utledet: 1, estimat: 2 };
  for (const f of ds.facts) {
    if (f.period !== period) continue;
    let ok = true;
    for (const d in sel) if (!ds.dims[d].leaves.get(sel[d]).has(f.codes[d])) { ok = false; break; }
    if (!ok) continue;
    sum += f.value; n++; status = status ?? f.status; sources.add(f.source);
    if (rank[f.claim] > rank[claim]) claim = f.claim;
  }
  return { value: n ? Math.round(sum * 1e6) / 1e6 : null, claim, status, sources: [...sources].sort() };
}

function labelFor(ds, segments, sel) {
  if (segments.length) {
    const last = segments[segments.length - 1];
    return ds.dims[last.dim].byCode.get(last.code).label;
  }
  return ds.dims[ds.meta.default_dimension ?? ds.dimIds[0]].root.label;
}

// ---- Node tree --------------------------------------------------------------------------------------
// state: {path, dim, period, unit (unit object), denominators, depth}
export function nodeFor(ds, state) {
  const segments = parsePath(state.path ?? "");
  const dim = state.dim ?? ds.meta.default_dimension ?? ds.dimIds[0];
  const unit = state.unit ?? BUILTIN_UNITS.raw;
  const total = aggregate(ds, {}, state.period).value;
  const here = aggregate(ds, selection(ds, segments), state.period);

  const build = (segs, nodeDim, depth, parentValue) => {
    const sel = selection(ds, segs);
    const agg = aggregate(ds, sel, state.period);
    const ctx = { parentValue, totalValue: total, denominators: state.denominators, period: state.period };
    const node = {
      path: formatPath(segs),
      dim: "",
      label: labelFor(ds, segs, sel),
      value: toUnit(agg.value, unit, { ...ctx, parentValue: parentValue ?? agg.value }),
      raw: agg.value,
      unit: unitLabel(ds, unit),
      status: agg.status ?? ds.statusByPeriod[state.period] ?? "regnskap",
      claim_level: agg.claim,
      source_ids: agg.sources,
    };
    const base = sel[nodeDim] ?? ds.dims[nodeDim].root.code;
    const kids = ds.dims[nodeDim].byCode.get(base).children;
    if (depth > 0 && kids.length) {
      node.dim = nodeDim;
      node.children = [];
      for (const k of kids) {
        const child = build([...segs, { dim: nodeDim, code: k.code }], nodeDim, depth - 1, agg.value);
        if (k.other) node.other = child; else node.children.push(child);
      }
    }
    return node;
  };
  const node = build(segments, dim, state.depth ?? 1, here.value);
  node.value = toUnit(here.value, unit, { parentValue: here.value, totalValue: total, denominators: state.denominators, period: state.period });
  return node;
}

// ---- breadcrumb -------------------------------------------------------------------------------------
// [{label, path, dim}] from the root to the current node; `dim` is the dimension the crumb was split by.
export function breadcrumb(ds, state) {
  const segments = parsePath(state.path ?? "");
  const crumbs = [{ label: ds.dims[ds.meta.default_dimension ?? ds.dimIds[0]].root.label, path: "" }];
  segments.forEach((s, i) => {
    crumbs.push({ label: ds.dims[s.dim].byCode.get(s.code).label, path: formatPath(segments.slice(0, i + 1)), dim: s.dim });
  });
  return crumbs;
}

// Dimensions the current node can still be split by (a dimension whose selected node is a leaf cannot).
export function splittableDims(ds, state) {
  const sel = selection(ds, parsePath(state.path ?? ""));
  return ds.dimIds
    .filter((d) => ds.dims[d].byCode.get(sel[d] ?? ds.dims[d].root.code).children.length > 0)
    .map((d) => ({ id: d, label: ds.dims[d].label }));
}

// ---- time series ------------------------------------------------------------------------------------
// SeriesSet = { title, unit, claim_level, series: [{id, label, other?, values: [{period, value, status, claim}]}],
//               breaks: [{period, note}], periods: [...] }
export function timeline(ds, state) {
  const segments = parsePath(state.path ?? "");
  const dim = state.dim ?? ds.meta.default_dimension ?? ds.dimIds[0];
  const unit = state.unit ?? BUILTIN_UNITS.raw;
  const sel = selection(ds, segments);
  const base = sel[dim] ?? ds.dims[dim].root.code;
  const series = [];
  for (const k of ds.dims[dim].byCode.get(base).children) {
    const childSel = { ...sel, [dim]: k.code };
    const values = ds.periods.map((period) => {
      const agg = aggregate(ds, childSel, period);
      const parent = aggregate(ds, sel, period).value;
      const total = aggregate(ds, {}, period).value;
      return { period, raw: agg.value, status: agg.status ?? ds.statusByPeriod[period], claim: agg.claim,
               value: toUnit(agg.value, unit, { parentValue: parent, totalValue: total, denominators: state.denominators, period }) };
    });
    series.push({ id: k.code, label: k.label, other: !!k.other, path: formatPath([...segments, { dim, code: k.code }]), values });
  }
  return { title: ds.meta.title, unit: unitLabel(ds, unit), claim_level: ds.meta.claim_level, series, breaks: ds.meta.breaks ?? [], periods: ds.periods };
}

// Plain series JSON (data/<topic>/<series>.json) -> one SeriesSet line.
export function seriesLine(json) {
  return {
    id: json.id, label: json.title, claim_level: json.claim_level, unit: json.unit, breaks: json.breaks ?? [],
    values: json.values.map((v) => ({ period: v.period, value: v.value, raw: v.value, status: v.status ?? null, claim: v.claim_level ?? json.claim_level })),
  };
}

export function seriesSet(title, jsons, opts = {}) {
  const series = jsons.map(seriesLine);
  (opts.labels ?? []).forEach((label, i) => { if (series[i] && label) series[i].label = label; });
  const periods = [...new Set(series.flatMap((s) => s.values.map((v) => v.period)))].sort();
  return { title, unit: opts.unit ?? jsons[0].unit, claim_level: opts.claim_level ?? jsons[0].claim_level, series,
           breaks: series.flatMap((s) => s.breaks), periods };
}
