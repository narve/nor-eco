// Small DOM helpers shared by the views. No framework.
import { fmt } from "../core/format.js";

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "text") el.textContent = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) el.append(c.nodeType ? c : document.createTextNode(c));
  return el;
}

// Replace an element's children, skipping null/undefined/false. The DOM's own replaceChildren turns null into the
// text «null», so optional parts must go through this (or through h()).
export function fill(el, ...children) {
  el.replaceChildren(...children.flat().filter((c) => c !== null && c !== undefined && c !== false));
}

const SVG = "http://www.w3.org/2000/svg";
export function s(tag, attrs = {}, ...children) {
  const el = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== null && v !== undefined) el.setAttribute(k, v);
  for (const c of children.flat()) if (c) el.append(c);
  return el;
}

// Size comes from the container, not the window, so the same module works on pages, in the gallery and fullscreen.
export function observeSize(el, cb) {
  let last = 0;
  const ro = new ResizeObserver((entries) => {
    const w = Math.round(entries[0].contentRect.width);
    if (w && w !== last) { last = w; cb(w); }
  });
  ro.observe(el);
  return () => ro.disconnect();
}

export const PRELIMINARY = new Set(["foreløpig", "anslag", "vedtatt", "budsjett", "forslag"]);
export const isPreliminary = (status) => PRELIMINARY.has(status);

// Categorical colour for series i; «Øvrig / ikke fordelt» is always the same neutral grey.
export const colorVar = (i, other = false) => (other ? "var(--other)" : `var(--c${(i % 8) + 1})`);

export const CLAIM_LABEL = { offisiell: "Offisielt tall", utledet: "Utledet", estimat: "Estimat" };
export const STATUS_LABEL = { foreløpig: "foreløpig", anslag: "anslag", vedtatt: "vedtatt", saldert: "saldert", regnskap: "regnskap", budsjett: "budsjett", forslag: "forslag" };

// «5 511,3 mrd. kr»
export function valueText(value, unit, decimals = 1) {
  if (value === null || value === undefined) return "ikke tilgjengelig";
  return `${fmt(value, decimals)}${unit === "prosent" ? " %" : " " + unit}`;
}

export function decimalsFor(unit, values) {
  if (unit === "prosent") return 1;
  const real = values.filter((v) => v !== null && v !== undefined);
  if (real.length && real.every(Number.isInteger)) return 0; // counts published as whole numbers stay whole
  if (unit.startsWith("kr per") || unit === "personer") return 0;
  const m = Math.max(0, ...values.filter((v) => v !== null).map(Math.abs));
  return m >= 1000 ? 0 : m >= 100 ? 1 : 2;
}
