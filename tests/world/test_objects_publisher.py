"""T62 — world objects publisher."""
from server.world.memory import RoleMemory
from server.world.objects_publisher import ObjectsPublisher
from server.world.registry import ObjectRegistry

WORLD = {"id": "w-0000beef", "world": {"name": "The Salt Sea", "setting": "open ocean"},
         "roles": [{"object_id": 2, "role": "ship", "name": "The Salt Queen", "behaviour": "neutral"}],
         "terrain": {"open_space": "open sea", "under_table": "the deep sea"}}


def validate_world_objects(data):
    """Local check of the C3 ``world.objects`` shape (until T04's schema lands)."""
    errors = []
    try:
        from server.common.schemas import validate_envelope  # T04
    except ImportError:
        validate_envelope = None
    if validate_envelope:
        env = {"topic": "world.objects", "ts": 0.0, "src": "test", "data": data}
        return [e for e in validate_envelope(env) if "warning" not in e.lower()]
    assert set(data) == {"world_id", "objects", "clusters", "terrain"}
    for o in data["objects"]:
        if set(o) != {"id", "cls", "pos", "size", "visible", "role", "name", "behaviour", "cluster_id", "from_sky"}:
            errors.append(f"object keys {sorted(o)}")
        if not isinstance(o["id"], int) or len(o["pos"]) != 2 or len(o["size"]) != 2:
            errors.append("object types")
        if o["behaviour"] not in (None, "friendly", "neutral", "threat"):
            errors.append("behaviour")
        if not isinstance(o["from_sky"], bool):
            errors.append("from_sky")
    for c in data["clusters"]:
        if not {"id", "pos", "member_ids", "role", "name"} <= set(c):
            errors.append(f"cluster keys {sorted(c)}")
    if not isinstance(data["terrain"], dict):
        errors.append("terrain")
    return errors


def make(**kw):
    reg = ObjectRegistry({})
    mem = RoleMemory()
    pub = ObjectsPublisher({"CLUSTER_GAP": 0.05}, registry=reg, memory=mem, **kw)
    pub.on_world(WORLD)
    return reg, mem, pub


def vstate(*objs):
    return {"objects": [{"id": i, "cls": "cup", "pos": list(p), "size": [0.03, 0.03]} for i, p in objs]}


def test_validates_and_shows_remembered_role():
    reg, mem, pub = make()
    reg.update(vstate((1, (0.2, 0.2)), (2, (0.6, 0.6)), (3, (0.9, 0.9))), 0)
    mem.set(WORLD["id"], 1, {"role": "lighthouse", "name": "Old Beacon", "behaviour": "friendly"})
    data = pub.snapshot(0)
    assert validate_world_objects(data) == []
    by_id = {o["id"]: o for o in data["objects"]}
    assert by_id[1]["role"] == "lighthouse" and by_id[1]["name"] == "Old Beacon"
    assert by_id[2]["role"] == "ship"            # from the world's own roles list
    assert by_id[3]["role"] is None and by_id[3]["behaviour"] is None
    assert data["world_id"] == WORLD["id"]
    assert data["terrain"]["open_space"] == "open sea"


def test_clusters_and_cluster_ids():
    reg, mem, pub = make()
    reg.update(vstate((1, (0.2, 0.2)), (2, (0.24, 0.2)), (3, (0.28, 0.2)), (4, (0.8, 0.8))), 0)
    data = pub.snapshot(0)
    assert len(data["clusters"]) == 1
    c = data["clusters"][0]
    assert sorted(c["member_ids"]) == [1, 2, 3] and c["role"] == "harbour" and c["name"]
    by_id = {o["id"]: o for o in data["objects"]}
    assert by_id[1]["cluster_id"] == c["id"] and by_id[4]["cluster_id"] is None
    assert validate_world_objects(data) == []


def test_out_of_view_objects_are_listed_but_not_clustered():
    reg, mem, pub = make()
    reg.update(vstate((1, (0.2, 0.2)), (2, (0.24, 0.2)), (3, (0.28, 0.2))), 0)
    reg.update(vstate((1, (0.2, 0.2)), (2, (0.24, 0.2))), 5)  # 3 left the view
    data = pub.snapshot(5)
    by_id = {o["id"]: o for o in data["objects"]}
    assert by_id[3]["visible"] is False and by_id[1]["visible"] is True
    assert data["clusters"] == []  # only two in view: not a place any more
    assert validate_world_objects(data) == []


def test_cluster_size_spans_its_members():
    reg, mem, pub = make()
    reg.update(vstate((1, (0.2, 0.2)), (2, (0.24, 0.2)), (3, (0.28, 0.2))), 0)
    c = pub.snapshot(0)["clusters"][0]
    assert abs(c["size"][0] - 0.11) < 1e-9 and abs(c["size"][1] - 0.03) < 1e-9


def test_recompute_at_most_2hz():
    calls = []

    def find(objects, gap):
        calls.append(1)
        return []

    reg, mem, pub = make(find_clusters=find, analyse=lambda objs, world: {})
    for i in range(10):  # 1 s at 10 Hz
        pub.snapshot(i * 0.1)
    assert len(calls) == 2


def test_from_sky_carried_for_three_seconds():
    reg, mem, pub = make()
    reg.update(vstate((1, (0.2, 0.2))), 0)
    pub.on_event({"kind": "object_added", "id": 1, "from_sky": True}, now=10.0)
    assert pub.snapshot(12.9)["objects"][0]["from_sky"] is True
    assert pub.snapshot(13.1)["objects"][0]["from_sky"] is False


def test_no_world_yet():
    reg = ObjectRegistry({})
    reg.update(vstate((1, (0.2, 0.2))), 0)
    data = ObjectsPublisher({}, registry=reg, memory=RoleMemory()).snapshot(0)
    assert data["world_id"] is None and data["objects"][0]["role"] is None
