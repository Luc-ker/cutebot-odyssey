"""T59 — friendly approach reaction."""
from server.world.friendly_reaction import FriendlyReaction

LIGHTHOUSE = {"kind": "friendly_enter", "id": 6, "name": "Old Beacon", "role": "lighthouse"}


def test_same_lighthouse_twice_in_5s_one_sound():
    r = FriendlyReaction({"lighthouse": "foghorn"})
    assert r.on_event(LIGHTHOUSE, 0.0) == {"sound": "foghorn"}
    assert r.on_event(LIGHTHOUSE, 5.0) is None
    assert r.on_event(LIGHTHOUSE, 10.5) == {"sound": "foghorn"}


def test_chime_when_role_has_no_sfx():
    r = FriendlyReaction({})
    assert r.on_event(dict(LIGHTHOUSE, role="village"), 0.0) == {"sound": "chime"}


def test_global_cooldown_two_seconds():
    r = FriendlyReaction({})
    assert r.on_event(LIGHTHOUSE, 0.0)
    assert r.on_event(dict(LIGHTHOUSE, id=7), 1.0) is None
    assert r.on_event(dict(LIGHTHOUSE, id=7), 2.1)


def test_ignores_other_kinds():
    assert FriendlyReaction({}).on_event({"kind": "danger_enter", "id": 1}, 0) is None
