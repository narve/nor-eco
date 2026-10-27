// Norwegian number formatting. Twin of transform/format.py (same rounding: half away from zero on the
// shortest decimal representation). tests/e2e/test_engine.py checks that both give the same strings.
export const NBSP = " ";
export const MINUS = "−";

// Round a non-negative finite number to `places` decimals, returning a plain decimal string.
function roundDecimal(x, places) {
  let s = String(x);
  if (/e/i.test(s)) s = x.toFixed(Math.max(places, 20)); // exponent form only for very large/small values
  let [whole, frac = ""] = s.split(".");
  if (frac.length <= places) return places ? whole + "." + frac.padEnd(places, "0") : whole;
  const roundUp = frac.charCodeAt(places) >= 53; // digit >= 5
  let digits = (whole + frac.slice(0, places)).split("").map(Number);
  if (roundUp) {
    let i = digits.length - 1;
    while (i >= 0) {
      if (digits[i] === 9) { digits[i] = 0; i--; } else { digits[i]++; break; }
    }
    if (i < 0) digits.unshift(1);
  }
  const str = digits.join("");
  const w = str.slice(0, str.length - places) || "0";
  return places ? w + "." + str.slice(str.length - places) : w;
}

export function fmt(value, decimals = null, { sign = false } = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  const places = decimals === null ? 2 : decimals;
  let text = roundDecimal(Math.abs(value), places);
  if (decimals === null && text.includes(".")) text = text.replace(/0+$/, "").replace(/\.$/, "");
  let [whole, frac] = text.split(".");
  whole = whole.replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);
  const out = whole + (frac ? "," + frac : "");
  const isZero = !/[1-9]/.test(text);
  if (value < 0 && !isZero) return MINUS + out;
  if (sign && value > 0) return "+" + out;
  return out;
}

const MONTHS = ["januar", "februar", "mars", "april", "mai", "juni", "juli", "august", "september", "oktober", "november", "desember"];
// '2025' -> '2025'; '2026-06' -> '30. juni 2026' (end of the month). Twin of build.period_label.
export function periodLabel(period) {
  if (/^\d{4}-\d{2}$/.test(period)) {
    const y = +period.slice(0, 4), m = +period.slice(5);
    return `${new Date(y, m, 0).getDate()}. ${MONTHS[m - 1]} ${y}`;
  }
  return period;
}
