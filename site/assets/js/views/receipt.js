// receipt: the parts of one node as a list of lines with dotted leaders and a sum line, like a till receipt.
// Meant for «per innbygger» values, but works for any unit. Each line is a button: a second press opens the part.
import { put, h, fill, valueText, decimalsFor, isPreliminary, CLAIM_LABEL, STATUS_LABEL } from "./common.js";
import { kidsOf } from "./hierarchy.js";
import { fmt } from "../core/format.js";

export function renderReceipt(container, node, opts = {}) {
  const { onDrill = () => {}, canDrill = () => false } = opts;
  container.replaceChildren();
  const lines = kidsOf(node).filter((n) => n.value !== null);
  if (!lines.length) { put(container, h("p", { class: "muted" }, "Ingen undernivå som kan vises.")); return { destroy() {} }; }
  const dec = decimalsFor(node.unit, lines.map((n) => n.value));
  const sum = lines.reduce((a, n) => a + n.value, 0);
  const mark = (n) => (n.claim_level === "utledet" ? " ƒ" : n.claim_level === "estimat" ? " ≈" : isPreliminary(n.status) ? " *" : "");
  const rows = lines.map((n) => h("li", { class: `rc-line claim-${n.claim_level}${n === node.other ? " is-other" : ""}` },
    h("button", { type: "button", class: "rc-btn", disabled: !canDrill(n), onclick: () => onDrill(n.path), "aria-label": `${n.label}: ${valueText(n.value, n.unit, dec)}` },
      h("span", { class: "rc-name" }, n.label, mark(n)), h("span", { class: "rc-dots", "aria-hidden": "true" }), h("span", { class: "num rc-val" }, fmt(n.value, dec)))));
  put(container, h("div", { class: "receipt" },
    h("p", { class: "rc-head mono" }, node.label), h("ul", { class: "rc-lines", role: "list" }, rows),
    h("p", { class: "rc-sum" }, h("span", {}, "Sum"), h("span", { class: "rc-dots", "aria-hidden": "true" }), h("span", { class: "num rc-val" }, fmt(sum, dec))),
    h("p", { class: "rc-unit muted small" }, `Enhet: ${node.unit}. `, lines.some((n) => isPreliminary(n.status)) ? "* foreløpig tall, budsjett eller anslag. " : null,
      lines.some((n) => n.claim_level === "utledet") ? "ƒ utledet. " : null, lines.some((n) => n.claim_level === "estimat") ? "≈ estimat. " : null)));
  return { destroy() { container.replaceChildren(); } };
}
