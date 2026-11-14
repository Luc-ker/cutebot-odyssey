import test from "node:test";
import assert from "node:assert/strict";
import {
  UART_CHARS, UART_SERVICE, chunks, createLink, drivePacket, lightPacket, parseTelemetry, stickToDrive,
} from "./pad.js";

test("stick: centre and dead zone are still, full forward is full throttle", () => {
  assert.deepEqual(stickToDrive(0, 0), { throttle: 0, turn: 0 });
  assert.deepEqual(stickToDrive(0.05, -0.08), { throttle: 0, turn: 0 });
  assert.deepEqual(stickToDrive(0, 1), { throttle: 100, turn: 0 });
  assert.deepEqual(stickToDrive(0, -1), { throttle: -100, turn: 0 });
  const right = stickToDrive(1, 0);
  assert.ok(right.turn > 0 && right.turn <= 75 && right.throttle === 0);
  assert.ok(stickToDrive(0, 0.5).throttle < 50, "gentle curve near the centre");
});

test("packets match contract C6 and stay inside their ranges", () => {
  assert.equal(drivePacket(50, -20, 7), "D,50,-20,7\n");
  assert.equal(drivePacket(250, -300, 257), "D,100,-100,1\n");
  assert.equal(lightPacket([255, 0, 0], "F", 600), "L,F,255,0,0,600\n");
  assert.equal(lightPacket([300, -1, 10], "X"), "L,S,255,0,10,0\n");
  for (const p of [drivePacket(-100, -100, 255), lightPacket([255, 255, 255], "P", 5000)]) {
    assert.ok(p.length - 1 <= 32, p);
  }
});

test("telemetry parsing", () => {
  assert.deepEqual(parseTelemetry("T,23,0,0,0"), { distance_cm: 23, blocked: false });
  assert.deepEqual(parseTelemetry("T,6,0,0,1\r"), { distance_cm: 6, blocked: true });
  assert.deepEqual(parseTelemetry("T,999,0,0,0"), { distance_cm: null, blocked: false });
  assert.equal(parseTelemetry("D,1,2,3"), null);
  assert.equal(parseTelemetry("T,abc,0,0,0"), null);
});

test("chunks split into 20-byte writes", () => {
  const parts = chunks("L,P,255,255,255,5000\n");
  assert.deepEqual(parts.map((p) => p.length), [20, 1]);
});

// ---- a fake micro:bit over Web Bluetooth -------------------------------------------------------------

function fakeBluetooth({ swapRoles = false } = {}) {
  const written = [];
  let notifyListener = null;
  let disconnectListener = null;
  let releaseWrite = null;
  const holdWrites = { on: false };

  const writable = {
    uuid: UART_CHARS[swapRoles ? 0 : 1],
    properties: { write: true, writeWithoutResponse: true },
    async writeValueWithoutResponse(bytes) {
      if (holdWrites.on) await new Promise((r) => { releaseWrite = r; });
      written.push(new TextDecoder().decode(bytes));
    },
  };
  const notifying = {
    uuid: UART_CHARS[swapRoles ? 1 : 0],
    properties: { notify: false, indicate: true },
    addEventListener(_ev, cb) { notifyListener = cb; },
    async startNotifications() {},
  };
  const device = {
    name: "BBC micro:bit [tegop]",
    gatt: {
      connected: false,
      async connect() {
        this.connected = true;
        return {
          async getPrimaryService(uuid) {
            assert.equal(uuid, UART_SERVICE);
            return { async getCharacteristic(u) { return [writable, notifying].find((c) => c.uuid === u); } };
          },
        };
      },
      disconnect() { this.connected = false; disconnectListener?.(); },
    },
    addEventListener(ev, cb) { if (ev === "gattserverdisconnected") disconnectListener = cb; },
  };
  return {
    bluetooth: { async requestDevice(opts) { this.opts = opts; return device; } },
    written,
    holdWrites,
    release() { releaseWrite?.(); releaseWrite = null; },
    robotSays(text) {
      notifyListener({ target: { value: new TextEncoder().encode(text) } });
    },
  };
}

const tick = () => new Promise((r) => setTimeout(r, 0));

test("connects, finds the writable characteristic whatever its UUID, sends and receives lines", async () => {
  for (const swapRoles of [false, true]) {
    const fb = fakeBluetooth({ swapRoles });
    const states = [];
    const lines = [];
    const link = createLink({ bluetooth: fb.bluetooth, onStatus: (s) => states.push(s), onLine: (l) => lines.push(l) });
    assert.equal(link.send("H\n"), false, "nothing is sent before connecting");
    await link.connect();
    assert.deepEqual(fb.bluetooth.opts.optionalServices, [UART_SERVICE]);
    assert.deepEqual(states, ["connecting", "connected"]);
    assert.ok(link.connected);
    link.send("H\n");
    await tick();
    assert.deepEqual(fb.written, ["H\n"]);
    fb.robotSays("T,2");
    fb.robotSays("3,0,0,0\nT,9,0,0,1\n");
    assert.deepEqual(lines, ["T,23,0,0,0", "T,9,0,0,1"]);
    link.disconnect();
    assert.equal(states.at(-1), "disconnected");
    assert.equal(link.connected, false);
  }
});

test("while a write is in flight only the newest drive packet waits; other messages are kept", async () => {
  const fb = fakeBluetooth();
  const link = createLink({ bluetooth: fb.bluetooth });
  await link.connect();
  fb.holdWrites.on = true;
  link.send(drivePacket(10, 0, 1), { drive: true });   // goes out, then waits on the radio
  await tick();
  link.send(drivePacket(20, 0, 2), { drive: true });
  link.send("H\n");
  link.send(drivePacket(30, 0, 3), { drive: true });   // replaces seq 2
  fb.holdWrites.on = false;
  fb.release();
  for (let i = 0; i < 5; i++) await tick();
  assert.deepEqual(fb.written, ["D,10,0,1\n", "D,30,0,3\n", "H\n"]);
});

test("a browser without Web Bluetooth gets a clear error", async () => {
  await assert.rejects(createLink({ bluetooth: undefined }).connect(), /Web Bluetooth/);
});
