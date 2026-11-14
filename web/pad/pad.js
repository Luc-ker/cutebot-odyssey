// Phone controller for the Cutebot over Bluetooth (Web Bluetooth, Chrome on Android or a laptop).
// Talks to firmware/makecode/cutebot_bluetooth.ts through the micro:bit's Bluetooth UART service, with the
// same text packets as contract C6: D (drive), L (lights), H (horn); the robot answers with T (distance).
//
// Everything here is free of page DOM so it can be tested with fakes; index.html wires it to the screen.

// micro:bit Bluetooth UART service. Of its two characteristics, one is written by us and one notifies us;
// which is which is read from their properties rather than assumed from the UUIDs.
export const UART_SERVICE = "6e400001-b5a3-f393-e0a9-e50e24dcca9e";
export const UART_CHARS = ["6e400002-b5a3-f393-e0a9-e50e24dcca9e", "6e400003-b5a3-f393-e0a9-e50e24dcca9e"];
export const NAME_PREFIX = "BBC micro:bit";

export const DRIVE_HZ = 20;       // the robot stops if it hears nothing for 300 ms
export const DEAD_ZONE = 0.12;
export const TURN_SCALE = 0.75;   // full sideways is a brisk turn, not a spin at full speed
const CHUNK = 20;                 // bytes per Bluetooth write (the default BLE packet size)

/** Stick position (x right, y up, each -1..1) -> {throttle, turn} as integers -100..100. */
export function stickToDrive(x, y) {
  const shape = (v) => {
    const a = Math.min(1, Math.abs(v));
    if (a < DEAD_ZONE) return 0;
    const k = (a - DEAD_ZONE) / (1 - DEAD_ZONE);
    return Math.sign(v) * (0.6 * k + 0.4 * k * k);   // gentle near the centre, full at the edge
  };
  return {
    throttle: Math.round(shape(y) * 100) || 0,
    turn: Math.round(shape(x) * 100 * TURN_SCALE) || 0,
  };
}

const clampInt = (v, lo, hi) => Math.max(lo, Math.min(hi, Math.round(Number(v) || 0)));

export function drivePacket(throttle, turn, seq) {
  return `D,${clampInt(throttle, -100, 100)},${clampInt(turn, -100, 100)},${clampInt(seq, 0, 1e9) % 256}\n`;
}

/** mode "S" keeps the colour; "F" or "P" shows it for `ms` then goes back. */
export function lightPacket([r, g, b], mode = "S", ms = 0) {
  const m = ["S", "F", "P"].includes(mode) ? mode : "S";
  return `L,${m},${clampInt(r, 0, 255)},${clampInt(g, 0, 255)},${clampInt(b, 0, 255)},${clampInt(ms, 0, 5000)}\n`;
}

export const HORN = "H\n";

/** "T,<cm>,<l>,<r>,<blocked>" -> {distance_cm, blocked}, or null for anything else. */
export function parseTelemetry(line) {
  const f = String(line ?? "").trim().split(",");
  if (f[0] !== "T" || f.length < 5) return null;
  const d = Number.parseInt(f[1], 10);
  if (!Number.isFinite(d)) return null;
  return { distance_cm: d >= 999 ? null : d, blocked: f[4] === "1" };
}

/** Split text into Bluetooth-sized byte chunks. */
export function chunks(text, size = CHUNK) {
  const bytes = new TextEncoder().encode(text);
  const out = [];
  for (let i = 0; i < bytes.length; i += size) out.push(bytes.slice(i, i + size));
  return out;
}

/**
 * The Bluetooth link. One write at a time (the browser rejects overlapping writes); a newer drive packet
 * replaces one still waiting, so the robot always gets the latest stick position, never a backlog.
 * @param {object} o
 * @param {Bluetooth} o.bluetooth        navigator.bluetooth
 * @param {(s: string, detail?: string) => void} [o.onStatus]  "connecting" | "connected" | "disconnected" | "error"
 * @param {(line: string) => void} [o.onLine]                  each line the robot sends
 */
export function createLink({ bluetooth, onStatus = () => {}, onLine = () => {} }) {
  let device = null;
  let tx = null;            // characteristic we write to
  let queue = [];           // [{text, drive}]
  let writing = false;
  let rxBuf = "";
  let wantConnected = false;

  const status = (s, detail) => onStatus(s, detail);

  async function pump() {
    if (writing) return;
    writing = true;
    try {
      while (queue.length && tx) {
        const { text } = queue.shift();
        for (const part of chunks(text)) {
          if (tx.writeValueWithoutResponse) await tx.writeValueWithoutResponse(part);
          else await tx.writeValue(part);
        }
      }
    } catch (e) {
      queue = [];
      status("error", e.message);
    } finally {
      writing = false;
    }
  }

  function onNotify(event) {
    rxBuf += new TextDecoder().decode(event.target.value);
    let i;
    while ((i = rxBuf.indexOf("\n")) >= 0) {
      const line = rxBuf.slice(0, i).replace(/\r$/, "");
      rxBuf = rxBuf.slice(i + 1);
      if (line) onLine(line);
    }
    if (rxBuf.length > 200) rxBuf = "";
  }

  async function attach() {
    status("connecting", device.name);
    const server = await device.gatt.connect();
    const service = await server.getPrimaryService(UART_SERVICE);
    const chars = await Promise.all(UART_CHARS.map((u) => service.getCharacteristic(u)));
    tx = chars.find((c) => c.properties.write || c.properties.writeWithoutResponse) ?? null;
    const rx = chars.find((c) => c.properties.notify || c.properties.indicate) ?? null;
    if (!tx) throw new Error("the robot's Bluetooth UART can't be written to");
    if (rx) {
      rx.addEventListener("characteristicvaluechanged", onNotify);
      await rx.startNotifications();
    }
    status("connected", device.name);
  }

  async function onDisconnected() {
    tx = null;
    queue = [];
    if (!wantConnected) return status("disconnected");
    status("connecting", "reconnecting…");
    for (let attempt = 0; attempt < 3 && wantConnected; attempt++) {
      try {
        await attach();
        return;
      } catch {
        await new Promise((r) => setTimeout(r, 800));
      }
    }
    wantConnected = false;
    status("disconnected", "lost the robot");
  }

  return {
    get connected() { return !!tx; },
    get name() { return device?.name ?? null; },

    async connect() {
      if (!bluetooth) throw new Error("Web Bluetooth isn't available in this browser");
      device = await bluetooth.requestDevice({
        filters: [{ namePrefix: NAME_PREFIX }],
        optionalServices: [UART_SERVICE],
      });
      device.addEventListener("gattserverdisconnected", onDisconnected);
      wantConnected = true;
      try {
        await attach();
      } catch (e) {
        wantConnected = false;
        tx = null;
        status("error", e.message);
        throw e;
      }
    },

    send(text, { drive = false } = {}) {
      if (!tx) return false;
      if (drive) {
        const i = queue.findIndex((q) => q.drive);
        if (i >= 0) queue[i] = { text, drive };
        else queue.push({ text, drive });
      } else {
        queue.push({ text, drive });
      }
      pump();
      return true;
    },

    disconnect() {
      wantConnected = false;
      if (device?.gatt?.connected) device.gatt.disconnect();
    },
  };
}
