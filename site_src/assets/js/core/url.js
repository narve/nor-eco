// URL view state. One grammar everywhere (see docs/PLAN.md):
//   ?chart=<id>&view=<view-id>&year=<yyyy>&year2=<yyyy (comparison views)>&unit=<unit-id>&status=<s>&def=<definition-id>&path=<dim>:<code>/<dim>:<code>&dim=<dim>
// Several charts can share a page; only the chart named by `chart` reads or writes the state.

export function parsePath(path) {
  if (!path) return [];
  return path.split("/").filter(Boolean).map((seg) => {
    const i = seg.indexOf(":");
    if (i < 1) throw new Error(`bad path segment '${seg}'`);
    return { dim: seg.slice(0, i), code: seg.slice(i + 1) };
  });
}

export function formatPath(segments) {
  return segments.map((s) => `${s.dim}:${s.code}`).join("/");
}

export function readState(chartId, search = location.search) {
  const p = new URLSearchParams(search);
  if (p.get("chart") !== chartId) return {};
  const out = {};
  for (const k of ["view", "year", "year2", "unit", "status", "def", "path", "dim"]) if (p.has(k)) out[k] = p.get(k);
  return out;
}

export function writeState(chartId, state, { replace = false } = {}) {
  const p = new URLSearchParams();
  p.set("chart", chartId);
  for (const k of ["view", "year", "year2", "unit", "status", "def", "path", "dim"]) {
    if (state[k] !== undefined && state[k] !== null && state[k] !== "") p.set(k, state[k]);
  }
  const url = `${location.pathname}?${p.toString()}${location.hash}`;
  (replace ? history.replaceState : history.pushState).call(history, { chart: chartId, ...state }, "", url);
}
