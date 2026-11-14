"""T58 — Threat reaction (recoil, warning, rumble).

On ``world.event danger_enter``: ``robot.cmd {kind:"recoil", ms: RECOIL_MS}``,
``sfx.play {sound:"warning"}`` and ``robot.cmd {kind:"rumble", ms: 300}``.
A global 2.5 s cooldown lets the robot escape. Lights (T23) and narration (T82)
are handled elsewhere.
"""

from __future__ import annotations

import time

DEFAULT_RECOIL_MS = 600
RUMBLE_MS = 300
COOLDOWN_S = 2.5


class ThreatReaction:
    def __init__(self, config: dict | None = None):
        config = config or {}
        self.recoil_ms = int(config.get("RECOIL_MS", DEFAULT_RECOIL_MS))
        self.reset()

    def reset(self):
        self.last: float | None = None

    def on_event(self, event: dict, now: float) -> list[tuple[str, dict]]:
        if event.get("kind") != "danger_enter":
            return []
        if self.last is not None and now - self.last < COOLDOWN_S:
            return []
        self.last = now
        return [
            ("robot.cmd", {"kind": "recoil", "ms": self.recoil_ms}),
            ("sfx.play", {"sound": "warning"}),
            ("robot.cmd", {"kind": "rumble", "ms": RUMBLE_MS}),
        ]


async def run(hub, config, *, clock=time.time):
    reaction = ThreatReaction(config)

    async def on_event(env):
        for topic, data in reaction.on_event(env.get("data") or {}, clock()):
            await hub.pub(topic, data)

    async def on_reset(_env):
        reaction.reset()

    hub.sub("world.event", on_event)
    hub.sub("system.reset", on_reset)
    return reaction
