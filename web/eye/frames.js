// Frame sender (whitepaper §7.3): the eye page shares the phone's raw camera feed with the vision service.
// A few times a second the raw stream is drawn into a small canvas, encoded as JPEG and published on
// `camera.frame` {jpeg (base64, no data: prefix), w, h, t} (C3). The vision service (python -m vision) turns
// those frames into `vision.state`: the objects and giants the robot can see. `t` is this page's clock
// (performance.now) when the frame was grabbed; vision echoes it as `client_ts` so the local renderer
// knows exactly how old each state is.
//
// Frames only exist in memory and on the hub socket; nothing is stored. The hub only delivers
// `camera.frame` to clients that ask for it by name, so other pages never receive them.

export const TOPIC = "camera.frame";
export const DEFAULT_HZ = 10;
export const DEFAULT_WIDTH = 640;
export const JPEG_QUALITY = 0.7;

/** Output size for a source of `vw`x`vh` scaled to `width` (never upscaled), both even integers. */
export function frameSize(vw, vh, width = DEFAULT_WIDTH) {
  if (!(vw > 0 && vh > 0)) return null;
  const w = Math.min(width, vw);
  const h = Math.round((w * vh) / vw);
  return [Math.max(2, Math.round(w / 2) * 2), Math.max(2, Math.round(h / 2) * 2)];
}

/** "data:image/jpeg;base64,AAAA" -> "AAAA" (or null if it isn't a JPEG data URL). */
export function stripDataUrl(url) {
  const m = /^data:image\/jpeg;base64,(.+)$/.exec(String(url ?? ""));
  return m ? m[1] : null;
}

/**
 * Start publishing frames from `video` (an element playing the raw stream).
 * @param {{pub: Function}} hub
 * @param {HTMLVideoElement} video
 * @param {object} [o]  hz, width, quality; test seams: canvas, setInterval, clearInterval, now
 * @returns {{stop(): void, sent(): number}}
 */
export function startFrameSender(hub, video, o = {}) {
  const hz = o.hz > 0 ? o.hz : DEFAULT_HZ;
  const width = o.width > 0 ? o.width : DEFAULT_WIDTH;
  const quality = o.quality ?? JPEG_QUALITY;
  const canvas = o.canvas ?? video.ownerDocument.createElement("canvas");
  const setI = o.setInterval ?? globalThis.setInterval.bind(globalThis);
  const clearI = o.clearInterval ?? globalThis.clearInterval.bind(globalThis);
  const now = o.now ?? (() => performance.now());
  const ctx = canvas.getContext("2d");
  let count = 0;

  function tick() {
    if (video.readyState < 2) return; // HAVE_CURRENT_DATA: nothing to draw yet
    const size = frameSize(video.videoWidth, video.videoHeight, width);
    if (!size) return;
    const [w, h] = size;
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    try {
      const t = Math.round(now() * 10) / 10;
      ctx.drawImage(video, 0, 0, w, h);
      const jpeg = stripDataUrl(canvas.toDataURL("image/jpeg", quality));
      if (!jpeg) return;
      hub.pub(TOPIC, { jpeg, w, h, t });
      count++;
    } catch (e) {
      console.warn("[frames] could not grab a frame:", e.message);
    }
  }

  const timer = setI(tick, Math.round(1000 / hz));
  return {
    stop() { clearI(timer); },
    sent() { return count; },
    tick, // exposed for tests
  };
}
