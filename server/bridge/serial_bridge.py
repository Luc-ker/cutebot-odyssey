"""T22 - laptop serial bridge: bridge micro:bit (USB) <-> hub.

 serial T,...  -> robot.telemetry     serial B,x -> gamepad.button
 robot.cmd     -> serial line (lights capped to LIGHT_MAX_HZ, latest wins; recoil/rumble never dropped)

Packets go through the shared codec (T05, server/common/radio_codec.py). Its dicts use the same `kind`
field as robot.cmd (C3/C6): {"kind": "lights"|"recoil"|"rumble", ...} encode to L/R/V lines, and decode()
returns {"kind": "telemetry", ...} or {"kind": "button", "button": "light"|...}.
"""
import asyncio
import logging
import os
import time

from server.common.radio_codec import decode, encode

log = logging.getLogger("serial_bridge")

CMD_KINDS = ("lights", "recoil", "rumble")


def cmd_to_line(data):
    """robot.cmd data -> serial line (no newline), or None if it isn't a command the bridge forwards."""
    kind = data.get("kind")
    if kind not in CMD_KINDS:
        return None
    msg = dict(data)
    if kind == "lights":
        msg.setdefault("mode", "solid")
        msg.setdefault("ms", 0)
    return encode(msg)


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
        if pkt["kind"] == "telemetry":
            await self.hub.pub("robot.telemetry", {
                "distance_cm": pkt["distance_cm"],
                "line": [int(pkt["line"][0]), int(pkt["line"][1])],
                "override": bool(pkt["override"])})
        elif pkt["kind"] == "button":
            await self.hub.pub("gamepad.button", {"button": pkt["button"]})

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
