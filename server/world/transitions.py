"""T95 — World transition coordinator.

Turns "the world changed" into one timed ``world.transition`` event that the
map, video, lights and narrator all follow, so a change feels like one
deliberate moment (whitepaper §7.12).

* On ``world.current`` with a new world id, publish
  ``world.transition {from, to, started, duration_ms: TRANSITION_MS}``.
* Repeats of the current id (the scheduler's 5 s re-publish) are ignored.
* A change that arrives mid-transition starts a fresh transition from the
  current target (the world we were heading to), not from the old origin.
* ``system.reset`` forgets the current world, so the next ``world.current``
  starts a transition from ``null``.

Contracts: C3 (``world.current``, ``world.transition``, ``system.reset``), C4 (World),
C10 (``TRANSITION_MS``).
"""

from __future__ import annotations

import time

DEFAULT_TRANSITION_MS = 3000


class TransitionCoordinator:
    def __init__(self, duration_ms: int = DEFAULT_TRANSITION_MS):
        self.duration_ms = int(duration_ms)
        self.reset()

    def reset(self):
        self.current: dict | None = None  # the latest target world
        self.started: float | None = None

    def in_transition(self, now: float) -> bool:
        return self.started is not None and (now - self.started) * 1000 < self.duration_ms

    def on_world(self, world: dict | None, now: float) -> dict | None:
        """Return the ``world.transition`` data to publish, or None."""
        if not isinstance(world, dict) or not world.get("id"):
            return None
        if self.current is not None and world["id"] == self.current.get("id"):
            self.current = world  # same world, keep the freshest copy for the next "from"
            return None
        previous, self.current, self.started = self.current, world, now
        return {"from": previous, "to": world, "started": now, "duration_ms": self.duration_ms}


async def run(hub, config, *, clock=time.time):
    coord = TransitionCoordinator((config or {}).get("TRANSITION_MS", DEFAULT_TRANSITION_MS))

    async def on_world(env):
        out = coord.on_world((env.get("data") or {}).get("world"), clock())
        if out is not None:
            await hub.pub("world.transition", out)

    async def on_reset(_env):
        coord.reset()

    hub.sub("world.current", on_world)
    hub.sub("system.reset", on_reset)
    return coord
