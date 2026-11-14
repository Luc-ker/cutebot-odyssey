"""T59 — Friendly approach reaction.

On ``world.event friendly_enter``: play the role's ``sfx`` from the roles
vocabulary (C5) if it has one, else ``chime``. Per-object cooldown 10 s,
global cooldown 2 s. Warm lights are the light director's job (T23).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

ROLES_PATH = Path(__file__).resolve().parents[2] / "shared" / "roles.json"
PER_OBJECT_COOLDOWN_S = 10.0
GLOBAL_COOLDOWN_S = 2.0
DEFAULT_SOUND = "chime"


def load_sfx_table(path: Path = ROLES_PATH) -> dict:
    try:
        roles = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {r["role"]: r["sfx"] for r in roles if r.get("role") and r.get("sfx")}


class FriendlyReaction:
    def __init__(self, sfx_by_role: dict | None = None):
        self.sfx_by_role = load_sfx_table() if sfx_by_role is None else sfx_by_role
        self.reset()

    def reset(self):
        self.last_global: float | None = None
        self.last_by_obj: dict = {}

    def on_event(self, event: dict, now: float) -> dict | None:
        if event.get("kind") != "friendly_enter":
            return None
        obj_id = event.get("id")
        if self.last_global is not None and now - self.last_global < GLOBAL_COOLDOWN_S:
            return None
        last = self.last_by_obj.get(obj_id)
        if last is not None and now - last < PER_OBJECT_COOLDOWN_S:
            return None
        self.last_global = now
        self.last_by_obj[obj_id] = now
        return {"sound": self.sfx_by_role.get(event.get("role")) or DEFAULT_SOUND}


async def run(hub, config, *, clock=time.time):
    reaction = FriendlyReaction()

    async def on_event(env):
        play = reaction.on_event(env.get("data") or {}, clock())
        if play:
            await hub.pub("sfx.play", play)

    async def on_reset(_env):
        reaction.reset()

    hub.sub("world.event", on_event)
    hub.sub("system.reset", on_reset)
    return reaction
