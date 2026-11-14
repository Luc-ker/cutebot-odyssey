import sonar


def test_gate():
    assert sonar.gate(80, 5) == 0
    assert sonar.gate(-80, 5) == -80
    assert sonar.gate(80, 30) == 80
    assert sonar.gate(80, None) == 80


def test_median_of_last_three_and_zero_ignored():
    seq = iter([30, 0, 10, 20, 90])
    s = sonar.Sonar(lambda: next(seq))
    assert s.read_cm() == 30          # [30]
    assert s.read_cm() == 30          # 0 ignored
    assert s.read_cm() == 30          # [30,10] -> upper median
    assert s.read_cm() == 20          # [30,10,20]
    assert s.read_cm() == 20          # [10,20,90]


def test_no_reading_yet_is_none():
    assert sonar.Sonar(lambda: 0).read_cm() is None
