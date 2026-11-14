import rumble


def test_v300_on_then_off():
    log = []
    r = rumble.Rumble(log.append)
    r.on_packet({"type": "V", "ms": 300}, 0)
    r.tick(100)
    assert log == [True]
    r.tick(300)
    assert log == [True, False]


def test_shorter_ignored_longer_extends_and_cap():
    log = []
    r = rumble.Rumble(log.append)
    r.start(500, 0)
    r.start(100, 50)
    r.tick(500)
    assert log == [True, False]
    r.start(5000, 1000)
    r.tick(1999)
    assert log[-1] is True
    r.tick(2000)
    assert log[-1] is False
