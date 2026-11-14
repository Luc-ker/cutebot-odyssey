import motors


class FakeI2C:
    def __init__(self):
        self.writes = []

    def write(self, addr, buf):
        self.writes.append((addr, bytes(buf)))


def test_mix_cases():
    assert motors.mix(100, 0) == (100, 100)
    assert motors.mix(0, 100) == (100, -100)
    l, r = motors.mix(50, 50)
    assert -100 <= l <= 100 and -100 <= r <= 100
    assert motors.mix(0, 0) == (0, 0)


def test_mix_clamps_input():
    assert motors.mix(500, 0) == (100, 100)


def test_set_drive_bytes():
    i2c = FakeI2C()
    motors.Motors(i2c).set_drive(100, 0)
    assert i2c.writes == [(0x10, bytes([1, 0, 100, 0])), (0x10, bytes([2, 0, 100, 0]))]


def test_reverse_sets_direction_flag():
    i2c = FakeI2C()
    motors.Motors(i2c).set_drive(-50, 0)
    assert i2c.writes[0][1] == bytes([1, 1, 50, 0])


def test_stop():
    i2c = FakeI2C()
    motors.Motors(i2c).stop()
    assert [w[1][2] for w in i2c.writes] == [0, 0]
