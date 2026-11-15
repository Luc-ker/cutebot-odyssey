"""T61 — Giant enter and leave events.

Turns hands and people over the table (``vision.state.giants``) into
``world.event giant_enter`` / ``giant_leave`` without flicker:

* a giant must be seen across at least 300 ms before ``giant_enter``;
* it must be unseen for 800 ms before ``giant_leave`` (shorter gaps are ignored);
* detections are matched to tracked giants by nearest position on the same
  edge, because vision ids may change between frames. Our ids are ``"g<n>"``.

Event shape: ``{"kind": "giant_enter", "id", "giant_kind", "edge"}``.
**Note:** C3 lists ``giant_enter {id, kind, edge}``, but ``kind`` is already the
``world.event`` discriminator, so the giant's hand/person kind travels as
``giant_kind``. A CONTRACTS.md fix should make this official.
"""

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass

from server.world import stable

ENTER_AFTER_S = 0.3
LEAVE_AFTER_S = 0.8
MATCH_DIST = 0.35
TICK_S = 0.1


@dataclass
class _Giant:
    id: str
    kind: str
    edge: str | None
    pos: list
    first_seen: float
    last_seen: float
    entered: bool = False


class GiantTracker:
    def __init__(self):
        self.reset()

    def reset(self):
        self._giants: list[_Giant] = []
        self._next = 1

    def _match(self, det, used) -> _Giant | None:
        best, best_d = None, MATCH_DIST
        for g in self._giants:
            if g.id in used or (det.get("edge") and g.edge and det["edge"] != g.edge):
                continue
            d = math.hypot(g.pos[0] - det["pos"][0], g.pos[1] - det["pos"][1])
            if d <= best_d:
                best, best_d = g, d
        return best

    def update(self, giants: list | None, now: float) -> list[dict]:
        used: set[str] = set()
        for det in giants or []:
            if det.get("pos") is None:
                continue
            g = self._match(det, used)
            if g is None:
                g = _Giant(id=f"g{self._next}", kind=det.get("kind", "hand"), edge=det.get("edge"),
                           pos=list(det["pos"]), first_seen=now, last_seen=now)
                self._next += 1
                self._giants.append(g)
            else:
                g.pos, g.last_seen = list(det["pos"]), now
                g.edge = det.get("edge") or g.edge
                if det.get("kind") == "person":
                    g.kind = "person"  # a person outranks a hand
            used.add(g.id)
        return self.tick(now)

    def tick(self, now: float) -> list[dict]:
        events = []
        for g in list(self._giants):
            if now - g.last_seen >= LEAVE_AFTER_S:
                self._giants.remove(g)
                if g.entered:
                    events.append({"kind": "giant_leave", "id": g.id})
            elif not g.entered and g.last_seen - g.first_seen >= ENTER_AFTER_S:
                g.entered = True
                events.append({"kind": "giant_enter", "id": g.id, "giant_kind": g.kind, "edge": g.edge})
        return events


async def run(hub, config, *, clock=time.time):
    if stable.enabled(config):
        # Stable Kingdom mode: hands and people reaching over the table never trigger the giant
        # transformation (prompt, eye shadow, narration, threat reactions all key off these events).
        return
    tracker = GiantTracker()

    async def publish(events):
        for ev in events:
            await hub.pub("world.event", ev)

    async def on_vision(env):
        await publish(tracker.update((env.get("data") or {}).get("giants"), clock()))

    async def on_reset(_env):
        tracker.reset()

    hub.sub("vision.state", on_vision)
    hub.sub("system.reset", on_reset)
    while True:  # leaves still fire if vision.state stops arriving
        await asyncio.sleep(TICK_S)
        await publish(tracker.tick(clock()))
