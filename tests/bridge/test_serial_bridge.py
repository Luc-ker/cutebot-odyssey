import asyncio

from server.bridge.serial_bridge import SerialBridge


class FakeHub:
    def __init__(self):
        self.sent = []

    async def pub(self, topic, data):
        self.sent.append((topic, data))

    def sub(self, pattern, cb):
        pass


class FakePort:
    def __init__(self, lines=()):
        self.lines = list(lines)
        self.written = []
        self.closed = False

    def readline(self):
        return self.lines.pop(0) if self.lines else b""

    def write(self, b):
        self.written.append(b.decode())

    def close(self):
        self.closed = True


def make(port=None, hz=10):
    t = [0.0]
    hub = FakeHub()
    b = SerialBridge(hub, {"LIGHT_MAX_HZ": hz}, open_port=lambda: port, clock=lambda: t[0])
    b.port = port
    return b, hub, t


def test_telemetry_line_becomes_hub_message():
    b, hub, _ = make(FakePort())
    asyncio.run(b.handle_line("T,12,0,1,0\n"))
    assert hub.sent == [("robot.telemetry", {"distance_cm": 12, "line": [0, 1], "override": False})]


def test_button_line_becomes_named_button():
    b, hub, _ = make(FakePort())
    asyncio.run(b.handle_line("B,H"))
    assert hub.sent == [("gamepad.button", {"button": "horn"})]


def test_garbage_is_ignored():
    b, hub, _ = make(FakePort())
    asyncio.run(b.handle_line("T,abc"))
    asyncio.run(b.handle_line(""))
    assert hub.sent == []


def test_light_rate_cap_but_recoil_always_written():
    port = FakePort()
    b, hub, t = make(port, hz=10)

    async def go():
        for i in range(50):
            t[0] = i * 0.02
            await b.on_cmd({"data": {"kind": "lights", "mode": "flash", "rgb": [255, 0, 0], "ms": 100}})
            if i == 25:
                await b.on_cmd({"data": {"kind": "recoil", "ms": 700}})
            await b.flush()
    asyncio.run(go())
    lights = [w for w in port.written if w.startswith("L,")]
    assert 0 < len(lights) <= 10
    assert "R,700\n" in port.written
    assert lights[0] == "L,F,255,0,0,100\n"


def test_latest_light_wins_when_throttled():
    port = FakePort()
    b, _, t = make(port, hz=10)

    async def go():
        await b.on_cmd({"data": {"kind": "lights", "mode": "solid", "rgb": [1, 1, 1], "ms": 0}})
        t[0] = 0.01
        await b.on_cmd({"data": {"kind": "lights", "mode": "solid", "rgb": [9, 9, 9], "ms": 0}})
        t[0] = 0.2
        await b.flush()
    asyncio.run(go())
    assert port.written == ["L,S,1,1,1,0\n", "L,S,9,9,9,0\n"]


def test_unplugged_port_is_reported_and_recovers():
    class BoomPort(FakePort):
        def readline(self):
            raise OSError("unplugged")

    attempts = []

    def opener():
        attempts.append(1)
        if len(attempts) == 1:
            return BoomPort()
        raise OSError("gone")

    hub = FakeHub()
    b = SerialBridge(hub, {}, open_port=opener)

    async def go():
        task = asyncio.create_task(b.loop())
        await asyncio.sleep(0.3)
        task.cancel()
    asyncio.run(go())
    assert any(t == "system.health" and d["ok"] is False for t, d in hub.sent)
