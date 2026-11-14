"""T23 - robot light director: decides what the Cutebot's headlights do and publishes robot.cmd.

 base colour   = first palette colour of the current world (fades in on world.transition)
 beat          = flash in the 2nd palette colour, length/brightness scaled by energy
 danger_enter  = red flash train for 1.5 s (suppresses beat flashes)
 friendly_enter= warm pulse
 silent        = one dim solid command, no flashing
Never publishes faster than LIGHT_MAX_HZ.

ASSUMPTION: shared/colours.json (T02) is {"word": [r,g,b], ...} (a top-level "colours" key is also accepted).
"""
import asyncio
import json
import os
import time

NEUTRAL = (128, 128, 128)
RED = (255, 0, 0)
WARM = (255, 170, 60)
DANGER_S = 1.5
DANGER_FLASH_GAP_S = 0.2
DEFAULT_COLOURS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "shared", "colours.json")

TOPICS = ("audio.beat", "audio.features", "world.current", "world.event", "world.transition")


def load_colours(path=DEFAULT_COLOURS_PATH):
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("colours", data)
    except (OSError, ValueError):
        return {}


def colour_for(word, colours):
    w = str(word).lower().strip()
    if w in colours:
        return tuple(colours[w])
    last = w.split(" ")[-1] if w else ""
    if last in colours:
        return tuple(colours[last])
    return NEUTRAL


def scale(rgb, k):
    k = max(0.0, min(1.0, k))
    return tuple(int(c * k) for c in rgb)


class LightDirector:
    def __init__(self, hub, config, colours=None, clock=time.monotonic):
        self.hub = hub
        self.clock = clock
        self.colours = load_colours() if colours is None else colours
        self.min_gap = 1.0 / max(1, config.get("LIGHT_MAX_HZ", 10))
        self.base = (60, 60, 60)
        self.accent = (255, 255, 255)
        self.energy = 0.5
        self.tempo = 120.0
        self.silent = False
        self.silent_applied = False
        self.danger_until = 0.0
        self.next_danger_flash = 0.0
        self.friendly_pending = False
        self.need_solid_at = None
        self.transition_until = 0.0
        self._last_emit = -1e9
        self._has_world = False

    async def _emit(self, mode, rgb, ms):
        now = self.clock()
        if now - self._last_emit < self.min_gap:
            return False
        self._last_emit = now
        await self.hub.pub("robot.cmd", {"kind": "lights", "mode": mode,
                                         "rgb": [int(c) for c in rgb], "ms": int(ms)})
        return True

    def _set_world(self, world):
        pal = (world.get("world") or {}).get("palette") or []
        if pal:
            self.base = colour_for(pal[0], self.colours)
        if len(pal) > 1:
            self.accent = colour_for(pal[1], self.colours)

    async def on_message(self, env):
        topic, data, now = env["topic"], env["data"], self.clock()
        if topic == "audio.features":
            self.energy = float(data.get("energy", self.energy))
            self.silent = bool(data.get("silent", False))
        elif topic == "audio.beat":
            self.tempo = float(data.get("tempo_bpm") or self.tempo)
            await self._beat(now)
        elif topic == "world.current":
            self._set_world(data["world"])
            if not self._has_world:
                self._has_world = True
                self.need_solid_at = now
        elif topic == "world.transition":
            self._set_world(data["to"])
            self._has_world = True
            dur = data.get("duration_ms", 3000) / 1000.0
            self.transition_until = now + dur
            self.need_solid_at = now + dur
            await self._emit("pulse", self.base, dur * 1000)   # glow towards the new colour
        elif topic == "world.event":
            kind = data.get("kind")
            if kind == "danger_enter":
                self.danger_until = now + DANGER_S
                self.next_danger_flash = now
                await self._danger_step(now)
            elif kind == "friendly_enter":
                self.friendly_pending = True
                await self._friendly_step(now)

    async def _beat(self, now):
        if self.silent or now < self.danger_until or now < self.transition_until:
            return
        period_ms = 60000.0 / max(40.0, self.tempo)
        ms = min(60 + 140 * self.energy, 0.5 * period_ms)
        await self._emit("flash", scale(self.accent, 0.4 + 0.6 * self.energy), ms)

    async def _danger_step(self, now):
        if now < self.danger_until and now >= self.next_danger_flash:
            if await self._emit("flash", RED, 120):
                self.next_danger_flash = now + DANGER_FLASH_GAP_S

    async def _friendly_step(self, now):
        if self.friendly_pending and now >= self.danger_until:
            if await self._emit("pulse", WARM, 1000):
                self.friendly_pending = False

    async def tick(self):
        """Call ~20 Hz: timed things (danger train, silence, end of transition)."""
        now = self.clock()
        await self._danger_step(now)
        await self._friendly_step(now)
        if self.silent and not self.silent_applied:
            if await self._emit("solid", scale(self.base, 0.15), 0):
                self.silent_applied = True
        elif not self.silent and self.silent_applied:
            if await self._emit("solid", self.base, 0):
                self.silent_applied = False
        if self.need_solid_at is not None and now >= self.need_solid_at and not self.silent:
            if await self._emit("solid", self.base, 0):
                self.need_solid_at = None


async def run(hub, config):
    d = LightDirector(hub, config)
    for t in TOPICS:
        hub.sub(t, d.on_message)
    while True:
        await d.tick()
        await asyncio.sleep(0.05)
