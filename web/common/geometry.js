// View geometry helpers for browser pages (T06, contracts C1/C9).
// View coords are normalised [x, y] in 0..1 of the robot camera's frame, origin top-left, y down.

/** View coords -> pixels in `rect` ({x, y, width, height}; a DOMRect works; x/y default to 0). */
export function toScreen([x, y], rect) {
  return [(rect.x || 0) + x * rect.width, (rect.y || 0) + y * rect.height];
}

export function fromScreen([px, py], rect) {
  return [(px - (rect.x || 0)) / rect.width, (py - (rect.y || 0)) / rect.height];
}

export function dist(a, b) {
  return Math.hypot(b[0] - a[0], b[1] - a[1]);
}

export function angleTo(a, b) {
  return Math.atan2(b[1] - a[1], b[0] - a[0]);
}

/** Angle (radians) from straight ahead to view x, for a camera with horizontal field of view `hfovDeg`. */
export function bearing(x, hfovDeg) {
  const half = (hfovDeg * Math.PI) / 360;
  return Math.atan((2 * x - 1) * Math.tan(half));
}
