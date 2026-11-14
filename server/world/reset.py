"""T63 — Gamepad reset and full demo reset.

* ``gamepad.button {button:"reset"}`` recentres the player: the current world's
  arrival line goes to ``narration.say`` (priority 2) and the robot's lights go
  solid in the world's base colour (first palette word) via ``robot.cmd``.
* ``system.reset`` (from ``scripts/reset_demo.py`` or the status page) makes
  every stateful module clear itself (C3 rule); this module then re-selects the
  default fallback world with ``world.select {name:"kingdom"}``.
"""

from __future__ import annotations

import json
from pathlib import Path

COLOURS_PATH = Path(__file__).resolve().parents[2] / "shared" / "colours.json"
DEFAULT_WORLD = "kingdom"
NARRATION_PRIORITY = 2
LIGHT_MS = 0  # solid with no timeout: hold until the next light command
WHITE = [255, 255, 255]

# Used until T02 ships shared/colours.json.
_BASIC_COLOURS = {
    "red": [255, 0, 0], "crimson": [220, 20, 60], "orange": [255, 140, 0], "amber": [255, 191, 0],
    "gold": [255, 200, 0], "yellow": [255, 230, 0], "green": [0, 200, 60], "emerald": [0, 160, 90],
    "teal": [0, 150, 140], "turquoise": [64, 224, 208], "cyan": [0, 220, 255], "blue": [0, 80, 255],
    "navy": [0, 0, 128], "indigo": [75, 0, 130], "purple": [140, 0, 200], "violet": [160, 60, 255],
    "magenta": [255, 0, 200], "pink": [255, 105, 180], "white": WHITE, "silver": [192, 192, 192],
    "grey": [128, 128, 128], "gray": [128, 128, 128], "black": [20, 20, 20], "brown": [139, 69, 19],
}


def load_colours(path: Path = COLOURS_PATH) -> dict:
    try:
        table = json.loads(Path(path).read_text(encoding="utf-8"))
        return {str(k).lower(): v for k, v in table.items() if isinstance(v, list)}
    except (OSError, ValueError, AttributeError):
        return dict(_BASIC_COLOURS)


def colour_for(word, colours: dict) -> list:
    word = str(word or "").lower().strip()
    if word in colours:
        return list(colours[word])
    for part in reversed(word.replace("-", " ").split()):  # "deep sea blue" -> "blue"
        if part in colours:
            return list(colours[part])
    return list(WHITE)


class ResetHandler:
    def __init__(self, colours: dict | None = None):
        self.colours = colours if colours is not None else load_colours()
        self.world: dict | None = None

    def on_world(self, world: dict | None):
        if world:
            self.world = world

    def on_button(self, data: dict) -> list[tuple[str, dict]]:
        if data.get("button") != "reset":
            return []
        out = []
        world = self.world or {}
        if world.get("narration"):
            out.append(("narration.say", {"text": world["narration"], "priority": NARRATION_PRIORITY}))
        palette = (world.get("world") or {}).get("palette") or []
        rgb = colour_for(palette[0], self.colours) if palette else list(WHITE)
        out.append(("robot.cmd", {"kind": "lights", "mode": "solid", "rgb": rgb, "ms": LIGHT_MS}))
        return out

    def on_system_reset(self) -> list[tuple[str, dict]]:
        self.world = None
        return [("world.select", {"name": DEFAULT_WORLD})]


async def run(hub, config):
    handler = ResetHandler()

    async def publish(msgs):
        for topic, data in msgs:
            await hub.pub(topic, data)

    async def on_world(env):
        handler.on_world((env.get("data") or {}).get("world"))

    async def on_button(env):
        await publish(handler.on_button(env.get("data") or {}))

    async def on_reset(_env):
        await publish(handler.on_system_reset())

    hub.sub("world.current", on_world)
    hub.sub("gamepad.button", on_button)
    hub.sub("system.reset", on_reset)
    return handler
