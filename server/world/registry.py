"""T48 — Object registry.

The laptop's list of every object the robot has discovered, kept up to date from the vision service's
``vision.state`` (C3).

The camera rides on the robot, so objects leave the view all the time. An object that is out of view is
**not** gone: it stays in the registry with ``visible = False`` and keeps its last view position, so it keeps
its role and comes back as itself when the robot looks at it again (vision re-identifies it by appearance).
Only an object unseen for ``OBJECT_FORGET_S`` is forgotten (``Diff.removed``).

- ``visible``: seen within the last ``VIEW_GRACE_S`` (a short grace so a missed frame doesn't flicker).
- ``pos``/``size``: view units (C1), from the last frame the object was in.

Contract (C7)::

    reg = ObjectRegistry(config)
    diff = reg.update(vision_state, now)   # -> Diff(added, removed)
    reg.get(obj_id) -> TrackedObject | None
    reg.all()       -> list[TrackedObject]   # everything known, in view or not
    reg.visible()   -> list[TrackedObject]   # what the robot can see now

The registry is a plain in-process object. It has no loop of its own: the module that feeds it
``vision.state`` (arrivals, T50) also calls ``clear()`` when it sees ``system.reset``.
``run(hub, config, registry=...)`` is provided for wiring that wants the registry to clear itself.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

DEFAULT_VIEW_GRACE_S = 0.6
DEFAULT_FORGET_S = 600.0


@dataclass
class TrackedObject:
    id: int
    cls: str
    pos: list
    size: list
    first_seen: float
    last_seen: float
    conf: float = 1.0
    visible: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Diff:
    added: list = field(default_factory=list)
    removed: list = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.added or self.removed)


class ObjectRegistry:
    def __init__(self, config: dict | None = None):
        config = config or {}
        self.view_grace_s = float(config.get("VIEW_GRACE_S", DEFAULT_VIEW_GRACE_S))
        self.forget_s = float(config.get("OBJECT_FORGET_S", DEFAULT_FORGET_S))
        self._objects: dict[int, TrackedObject] = {}

    # -- queries -----------------------------------------------------------
    def get(self, obj_id: int) -> TrackedObject | None:
        return self._objects.get(obj_id)

    def all(self) -> list[TrackedObject]:
        return list(self._objects.values())

    def visible(self) -> list[TrackedObject]:
        return [o for o in self._objects.values() if o.visible]

    def __len__(self) -> int:
        return len(self._objects)

    # -- updates -----------------------------------------------------------
    def clear(self) -> None:
        self._objects.clear()

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
                diff.added.append(obj_id)
                continue
            cur.pos, cur.size, cur.last_seen, cur.visible = pos, size, now, True
            cur.conf = float(o.get("conf", cur.conf))
            if o.get("cls"):
                cur.cls = str(o["cls"])

        for obj_id, obj in list(self._objects.items()):
            if obj_id in seen_ids:
                continue
            unseen = now - obj.last_seen
            if unseen > self.forget_s:
                del self._objects[obj_id]
                diff.removed.append(obj_id)
            elif unseen > self.view_grace_s:
                obj.visible = False
        return diff


async def run(hub, config, registry: ObjectRegistry | None = None):
    """Optional wiring: clear ``registry`` on ``system.reset``."""
    if registry is None:
        return

    async def _on_reset(_env):
        registry.clear()

    hub.sub("system.reset", _on_reset)
