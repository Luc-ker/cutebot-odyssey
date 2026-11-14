"""T52 — Object clustering into places.

Several objects close together read as one place (three cups become a village).

Contract (C7)::

    find_clusters(objects, max_gap) -> list[Cluster(id, member_ids, pos)]

* Single-linkage grouping: two objects link when the gap between their
  footprints (axis-aligned boxes from ``pos``/``size``) is at most ``max_gap``
  (table units, i.e. ``config.CLUSTER_GAP``). A cluster needs at least 3 members.
* Cluster ids are ints from ``CLUSTER_ID_BASE + 1`` upwards so they never collide
  with tracker ids; facing (T56) and ``robot.state.facing_id`` can carry them.
* An id stays while the membership overlaps a recent cluster's by more than half.
  ``ClusterTracker`` keeps that history; the module-level ``find_clusters`` uses a
  shared default tracker (``reset()`` clears it, e.g. on ``system.reset``).
* ``name_cluster(cluster, world)`` picks a place role (village, market, harbour,
  camp) from the world setting and a stable name.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field

CLUSTER_ID_BASE = 100000
MIN_MEMBERS = 3
HISTORY = 16

_PLACE_BY_SETTING = [
    (("ocean", "sea", "coast", "island", "river"), "harbour"),
    (("city", "neon", "court", "royal", "market", "bazaar"), "market"),
    (("wasteland", "desert", "volcan", "jungle", "rainforest", "space"), "camp"),
]
_PLACE_NAMES = {
    "harbour": ["Gull's Rest", "Saltwharf", "Anchor Bay", "Tidewater Docks"],
    "market": ["The Night Bazaar", "Lantern Row", "Coin Square", "The Glass Market"],
    "camp": ["Ember Camp", "Last Fire", "Dustwatch Camp", "The Outpost"],
    "village": ["Little Hollow", "Millbrook", "Three Wells", "Hearthstead"],
}


@dataclass
class Cluster:
    id: int
    member_ids: list
    pos: list
    role: str | None = None
    name: str | None = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"id": self.id, "pos": self.pos, "member_ids": self.member_ids,
                "role": self.role, "name": self.name}


def _get(o, key, default=None):
    return o.get(key, default) if isinstance(o, dict) else getattr(o, key, default)


def _gap(a, b) -> float:
    (ax, ay), (bx, by) = _get(a, "pos"), _get(b, "pos")
    aw, ah = (_get(a, "size") or [0, 0])[:2]
    bw, bh = (_get(b, "size") or [0, 0])[:2]
    dx = max(0.0, abs(ax - bx) - (aw + bw) / 2)
    dy = max(0.0, abs(ay - by) - (ah + bh) / 2)
    return math.hypot(dx, dy)


def group(objects, max_gap) -> list[list]:
    """Single-linkage groups (any size) as lists of objects."""
    objs = [o for o in objects if _get(o, "pos") is not None]
    parent = list(range(len(objs)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(objs)):
        for j in range(i + 1, len(objs)):
            if _gap(objs[i], objs[j]) <= max_gap:
                parent[find(i)] = find(j)
    groups: dict[int, list] = {}
    for i, o in enumerate(objs):
        groups.setdefault(find(i), []).append(o)
    return list(groups.values())


class ClusterTracker:
    def __init__(self):
        self._next = CLUSTER_ID_BASE + 1
        self._history: list[tuple[int, frozenset]] = []  # most recent last

    def reset(self):
        self._next = CLUSTER_ID_BASE + 1
        self._history.clear()

    def update(self, objects, max_gap) -> list[Cluster]:
        found = [g for g in group(objects, max_gap) if len(g) >= MIN_MEMBERS]
        found.sort(key=len, reverse=True)
        used: set[int] = set()
        out = []
        for members in found:
            ids = frozenset(int(_get(o, "id")) for o in members)
            best_id, best_overlap = None, 0.5
            for cid, prev in reversed(self._history):
                if cid in used:
                    continue
                overlap = len(ids & prev) / max(len(ids), len(prev))
                if overlap > best_overlap:
                    best_id, best_overlap = cid, overlap
            if best_id is None:
                best_id, self._next = self._next, self._next + 1
            used.add(best_id)
            pos = [sum(_get(o, "pos")[0] for o in members) / len(members),
                   sum(_get(o, "pos")[1] for o in members) / len(members)]
            out.append(Cluster(id=best_id, member_ids=sorted(ids), pos=pos))
        # history: current clusters newest, older (vanished) ones kept for a while
        current = {c.id: frozenset(c.member_ids) for c in out}
        self._history = [(cid, m) for cid, m in self._history if cid not in current][-HISTORY:]
        self._history += list(current.items())
        return out


_default = ClusterTracker()


def find_clusters(objects, max_gap, tracker: ClusterTracker | None = None) -> list[Cluster]:
    return (tracker or _default).update(objects, max_gap)


def reset():
    _default.reset()


def _setting(world) -> str:
    world = world or {}
    info = world.get("world", world) if isinstance(world.get("world"), dict) else world
    return f"{info.get('setting', '')} {info.get('name', '')}".lower()


def name_cluster(cluster: Cluster, world) -> Cluster:
    text = _setting(world)
    role = "village"
    for keys, place in _PLACE_BY_SETTING:
        if any(k in text for k in keys):
            role = place
            break
    names = _PLACE_NAMES[role]
    h = int.from_bytes(hashlib.sha1(f"{cluster.id}|{text}".encode()).digest()[:4], "big")
    cluster.role, cluster.name = role, names[h % len(names)]
    return cluster
