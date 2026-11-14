import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server.narration import queue as nq  # noqa: E402
from server.narration.queue import NarrationQueue, truncate  # noqa: E402


def say(q, text, priority=1, now=0.0, voice=None):
    return q.say({"text": text, "priority": priority, "voice": voice}, now)


# ---- acceptance -----------------------------------------------------------------------------

def test_second_say_waits_for_first_done():
    q = NarrationQueue()
    say(q, "First line.", now=0.0)
    say(q, "Second line.", now=0.1)
    first = q.tick(0.1)
    assert first["text"] == "First line."
    assert q.tick(0.2) is None
    assert q.tick(1.0) is None
    q.done({"id": "someone-else"})
    assert q.tick(1.1) is None
    q.done({"id": first["id"]})
    second = q.tick(1.2)
    assert second["text"] == "Second line."
    assert second["id"] != first["id"]


def test_priority_3_jumps_ahead_of_queued_priority_1():
    q = NarrationQueue()
    say(q, "Speaking now.", 1, 0.0)
    playing = q.tick(0.0)
    say(q, "Low one.", 1, 0.1)
    say(q, "Low two.", 1, 0.2)
    say(q, "Beware the dragon!", 3, 0.3)
    q.done({"id": playing["id"]})
    order = []
    for t in (0.4, 0.5, 0.6):
        s = q.tick(t)
        order.append(s["text"])
        q.done({"id": s["id"]})
    assert order == ["Beware the dragon!", "Low one.", "Low two."]


# ---- rules ----------------------------------------------------------------------------------

def test_timeout_releases_the_next_line():
    q = NarrationQueue()
    say(q, "A" * 24 + ".", now=0.0)  # 25 chars -> 25/12 + 2 ≈ 4.08 s
    say(q, "Next.", now=0.0)
    q.tick(0.0)
    assert q.tick(4.0) is None
    assert q.tick(4.2)["text"] == "Next."


def test_items_older_than_8s_are_dropped():
    q = NarrationQueue()
    say(q, "Long line being spoken.", now=0.0)
    q.tick(0.0)
    say(q, "Stale news.", now=0.5)
    q.done({"id": "n1"})
    assert q.tick(9.0) is None


def test_queue_length_capped_at_4_dropping_lowest_priority():
    q = NarrationQueue()
    say(q, "Busy.", 3, 0.0)
    q.tick(0.0)
    say(q, "p0.", 0, 0.1)
    say(q, "p1.", 1, 0.2)
    say(q, "p2.", 2, 0.3)
    say(q, "p2 again.", 2, 0.4)
    say(q, "p3.", 3, 0.5)
    texts = sorted(i.text for i in q.items)
    assert len(q.items) == 4
    assert "p0." not in texts


def test_identical_text_within_10s_is_ignored():
    q = NarrationQueue()
    assert say(q, "Hello.", now=0.0)
    assert not say(q, "Hello.", now=5.0)
    assert say(q, "Hello.", now=10.5)


def test_empty_text_ignored():
    q = NarrationQueue()
    assert not say(q, "   ")
    assert q.tick(0.0) is None


def test_voice_passed_through():
    q = NarrationQueue()
    say(q, "Ahoy.", voice="old")
    assert q.tick(0.0) == {"id": "n1", "text": "Ahoy.", "voice": "old"}


def test_reset_clears_everything():
    q = NarrationQueue()
    say(q, "One.")
    q.tick(0.0)
    say(q, "Two.")
    q.reset()
    assert q.tick(0.1) is None
    assert say(q, "One.", now=0.2)  # de-dup memory cleared too


# ---- truncation -----------------------------------------------------------------------------

def test_truncate_at_sentence_boundary():
    text = "The storm rolls in. Keep clear of the Coil. The sea is wide and dark tonight."
    assert truncate(text, 45) == "The storm rolls in. Keep clear of the Coil."


def test_truncate_single_long_sentence_cuts_at_word():
    out = truncate("word " * 100, 50)
    assert len(out) <= 50
    assert out.endswith("…")
    assert "wor…" not in out


def test_short_text_unchanged_and_whitespace_collapsed():
    assert truncate("  Hi   there. ", 200) == "Hi there."


def test_queue_uses_max_chars():
    q = NarrationQueue(max_chars=20)
    say(q, "Short one. Then a much longer sentence follows.")
    assert q.tick(0.0)["text"] == "Short one."


# ---- hub wiring -----------------------------------------------------------------------------

class FakeHub:
    def __init__(self):
        self.subs, self.published = [], []

    def sub(self, pattern, cb):
        self.subs.append((pattern, cb))

    async def pub(self, topic, data):
        self.published.append((topic, data))

    async def emit(self, topic, data):
        for p, cb in self.subs:
            if p == topic:
                await cb({"topic": topic, "ts": 0, "src": "test", "data": data})


def test_run_publishes_one_speak_at_a_time(monkeypatch):
    monkeypatch.setattr(nq, "TICK_S", 0.001)

    async def scenario():
        hub = FakeHub()
        task = asyncio.create_task(nq.run(hub, {"NARRATION_MAX_CHARS": 200}))
        await asyncio.sleep(0)
        await hub.emit("narration.say", {"text": "One.", "priority": 1})
        await hub.emit("narration.say", {"text": "Two.", "priority": 1})
        await asyncio.sleep(0.02)
        speaks = [d for t, d in hub.published if t == "narration.speak"]
        assert [s["text"] for s in speaks] == ["One."]
        await hub.emit("narration.done", {"id": speaks[0]["id"]})
        await asyncio.sleep(0.02)
        speaks = [d for t, d in hub.published if t == "narration.speak"]
        assert [s["text"] for s in speaks] == ["One.", "Two."]
        task.cancel()

    asyncio.run(scenario())
