import telemetry


def test_rate_is_ten_hz():
    sent = []
    t = telemetry.Telemetry(sent.append)
    for ms in range(0, 1000, 10):
        t.maybe_send(ms, 25, (0, 0), False)
    assert 9 <= len(sent) <= 11
    assert all(len(p) <= 32 for p in sent)


def test_override_change_within_100ms():
    sent = []
    t = telemetry.Telemetry(sent.append)
    t.maybe_send(0, 25, (0, 0), False)
    got = None
    for ms in range(10, 120, 10):
        t.maybe_send(ms, 25, (0, 0), True)
        if sent and sent[-1].endswith(",1"):
            got = ms
            break
    assert got is not None and got <= 100


def test_caps_and_formats():
    sent = []
    telemetry.Telemetry(sent.append).maybe_send(0, 999.6, (1, 0), False)
    assert sent == ["T,400,1,0,0"]
