"""T54 — World registry and returning-song match.

Remembers every world composed this session with the music that made it, so an
earlier song brings back that same world (and, via RoleMemory, its roles).

Contract (C7)::

    reg = WorldRegistry(config)
    reg.add(world)              # assigns "w-" + 8 hex id if missing; returns the world
    reg.add(world, fallback=True)
    reg.get(world_id) / reg.get_by_name(name) / reg.all()
    reg.match(signature) -> World | None   # nearest session world under RETURN_MATCH_THRESHOLD

Fallback worlds (T75) are stored but never matched by signature. ``clear()``
(on ``system.reset``) forgets the session worlds and keeps the fallbacks, which
are static data.

Signature distance comes from T70 (``server.audio.signature.distance``); until
that lands a local 0–1 distance over tempo, energy, brightness and chroma is used.
"""

from __future__ import annotations

import math
import secrets

DEFAULT_THRESHOLD = 0.25


def _local_distance(a: dict, b: dict) -> float:
    """0 = same, 1 = very different. Weighted mean of per-feature distances."""
    parts, weights = [], []
    ta, tb = a.get("tempo_bpm"), b.get("tempo_bpm")
    if ta and tb:
        # tempo octave errors (half/double time) count as close
        ratio = max(ta, tb) / min(ta, tb)
        ratio = min(ratio, abs(ratio - 2) + 1)
        parts.append(min(1.0, (ratio - 1) / 0.5))
        weights.append(1.0)
    for key in ("energy", "brightness"):
        if a.get(key) is not None and b.get(key) is not None:
            parts.append(min(1.0, abs(float(a[key]) - float(b[key]))))
            weights.append(1.0)
    ca, cb = a.get("chroma"), b.get("chroma")
    if ca and cb and len(ca) == len(cb):
        dot = sum(x * y for x, y in zip(ca, cb))
        na, nb = math.sqrt(sum(x * x for x in ca)), math.sqrt(sum(y * y for y in cb))
        if na > 0 and nb > 0:
            parts.append(max(0.0, min(1.0, 1 - dot / (na * nb))))
            weights.append(1.5)
    if not weights:
        return 1.0
    return sum(p * w for p, w in zip(parts, weights)) / sum(weights)


def _default_distance():
    try:
        from server.audio.signature import distance  # T70
        return distance
    except ImportError:
        return _local_distance


def new_world_id() -> str:
    return "w-" + secrets.token_hex(4)


class WorldRegistry:
    def __init__(self, config: dict | None = None, distance=None):
        config = config or {}
        self.threshold = float(config.get("RETURN_MATCH_THRESHOLD", DEFAULT_THRESHOLD))
        self.distance = distance or _default_distance()
        self._worlds: dict[str, dict] = {}
        self._fallback_ids: set[str] = set()

    def add(self, world: dict, fallback: bool = False) -> dict:
        if not world.get("id"):
            world["id"] = new_world_id()
        self._worlds[world["id"]] = world
        if fallback:
            self._fallback_ids.add(world["id"])
        return world

    def get(self, world_id: str) -> dict | None:
        return self._worlds.get(world_id)

    def get_by_name(self, name: str) -> dict | None:
        """Look up a world (fallbacks first) by its file stem, id or world name."""
        name_l = str(name).lower()
        ordered = sorted(self._worlds.values(), key=lambda w: w["id"] not in self._fallback_ids)
        for w in ordered:
            info = w.get("world") or {}
            keys = {str(w.get("id", "")).lower(), str(w.get("key", "")).lower(),
                    str(info.get("name", "")).lower(), str(info.get("setting", "")).lower()}
            if name_l in keys:
                return w
        return None

    def all(self) -> list[dict]:
        return list(self._worlds.values())

    def is_fallback(self, world_id: str) -> bool:
        return world_id in self._fallback_ids

    def match(self, signature: dict | None) -> dict | None:
        if not signature:
            return None
        best, best_d = None, self.threshold
        for wid, world in self._worlds.items():
            sig = world.get("music_signature")
            if wid in self._fallback_ids or not sig:
                continue
            d = self.distance(signature, sig)
            if d < best_d:
                best, best_d = world, d
        return best

    def clear(self) -> None:
        self._worlds = {k: v for k, v in self._worlds.items() if k in self._fallback_ids}


async def run(hub, config, registry: WorldRegistry | None = None):
    """Clear the (shared) registry's session worlds on ``system.reset``."""
    if registry is None:
        return

    async def _on_reset(_env):
        registry.clear()

    hub.sub("system.reset", _on_reset)
