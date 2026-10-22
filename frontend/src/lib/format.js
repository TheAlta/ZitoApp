// Persian number, date and progress helpers (same output as the design demo).
const numberFormat = new Intl.NumberFormat("fa-IR", { useGrouping: true });
const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

export const fa = (value) =>
  typeof value === "number" ? numberFormat.format(value) : String(value ?? "").replace(/[0-9]/g, (d) => FA_DIGITS[+d]);

export const pct = (value) => `${fa(Math.round(value))}٪`;

export function normDigits(text) {
  return String(text ?? "")
    .replace(/[۰-۹]/g, (d) => String(FA_DIGITS.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String("٠١٢٣٤٥٦٧٨٩".indexOf(d)));
}

export function normPhone(text) {
  const match = normDigits(text).replace(/[\s-]/g, "").match(/^(?:\+98|0098|98|0)?(9\d{9})$/);
  return match ? `0${match[1]}` : null;
}

const jalaliFormat = new Intl.DateTimeFormat("fa-IR-u-ca-persian", { day: "numeric", month: "long", year: "numeric" });

export function jalali(date) {
  const parts = jalaliFormat.formatToParts(new Date(date));
  const part = (type) => parts.find((p) => p.type === type)?.value ?? "";
  return `${part("day")} ${part("month")} ${part("year")}`;
}

export const clock = (date) =>
  new Intl.DateTimeFormat("fa-IR", { hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(date));

export function ago(date, now = Date.now()) {
  const seconds = Math.max(0, Math.round((now - new Date(date).getTime()) / 1000));
  if (seconds < 45) return "همین الان";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${fa(minutes)} دقیقه پیش`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${fa(hours)} ساعت پیش`;
  const days = Math.round(hours / 24);
  return days < 30 ? `${fa(days)} روز پیش` : jalali(date);
}

export const secs = (ms) => `${fa(Math.max(1, Math.round(ms / 1000)))} ثانیه`;

function hash(text) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export function seeded(seed) {
  let state = seed || 1;
  return () => {
    state |= 0;
    state = (state + 1831565813) | 0;
    let x = Math.imul(state ^ (state >>> 15), 1 | state);
    x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x;
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
}

export const hashOf = hash;

// Stable per-viewer shuffle (used for scenario options in lessons).
export function shuffle(items, a, b) {
  const rand = seeded(hash(`${a}|${b}`));
  const out = items.slice();
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

// A course hue for covers when the server gives none: stable per course id.
export const hueOf = (id) => (hash(String(id)) % 300) + 10;
