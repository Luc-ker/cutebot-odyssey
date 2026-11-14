// Colour words → RGB for lights and map tints (T02, contract C9).
// colourFor(word): exact match, then last-word match ("storm grey" → "grey"), else a neutral default.

export const NEUTRAL = [128, 128, 128];

let table = null;
let loading = null;

export function setColours(colours) {
  table = normalise(colours);
}

function normalise(colours) {
  const out = new Map();
  for (const [k, v] of Object.entries(colours)) out.set(clean(k), v);
  return out;
}

function clean(word) {
  return String(word ?? "").toLowerCase().replace(/[-_]/g, " ").replace(/\s+/g, " ").trim();
}

async function load(url) {
  if (table) return table;
  if (!loading) {
    loading = fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(`colours fetch failed: ${r.status}`);
        return r.json();
      })
      .then((d) => (table = normalise(d.colours || d)))
      .finally(() => (loading = null));
  }
  return loading;
}

export function lookupColour(word, colours = table) {
  if (!colours) return NEUTRAL.slice();
  const w = clean(word);
  if (colours.has(w)) return colours.get(w).slice();
  const last = w.split(" ").pop();
  if (last && colours.has(last)) return colours.get(last).slice();
  return NEUTRAL.slice();
}

export async function colourFor(word, url = "/shared/colours.json") {
  try {
    await load(url);
  } catch {
    return NEUTRAL.slice();
  }
  return lookupColour(word);
}
