// waterfall: a running total built step by step. Rows read top to bottom (works the same on a phone and on a
// desktop): label, signed step value, and a floating bar from the running total before the step to the total
// after it. Totals are checkpoints: if the steps above do not add up to a published total, a visible
// «Ikke forklart» step is inserted with the difference, never absorbed into another step.
import { h, isPreliminary, valueText, CLAIM_LABEL, STATUS_LABEL } from "./common.js";
import { fmt } from "../core/format.js";

// steps: [{label, value, role: "start"|"delta"|"total", expected?, claim, status, note}] -> rows with running totals
export function buildRows(steps, tol = 0.05) {
  const rows = [];
  let run = 0;
  for (const s of steps) {
    if (s.role === "start") {
      run = s.value;
      rows.push({ ...s, from: 0, to: run, run });
    } else if (s.role === "delta") {
      rows.push({ ...s, from: run, to: run + s.value, run: run + s.value });
      run += s.value;
    } else {
      const expected = s.expected ?? run;
      if (Math.abs(expected - run) > tol) {
        // the steps above do not reach the published total: show the gap as its own step
        rows.push({ label: "Ikke forklart", role: "delta", value: expected - run, from: run, to: expected, run: expected, claim: "utledet", residual: true,
                    status: s.status, note: "Differansen mellom summen av trinnene og det publiserte tallet." });
        run = expected;
      }
      rows.push({ ...s, value: run, from: 0, to: run, run });
    }
  }
  return rows;
}

export function renderWaterfall(container, steps, opts = {}) {
  const { unit = "mrd. kr", decimals = 1 } = opts;
  container.replaceChildren();
  const rows = buildRows(steps, opts.tol);
  const extents = rows.flatMap((r) => [r.from, r.to]);
  const dmin = Math.min(0, ...extents), dmax = Math.max(0, ...extents);
  const range = dmax - dmin || 1;
  const pos = (v) => ((v - dmin) / range) * 100;

  const list = h("ol", { class: "wf-list" });
  rows.forEach((r, i) => {
    const lo = Math.min(r.from, r.to), hi = Math.max(r.from, r.to);
    const isTotal = r.role !== "delta";
    const kind = isTotal ? "total" : r.value >= 0 ? "up" : "down";
    const cls = ["wf-bar", `wf-${kind}`, r.residual ? "wf-residual" : "", `claim-${r.claim ?? "offisiell"}`, isPreliminary(r.status) ? "is-prelim" : ""].join(" ");
    const signed = isTotal ? valueText(r.value, unit, decimals) : `${r.value >= 0 ? "+" : ""}${valueText(r.value, unit, decimals)}`;
    const next = rows[i + 1];
    list.append(h("li", { class: `wf-row${isTotal ? " is-total" : ""}${r.residual ? " is-residual" : ""}`,
      "aria-label": `${r.label}: ${signed}. Sum etter steget: ${valueText(r.run, unit, decimals)}.` },
      h("span", { class: "wf-label" }, r.label,
        r.claim && r.claim !== "offisiell" ? h("span", { class: `claim claim-${r.claim}` }, CLAIM_LABEL[r.claim]) : null,
        isPreliminary(r.status) ? h("span", { class: "muted small" }, ` ${STATUS_LABEL[r.status]}`) : null),
      h("span", { class: "wf-value num" }, signed),
      h("span", { class: "wf-track", "aria-hidden": "true" },
        dmin < 0 ? h("span", { class: "wf-zero", style: `left:${pos(0)}%` }) : null,
        h("span", { class: cls, style: `left:${pos(lo)}%;width:${Math.max(0.4, pos(hi) - pos(lo))}%` }),
        // connector: where the running total continues into the next row
        next ? h("span", { class: "wf-link", style: `left:${pos(r.run)}%` }) : null),
      r.note ? h("span", { class: "wf-note muted small" }, r.note) : null));
  });
  container.append(list, h("p", { class: "muted small wf-foot" },
    "Hvert trinn er forskjellen fra sum før trinnet. Søylene starter ved null (strek ved null når tallene er negative)."));
  return { destroy() { container.replaceChildren(); }, rows };
}
