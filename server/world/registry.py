"""T48 — Object registry.

The laptop's list of every object on the table, kept up to date from the Jetson's
``vision.state`` (C3), with a grace period so an object hidden for a moment
(by a hand, by the robot) is not forgotten.

Contract (C7)::

    reg = ObjectRegistry(config)
    diff = reg.update(vision_state, now)   # -> Diff(added, removed, moved)
    reg.get(obj_id) -> TrackedObject | None
    reg.all()       -> list[TrackedObject]

``all()`` includes objects that are currently inside their grace period, so the
map does not flicker when an object is briefly hidden.

The registry is a plain in-process object. It has no loop of its own: the module
that feeds it ``vision.state`` (arrivals, T50) also calls ``clear()`` when it sees
``system.reset``. ``run(hub, config, registry=...)`` is provided for wiring that
wants the registry to clear itself.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

DEFAULT_GRACE_S = 5.0
DEFAULT_TABLE_W_CM = 120.0
DEFAULT_TABLE_H_CM = 80.0
MOVE_THRESHOLD_CM = 2.0


@dataclass
class TrackedObject:
    id: int
    cls: str
    pos: list
    size: list
    first_seen: float
    last_seen: float
    conf: float = 1.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Diff:
    added: list = field(default_factory=list)
    removed: list = field(default_factory=list)
    moved: list = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.added or self.removed or self.moved)


class ObjectRegistry:
    def __init__(self, config: dict | None = None):
        config = config or {}
        self.grace_s = float(config.get("OBJECT_GRACE_S", DEFAULT_GRACE_S))
        self.table_w_cm = float(config.get("TABLE_W_CM", DEFAULT_TABLE_W_CM))
        self.table_h_cm = float(config.get("TABLE_H_CM", DEFAULT_TABLE_H_CM))
        self._objects: dict[int, TrackedObject] = {}
        # Position at which each object last counted as "moved" (or was added);
        # comparing against this anchor lets slow drift add up to a move.
        self._anchor: dict[int, list] = {}

    # -- queries -----------------------------------------------------------
    def get(self, obj_id: int) -> TrackedObject | None:
        return self._objects.get(obj_id)

    def all(self) -> list[TrackedObject]:
        return list(self._objects.values())

    def __len__(self) -> int:
        return len(self._objects)

    # -- updates -----------------------------------------------------------
    def clear(self) -> None:
        self._objects.clear()
        self._anchor.clear()

    def _moved_cm(self, a, b) -> float:
        return math.hypot((a[0] - b[0]) * self.table_w_cm, (a[1] - b[1]) * self.table_h_cm)

    def update(self, vision_state: dict | None, now: float) -> Diff:
        diff = Diff()
        seen_ids = set()
        for o in (vision_state or {}).get("objects") or []:
            try:
                obj_id = int(o["id"])
                pos = [float(o["pos"][0]), float(o["pos"][1])]
            except (KeyError, TypeError, ValueError, IndexError):
                continue
            size = list(o.get("size") or [0.0, 0.0])
            seen_ids.add(obj_id)
            cur = self._objects.get(obj_id)
            if cur is None:
                self._objects[obj_id] = TrackedObject(
                    id=obj_id, cls=str(o.get("cls", "object")), pos=pos, size=size,
                    first_seen=now, last_seen=now, conf=float(o.get("conf", 1.0)),
                )
                self._anchor[obj_id] = pos
                diff.added.append(obj_id)
                continue
            cur.pos, cur.size, cur.last_seen = pos, size, now
            cur.conf = float(o.get("conf", cur.conf))
            if o.get("cls"):
                cur.cls = str(o["cls"])
            if self._moved_cm(pos, self._anchor[obj_id]) > MOVE_THRESHOLD_CM:
                self._anchor[obj_id] = pos
                diff.moved.append(obj_id)

        for obj_id, obj in list(self._objects.items()):
            if obj_id not in seen_ids and now - obj.last_seen > self.grace_s:
                del self._objects[obj_id]
                self._anchor.pop(obj_id, None)
                diff.removed.append(obj_id)
        return diff


async def run(hub, config, registry: ObjectRegistry | None = None):
    """Optional wiring: clear ``registry`` on ``system.reset``."""
    if registry is None:
        return

    async def _on_reset(_env):
        registry.clear()

    hub.sub("system.reset", _on_reset)
