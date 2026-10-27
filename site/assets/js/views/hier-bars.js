// hier-bars: one level at a time. Sorted horizontal bars for the children of the current node, with the
// parent total as a reference bar on top. «Øvrig / ikke fordelt» is always last, always grey, never hidden.
// Bars start at zero (or at a visible zero line when values are negative). HTML/CSS, so it scales with the
// container and works with touch: a tap selects a row (readout below), a second tap on it drills.
import { h, colorVar, isPreliminary, valueText, decimalsFor, CLAIM_LABEL, STATUS_LABEL } from "./common.js";
import { fmt } from "../core/format.js";

export function renderHierBars(container, node, opts = {}) {
  const { onDrill = () => {}, canDrill = () => false, selected = null } = opts;
  container.replaceChildren();
  const rows = [...(node.children ?? [])].sort((a, b) => Math.abs(b.value ?? 0) - Math.abs(a.value ?? 0));
  if (node.other) rows.push(node.other);
  if (!rows.length) {
    container.append(h("p", { class: "muted" }, "Ingen undernivå på dette punktet."));
    return { destroy() {} };
  }
  const values = [node.value, ...rows.map((r) => r.value)].filter((v) => v !== null);
  const dmin = Math.min(0, ...values), dmax = Math.max(0, ...values);
  const range = dmax - dmin || 1;
  const dec = decimalsFor(node.unit, values);
  const pctOfParent = (r) => (node.raw ? (100 * r.raw) / node.raw : null);

  const track = (n, i, other) => {
    const left = ((Math.min(0, n.value ?? 0) - dmin) / range) * 100;
    const width = (Math.abs(n.value ?? 0) / range) * 100;
    const cls = ["hb-bar", `claim-${n.claim_level}`, isPreliminary(n.status) ? "is-prelim" : ""].join(" ");
    return h("span", { class: "hb-track", "aria-hidden": "true" },
      dmin < 0 ? h("span", { class: "hb-zero", style: `left:${((0 - dmin) / range) * 100}%` }) : null,
      h("span", { class: cls, style: `left:${left}%;width:${width}%;--bar:${colorVar(i, other)}` }));
  };

  const ref = h("div", { class: "hb-ref" },
    h("span", { class: "hb-label" }, node.label, h("span", { class: "hb-sub" }, " (= alle undernivå samlet)")),
    h("span", { class: "hb-value num" }, valueText(node.value, node.unit, dec)),
    track(node, 0, true));

  const list = h("ul", { class: "hb-list", role: "list" });
  const readout = h("div", { class: "readout", "aria-live": "polite" });
  let sel = selected;

  const showReadout = (r) => {
    const share = node.unit === "prosent" ? null : pctOfParent(r);
    readout.replaceChildren(
      h("strong", {}, r.label), ": ",
      h("span", { class: "num" }, valueText(r.value, r.unit, dec)),
      share !== null && r.value !== null ? h("span", { class: "muted" }, ` (${fmt(share, 1)} % av ${node.label})`) : null,
      " ", h("span", { class: `claim claim-${r.claim_level}` }, CLAIM_LABEL[r.claim_level]),
      isPreliminary(r.status) ? h("span", { class: "muted" }, ` · ${STATUS_LABEL[r.status]}`) : null,
      canDrill(r) ? h("button", { type: "button", class: "btn", onclick: () => onDrill(r.path) }, "Åpne ›") : null,
    );
  };

  rows.forEach((r, i) => {
    const other = r === node.other;
    const drillable = canDrill(r);
    const btn = h("button", {
      type: "button", class: "hb-row" + (other ? " is-other" : ""), "data-path": r.path,
      "aria-label": `${r.label}: ${valueText(r.value, r.unit, dec)}${drillable ? ". Trykk to ganger for å åpne." : ""}`,
      "aria-pressed": String(sel === r.path),
      onclick: () => {
        if (sel === r.path && drillable) { onDrill(r.path); return; }
        sel = r.path;
        list.querySelectorAll(".hb-row").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.path === sel)));
        showReadout(r);
      },
    },
      h("span", { class: "hb-label" }, r.label, drillable ? h("span", { class: "hb-more", "aria-hidden": "true" }, " ›") : null),
      h("span", { class: "hb-value num" }, valueText(r.value, r.unit, dec)),
      track(r, i, other));
    list.append(h("li", {}, btn));
  });

  container.append(ref, list, readout);
  const current = rows.find((r) => r.path === sel);
  if (current) showReadout(current);
  else readout.append(h("span", { class: "muted" }, "Trykk på en søyle for detaljer."));
  return { destroy() { container.replaceChildren(); } };
}
