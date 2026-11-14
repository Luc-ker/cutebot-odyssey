// Table geometry helpers for browser pages (T06, contracts C1/C9).
// Table coords are normalised [x, y] in 0..1, origin top-left, y down.

let tableAspect = 1.5; // TABLE_W_CM / TABLE_H_CM; call setTableSize() with the real config values.

export function setTableSize(wCm, hCm) {
  if (wCm > 0 && hCm > 0) tableAspect = wCm / hCm;
}

export function getTableAspect() {
  return tableAspect;
}

// The largest rect with the table's aspect ratio, centred (letterboxed) inside `rect`.
// `rect` is {x, y, width, height} (a DOMRect works); x/y default to 0.
export function fitRect(rect, aspect = tableAspect) {
  const rx = rect.x || 0;
  const ry = rect.y || 0;
  const rw = rect.width;
  const rh = rect.height;
  let w = rw;
  let h = rw / aspect;
  if (h > rh) {
    h = rh;
    w = rh * aspect;
  }
  return { x: rx + (rw - w) / 2, y: ry + (rh - h) / 2, width: w, height: h };
}

export function toScreen([x, y], rect, aspect = tableAspect) {
  const r = fitRect(rect, aspect);
  return [r.x + x * r.width, r.y + y * r.height];
}

export function fromScreen([px, py], rect, aspect = tableAspect) {
  const r = fitRect(rect, aspect);
  return [(px - r.x) / r.width, (py - r.y) / r.height];
}

export function dist(a, b) {
  return Math.hypot(b[0] - a[0], b[1] - a[1]);
}

export function angleTo(a, b) {
  return Math.atan2(b[1] - a[1], b[0] - a[0]);
}
