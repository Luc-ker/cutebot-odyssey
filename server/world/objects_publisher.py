"""T62 — World objects publisher.

Publishes ``world.objects`` every 100 ms (C3)::

    {world_id, objects: [{id, cls, pos, size, role, name, behaviour, cluster_id, from_sky}],
     clusters: [{id, pos, member_ids, role, name}], terrain}

* Objects come from the shared ``ObjectRegistry`` (T48); roles from ``RoleMemory``
  (T49) for the current world, falling back to the world's own ``roles`` list.
  Objects without a role yet have ``role/name/behaviour: null``.
* Clusters (T52) and terrain (T53) are recomputed at most twice a second.
* ``from_sky`` from an ``object_added`` event is carried for 3 s so the map can
  animate the landing.
"""

from __future__ import annotations

import asyncio
import time

from server.world.memory import RoleMemory
from server.world.registry import ObjectRegistry

PUBLISH_S = 0.1
RECOMPUTE_S = 0.5
FROM_SKY_S = 3.0
DEFAULT_CLUSTER_GAP = 0.05


def _get(o, key, default=None):
    return o.get(key, default) if isinstance(o, dict) else getattr(o, key, default)


def _default_clusters():
    """(find_clusters, name_cluster) from T52 with a private tracker, or no-ops."""
    try:
        from server.world.clusters import ClusterTracker, name_cluster  # T52
    except ImportError:
        return (lambda objects, max_gap: []), None
    tracker = ClusterTracker()

    def find(objects, max_gap):
        return tracker.update(objects, max_gap)
    find.reset = tracker.reset
    return find, name_cluster


def _default_analyse():
    try:
        from server.world.terrain import analyse  # T53
        return analyse
    except ImportError:
        return lambda objects, world: {"open_regions": [], "open_space": None, "under_table": None}


def _as_dict(c) -> dict:
    if isinstance(c, dict):
        return c
    return {"id": c.id, "pos": c.pos, "member_ids": c.member_ids,
            "role": getattr(c, "role", None), "name": getattr(c, "name", None)}


class ObjectsPublisher:
    def __init__(self, config: dict | None = None, *, registry=None, memory=None,
                 find_clusters=None, name_cluster=None, analyse=None):
        config = config or {}
        self.cluster_gap = float(config.get("CLUSTER_GAP", DEFAULT_CLUSTER_GAP))
        self.registry = registry if registry is not None else ObjectRegistry(config)
        self.memory = memory if memory is not None else RoleMemory()
        if find_clusters is None:
            find_clusters, default_namer = _default_clusters()
            name_cluster = name_cluster or default_namer
        self.find_clusters = find_clusters
        self.name_cluster = name_cluster
        self.analyse = analyse or _default_analyse()
        self.reset()

    def reset(self):
        self.world: dict | None = None
        self.from_sky_until: dict[int, float] = {}
        self._clusters: list[dict] = []
        self._terrain: dict = {}
        self._computed_at: float | None = None
        if hasattr(self.find_clusters, "reset"):
            self.find_clusters.reset()

    def on_world(self, world: dict | None):
        if world and (not self.world or world.get("id") != self.world.get("id")):
            self._computed_at = None  # new names/terrain words right away
        self.world = world

    def on_event(self, event: dict, now: float):
        if event.get("kind") == "object_added" and event.get("from_sky"):
            self.from_sky_until[event["id"]] = now + FROM_SKY_S
        elif event.get("kind") == "object_removed":
            self.from_sky_until.pop(event.get("id"), None)

    def _world_roles(self) -> dict:
        roles = {}
        for r in (self.world or {}).get("roles") or []:
            if r.get("object_id") is not None:
                roles[int(r["object_id"])] = r
        return roles

    def _recompute(self, objects, now: float):
        try:
            clusters = self.find_clusters(objects, self.cluster_gap)
            if self.name_cluster:
                clusters = [self.name_cluster(c, self.world) for c in clusters]
            self._clusters = [_as_dict(c) for c in clusters]
        except Exception:
            self._clusters = []
        try:
            self._terrain = self.analyse(objects, self.world)
        except Exception:
            self._terrain = {}
        self._computed_at = now

    def snapshot(self, now: float) -> dict:
        world_id = (self.world or {}).get("id")
        remembered = self.memory.roles_for(world_id) if world_id else {}
        composed = self._world_roles()
        raw = self.registry.all()
        if self._computed_at is None or now - self._computed_at >= RECOMPUTE_S:
            self._recompute([{"id": _get(o, "id"), "pos": _get(o, "pos"), "size": _get(o, "size")}
                             for o in raw], now)
        cluster_of = {m: c["id"] for c in self._clusters for m in c.get("member_ids", [])}
        for obj_id, until in list(self.from_sky_until.items()):
            if until <= now:
                del self.from_sky_until[obj_id]

        objects = []
        for o in raw:
            obj_id = int(_get(o, "id"))
            role = remembered.get(obj_id) or composed.get(obj_id) or {}
            objects.append({
                "id": obj_id, "cls": _get(o, "cls"), "pos": list(_get(o, "pos")),
                "size": list(_get(o, "size") or [0, 0]),
                "role": role.get("role"), "name": role.get("name"), "behaviour": role.get("behaviour"),
                "cluster_id": cluster_of.get(obj_id),
                "from_sky": obj_id in self.from_sky_until,
            })
        return {"world_id": world_id, "objects": objects, "clusters": self._clusters,
                "terrain": self._terrain}


async def run(hub, config, *, registry=None, memory=None, clock=time.time):
    pub = ObjectsPublisher(config, registry=registry, memory=memory)

    async def on_world(env):
        pub.on_world((env.get("data") or {}).get("world"))

    async def on_event(env):
        pub.on_event(env.get("data") or {}, clock())

    async def on_reset(_env):
        pub.reset()

    hub.sub("world.current", on_world)
    hub.sub("world.event", on_event)
    hub.sub("system.reset", on_reset)
    while True:
        await hub.pub("world.objects", pub.snapshot(clock()))
        await asyncio.sleep(PUBLISH_S)
