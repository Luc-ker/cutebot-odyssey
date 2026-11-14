// Shared config loader for browser pages (T01, contract C9/C10).
// Fetches /shared/config.json once and caches it; concurrent callers share one fetch.

let cached = null;

export function loadConfig(url = "/shared/config.json") {
  if (!cached) {
    cached = fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`config fetch failed: ${res.status}`);
        return res.json();
      })
      .then((raw) => {
        const cfg = {};
        for (const [k, v] of Object.entries(raw)) if (!k.startsWith("_")) cfg[k] = v;
        return cfg;
      })
      .catch((err) => {
        cached = null; // allow a retry after a failed fetch
        throw err;
      });
  }
  return cached;
}

// Test helper: forget the cached config.
export function _resetConfigCache() {
  cached = null;
}
