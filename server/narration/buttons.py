"""Horn and Light buttons (T84, whitepaper §7.1).

    horn  -> sfx.play horn_<setting>  (nearest of the 8 fallback settings by keyword, default horn_kingdom)
             + world.event {kind: "horn"}
    light -> robot.cmd {kind: "lights", mode: "flash", rgb: warm white, ms: 600} + sfx.play whoosh

Each button has its own 0.5 s cooldown.

Contracts: C3 (``gamepad.button``, ``world.current``, ``sfx.play``, ``robot.cmd``, ``world.event``,
``system.reset``), C4 (World).
"""

from __future__ import annotations

import time
from typing import Any

COOLDOWN_S = 0.5
WARM_WHITE = [255, 214, 170]
LIGHT_MS = 600
DEFAULT_SETTING = "kingdom"

# The 8 fallback settings (whitepaper §7.6) and the words that point to each. Ties go to the earlier
# entry, so the specific ones come first ("snowy night village" is snow, not kingdom).
SETTINGS: list[tuple[str, tuple[str, ...]]] = [
    ("ocean", ("ocean", "sea", "pirate", "coast", "island", "harbour", "reef", "shanty", "ship", "sail")),
    ("snow", ("snow", "ice", "frost", "frozen", "winter", "glacier", "arctic", "tundra", "lullaby")),
    ("wasteland", ("wasteland", "volcan", "lava", "ash", "inferno", "fire", "desert", "metal")),
    ("space_station", ("space", "station", "orbit", "galaxy", "cosmic", "star", "ambient")),
    ("neon_city", ("neon", "city", "cyber", "synth", "metropolis", "future")),
    ("jungle", ("jungle", "rainforest", "forest", "swamp", "grove", "woods", "tropical", "drum")),
    ("royal_court", ("royal", "court", "palace", "throne", "baroque", "classical")),
    ("kingdom", ("kingdom", "castle", "medieval", "village", "knight", "realm", "lute")),
]
SETTING_KEYS = [k for k, _ in SETTINGS]


def nearest_setting(world: dict | None) -> str:
    """Best of the 8 settings for a World: most keyword hits in ``setting``, then in ``name``."""
    info = (world or {}).get("world") or {}
    for field in ("setting", "name"):
        text = str(info.get(field) or "").lower()
        if not text:
            continue
        best, best_hits = None, 0
        for key, words in SETTINGS:
            hits = sum(1 for w in words if w in text)
            if hits > best_hits:
                best, best_hits = key, hits
        if best:
            return best
    return DEFAULT_SETTING


def horn_sound(world: dict | None) -> str:
    return f"horn_{nearest_setting(world)}"


class Buttons:
    """Pure: ``press(button, now)`` returns the (topic, data) messages to publish."""

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.world: dict | None = None
        self.last: dict[str, float] = {}

    def on_world_current(self, data: dict) -> None:
        if isinstance(data.get("world"), dict):
            self.world = data["world"]

    def press(self, button: str, now: float) -> list[tuple[str, dict]]:
        if button not in ("horn", "light"):
            return []
        if now - self.last.get(button, float("-inf")) < COOLDOWN_S:
            return []
        self.last[button] = now
        if button == "horn":
            return [("sfx.play", {"sound": horn_sound(self.world)}),
                    ("world.event", {"kind": "horn"})]
        return [("robot.cmd", {"kind": "lights", "mode": "flash", "rgb": list(WARM_WHITE), "ms": LIGHT_MS}),
                ("sfx.play", {"sound": "whoosh"})]


async def run(hub: Any, config: dict | None = None, clock=time.monotonic) -> None:
    """Brain entrypoint (C7)."""
    b = Buttons()

    async def on_button(env: dict) -> None:
        for topic, data in b.press((env.get("data") or {}).get("button"), clock()):
            await hub.pub(topic, data)

    async def on_world(env: dict) -> None:
        b.on_world_current(env.get("data") or {})

    async def on_reset(_env: dict) -> None:
        b.reset()

    hub.sub("gamepad.button", on_button)
    hub.sub("world.current", on_world)
    hub.sub("system.reset", on_reset)
