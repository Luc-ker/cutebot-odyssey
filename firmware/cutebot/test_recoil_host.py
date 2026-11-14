import recoil


def setup_function(_):
    recoil.reset()


def test_phases():
    recoil.start_recoil(1000, 0)
    assert recoil.command(100)[0] < 0 and recoil.command(100)[1] == 0
    t, r = recoil.command(800)
    assert t == 0 and r != 0
    assert recoil.active(999)
    assert not recoil.active(1000)
    assert recoil.command(1000) == (0, 0)


def test_restart_does_not_stack():
    recoil.start_recoil(1000, 0)
    recoil.start_recoil(1000, 900)
    assert recoil.active(1800)
    assert not recoil.active(1900)
