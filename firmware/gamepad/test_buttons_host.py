import buttons


def run(b, until, state_at, step=5):
    for t in range(0, until, step):
        b.update(t, state_at(t))


def test_bouncy_press_is_one_action():
    sent = []
    b = buttons.Buttons(sent.append)

    def st(t):
        bounce = {0: True, 5: False, 10: True, 15: False, 20: True}
        if t < 25:
            down = bounce.get(t - t % 5, False)
        elif t < 200:
            down = True
        elif t < 220:
            down = (t // 5) % 2 == 0   # release bounce
        else:
            down = False
        return {"H": down}

    run(b, 400, st)
    assert b.fired == ["H"]
    assert sent == ["B,H"] * 3


def test_short_reset_sends_nothing_long_reset_sends_once():
    sent = []
    b = buttons.Buttons(sent.append)
    run(b, 1000, lambda t: {"R": t < 500})
    assert sent == [] and b.fired == []
    b2 = buttons.Buttons(sent.append)
    run(b2, 3000, lambda t: {"R": t < 2000})
    assert b2.fired == ["R"] and sent == ["B,R"] * 3


def test_repeats_are_spaced():
    times = []
    b = buttons.Buttons(lambda p: times.append(b_now[0]))
    b_now = [0]
    for t in range(0, 200, 5):
        b_now[0] = t
        b.update(t, {"L": t >= 10})
    gaps = [y - x for x, y in zip(times, times[1:])]
    assert len(times) == 3 and all(g >= 20 for g in gaps)
