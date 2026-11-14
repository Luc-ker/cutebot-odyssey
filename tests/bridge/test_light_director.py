import asyncio

from server.bridge.light_director import LightDirector, colour_for

COLOURS = {"teal": [0, 128, 128], "grey": [128, 128, 128], "gold": [255, 200, 50]}
WORLD = {"id": "w-1", "world": {"name": "X", "palette": ["deep teal", "storm grey", "lantern gold"]}}
ACCENT = (128, 128, 128)


class Clock:
    t = 0.0

    def __call__(self):
        return self.t


class FakeHub:
    def __init__(self, clock):
        self.clock, self.sent = clock, []

    async def pub(self, topic, data):
        self.sent.append((self.clock.t, topic, data))


def make():
    clk = Clock()
    hub = FakeHub(clk)
    d = LightDirector(hub, {"LIGHT_MAX_HZ": 10}, colours=COLOURS, clock=clk)
    return d, hub, clk


def env(topic, data):
    return {"topic": topic, "data": data, "ts": 0, "src": "t"}


def run(coro):
    return asyncio.run(coro)


def lights(hub):
    return [(t, d) for t, tp, d in hub.sent if tp == "robot.cmd"]


def test_colour_for_last_word_fallback():
    assert colour_for("deep teal", COLOURS) == (0, 128, 128)
    assert colour_for("mystery", COLOURS) == (128, 128, 128)


def test_120bpm_beats_flash_in_accent_and_are_rate_limited():
    d, hub, clk = make()

    async def go():
        await d.on_message(env("world.current", {"world": WORLD}))
        await d.on_message(env("audio.features", {"energy": 0.8, "silent": False}))
        await d.tick()
        for i in range(8):                       # 120 bpm, 2 beats/s
            clk.t = 1 + i * 0.5
            await d.on_message(env("audio.beat", {"tempo_bpm": 120, "strength": 1}))
        for i in range(50):                      # a burst far above LIGHT_MAX_HZ
            clk.t = 10 + i * 0.01
            await d.on_message(env("audio.beat", {"tempo_bpm": 120, "strength": 1}))
    run(go())
    flashes = [(t, c) for t, c in lights(hub) if c["mode"] == "flash"]
    assert len(flashes) >= 8
    assert all(c["rgb"][0] <= ACCENT[0] for _, c in flashes)
    times = [t for t, _ in lights(hub)]
    assert all(b - a >= 0.1 - 1e-9 for a, b in zip(times, times[1:]))


def test_danger_window_suppresses_beats_and_is_red():
    d, hub, clk = make()

    async def go():
        await d.on_message(env("audio.features", {"energy": 0.9, "silent": False}))
        clk.t = 5.0
        await d.on_message(env("world.event", {"kind": "danger_enter", "id": 3, "name": "n", "role": "dragon"}))
        for step in range(1, 15):
            clk.t = 5.0 + step * 0.1
            await d.on_message(env("audio.beat", {"tempo_bpm": 120, "strength": 1}))
            await d.tick()
        clk.t = 8.0
        await d.on_message(env("audio.beat", {"tempo_bpm": 120, "strength": 1}))
    run(go())
    inside = [c for t, c in lights(hub) if 5.0 <= t < 6.5]
    assert inside and all(c["rgb"] == [255, 0, 0] and c["mode"] == "flash" for c in inside)
    after = [c for t, c in lights(hub) if t >= 8.0]
    assert after and after[0]["rgb"] != [255, 0, 0]


def test_silence_is_one_dim_solid_and_no_flashes():
    d, hub, clk = make()

    async def go():
        await d.on_message(env("world.current", {"world": WORLD}))
        clk.t = 1.0
        await d.tick()                           # initial solid base
        hub.sent.clear()
        for i in range(10):
            clk.t = 2 + i * 0.2
            await d.on_message(env("audio.features", {"energy": 0.0, "silent": True}))
            await d.on_message(env("audio.beat", {"tempo_bpm": 120, "strength": 1}))
            await d.tick()
    run(go())
    cmds = lights(hub)
    assert len(cmds) == 1 and cmds[0][1]["mode"] == "solid"
    assert max(cmds[0][1]["rgb"]) < 40


def test_transition_glows_then_settles_on_new_base():
    d, hub, clk = make()

    async def go():
        await d.on_message(env("world.transition", {"from": None, "to": WORLD, "started": 0, "duration_ms": 3000}))
        clk.t = 3.2
        await d.tick()
    run(go())
    cmds = [c for _, c in lights(hub)]
    assert cmds[0]["mode"] == "pulse" and cmds[0]["ms"] == 3000
    assert cmds[-1]["mode"] == "solid" and cmds[-1]["rgb"] == [0, 128, 128]
