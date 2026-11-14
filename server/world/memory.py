"""T49 — Per-world role memory.

Remembers which role every object has in every world, so the chair is the
castle every time, and again when an earlier song comes back (§7.4, §7.12).

Contract (C7)::

    mem = RoleMemory()
    mem.set(world_id, obj_id, {"role", "name", "behaviour"}) -> stored role
    mem.get(world_id, obj_id) -> role | None
    mem.roles_for(world_id)   -> {obj_id: role}
    mem.forget_object(obj_id)

Two objects in one world may share a role but not a name: ``set`` appends
" II" (then " III", ...) when the name is already used by another object.

The store is session-only. With ``snapshot_path`` set, every change is also
written to a JSON file (default for ``run``: ``runtime/memory.json``) so a
crashed brain can pick up where it left off; the snapshot is deleted on
``clear()`` / ``system.reset``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_SNAPSHOT = Path("runtime") / "memory.json"
_ROMAN = ["II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]


def _clean(role: dict) -> dict:
    return {
        "role": role.get("role"),
        "name": role.get("name"),
        "behaviour": role.get("behaviour", "neutral"),
    }


class RoleMemory:
    def __init__(self, snapshot_path: str | os.PathLike | None = None):
        self._by_world: dict[str, dict[int, dict]] = {}
        self.snapshot_path = Path(snapshot_path) if snapshot_path else None

    @classmethod
    def load(cls, snapshot_path) -> "RoleMemory":
        """Recover from a snapshot written by an earlier run (missing file → empty)."""
        mem = cls(snapshot_path)
        try:
            raw = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return mem
        for world_id, roles in (raw or {}).items():
            mem._by_world[world_id] = {int(k): _clean(v) for k, v in roles.items()}
        return mem

    # -- queries -----------------------------------------------------------
    def get(self, world_id: str, obj_id: int) -> dict | None:
        role = self._by_world.get(world_id, {}).get(int(obj_id))
        return dict(role) if role else None

    def roles_for(self, world_id: str) -> dict[int, dict]:
        return {k: dict(v) for k, v in self._by_world.get(world_id, {}).items()}

    def worlds(self) -> list[str]:
        return list(self._by_world)

    # -- updates -----------------------------------------------------------
    def set(self, world_id: str, obj_id: int, role: dict) -> dict:
        obj_id = int(obj_id)
        roles = self._by_world.setdefault(world_id, {})
        stored = _clean(role)
        stored["name"] = self._unique_name(roles, obj_id, stored["name"])
        roles[obj_id] = stored
        self._save()
        return dict(stored)

    def forget_object(self, obj_id: int) -> None:
        obj_id = int(obj_id)
        for roles in self._by_world.values():
            roles.pop(obj_id, None)
        self._save()

    def clear(self) -> None:
        self._by_world.clear()
        if self.snapshot_path:
            try:
                self.snapshot_path.unlink()
            except FileNotFoundError:
                pass

    # -- internals ---------------------------------------------------------
    @staticmethod
    def _unique_name(roles: dict, obj_id: int, name):
        if not name:
            return name
        taken = {r["name"] for oid, r in roles.items() if oid != obj_id and r.get("name")}
        if name not in taken:
            return name
        for suffix in _ROMAN:
            candidate = f"{name} {suffix}"
            if candidate not in taken:
                return candidate
        n = len(_ROMAN) + 2
        while f"{name} {n}" in taken:
            n += 1
        return f"{name} {n}"

    def _save(self) -> None:
        if not self.snapshot_path:
            return
        try:
            self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            data = {w: {str(k): v for k, v in r.items()} for w, r in self._by_world.items()}
            tmp = self.snapshot_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data), encoding="utf-8")
            os.replace(tmp, self.snapshot_path)
        except OSError:
            pass  # the snapshot is a convenience; never break the game over it


async def run(hub, config, memory: RoleMemory | None = None):
    """Clear the (shared) memory on ``system.reset``."""
    if memory is None:
        return

    async def _on_reset(_env):
        memory.clear()

    hub.sub("system.reset", _on_reset)
