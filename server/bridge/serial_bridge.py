"""T22 - laptop serial bridge: bridge micro:bit (USB) <-> hub.

 serial T,...  -> robot.telemetry     serial B,x -> gamepad.button
 robot.cmd     -> serial line (lights capped to LIGHT_MAX_HZ, latest wins; recoil/rumble never dropped)

ASSUMPTION (reconcile with T05 server/common/radio_codec.py): decode() returns
 {"type":"T","distance_cm","line":[l,r],"override"} / {"type":"B","button":"L|H|S|R"} and encode() takes
 {"type":"L","mode":"S|F|P","rgb":[..],"ms"} / {"type":"R","ms"} / {"type":"V","ms"}.
Small local fallbacks are used if radio_codec is not merged yet.
"""
import asyncio
import logging
import os
import time

log = logging.getLogger("serial_bridge")

BUTTONS = {"L": "light", "H": "horn", "S": "shout", "R": "reset"}
MODES = {"solid": "S", "flash": "F", "pulse": "P"}


def _fallback_decode(line):
    try:
        p = line.strip().split(",")
        if p[0] == "T" and len(p) == 5:
            return {"type": "T", "distance_cm": int(p[1]), "line": [int(p[2]), int(p[3])], "override": int(p[4])}
        if p[0] == "B" and len(p) == 2 and p[1] in BUTTONS:
            return {"type": "B", "button": p[1]}
    except Exception:
        pass
    return None


def _fallback_encode(d):
    def c(v, lo, hi):
        return max(lo, min(hi, int(v)))
    k = d["type"]
    if k == "L":
        r, g, b = (c(x, 0, 255) for x in d["rgb"])
        return "L,%s,%d,%d,%d,%d" % (d["mode"], r, g, b, c(d.get("ms", 0), 0, 5000))
    return "%s,%d" % (k, c(d["ms"], 0, 5000))


try:
    from server.common.radio_codec import decode, encode
except ImportError:
    decode, encode = _fallback_decode, _fallback_encode


def cmd_to_line(data):
    """robot.cmd data -> serial line (no newline), or None if unknown."""
    kind = data.get("kind")
    if kind == "lights":
        return encode({"type": "L", "mode": MODES.get(data.get("mode"), "S"),
                       "rgb": data["rgb"], "ms": data.get("ms", 0)})
    if kind == "recoil":
        return encode({"type": "R", "ms": data["ms"]})
    if kind == "rumble":
        return encode({"type": "V", "ms": data["ms"]})
    return None


def open_serial(port_name=None):
    import serial
    from serial.tools import list_ports
    name = port_name or os.environ.get("GENRATOR_SERIAL_PORT")
    if not name:
        for p in list_ports.comports():
            if p.vid == 0x0D28:  # micro:bit
                name = p.device
                break
    if not name:
        raise OSError("no micro:bit serial port found")
    return serial.Serial(name, 115200, timeout=0.1)


class SerialBridge:
    def __init__(self, hub, config, open_port=None, clock=time.monotonic):
        self.hub = hub
        self.light_gap = 1.0 / max(1, config.get("LIGHT_MAX_HZ", 10))
        self.open_port = open_port or open_serial
        self.clock = clock
        self.port = None
        self.ok = False
        self.detail = "starting"
        self._last_light = -1e9
        self._pending_light = None

    # ---- serial -> hub
    async def handle_line(self, line):
        pkt = decode(line.strip())
        if not pkt:
            return
        if pkt["type"] == "T":
            await self.hub.pub("robot.telemetry", {
                "distance_cm": pkt["distance_cm"],
                "line": [int(pkt["line"][0]), int(pkt["line"][1])],
                "override": bool(pkt["override"])})
        elif pkt["type"] == "B":
            await self.hub.pub("gamepad.button", {"button": BUTTONS[pkt["button"]]})

    # ---- hub -> serial
    def _write(self, line):
        if self.port is None:
            return False
        try:
            self.port.write((line + "\n").encode("ascii"))
            return True
        except Exception as e:
            self._lost(e)
            return False

    async def on_cmd(self, env):
        data = env["data"]
        line = cmd_to_line(data)
        if line is None:
            return
        if data.get("kind") != "lights":
            self._write(line)           # recoil and rumble are never rate limited or dropped
            return
        now = self.clock()
        if now - self._last_light >= self.light_gap:
            if self._write(line):
                self._last_light = now
            self._pending_light = None
        else:
            self._pending_light = line  # newest colour wins; sent when the window opens

    async def flush(self):
        if self._pending_light and self.clock() - self._last_light >= self.light_gap:
            line, self._pending_light = self._pending_light, None
            if self._write(line):
                self._last_light = self.clock()

    # ---- connection handling
    def _lost(self, err):
        log.warning("serial lost: %s", err)
        try:
            self.port and self.port.close()
        except Exception:
            pass
        self.port = None
        self.ok = False
        self.detail = "disconnected"

    async def publish_health(self):
        await self.hub.pub("system.health", {"service": "serial_bridge", "ok": self.ok, "detail": self.detail})

    async def loop(self):
        last_health = -1e9
        while True:
            if self.port is None:
                try:
                    self.port = self.open_port()
                    self.ok, self.detail = True, "connected"
                except Exception as e:
                    self.ok, self.detail = False, "no port: %s" % e
                    await self.publish_health()
                    await asyncio.sleep(2)
                    continue
            try:
                raw = await asyncio.to_thread(self.port.readline)
                if raw:
                    await self.handle_line(raw.decode("ascii", "ignore"))
            except Exception as e:
                self._lost(e)
                continue
            await self.flush()
            if time.monotonic() - last_health >= 2:
                last_health = time.monotonic()
                await self.publish_health()


async def run(hub, config):
    bridge = SerialBridge(hub, config)
    hub.sub("robot.cmd", bridge.on_cmd)
    await bridge.loop()
