import drive

C = (512, 512)
F = drive.Y_FORWARD_SIGN
R = drive.X_RIGHT_SIGN


def test_centre_and_deadzone():
    assert drive.axes_to_drive(512, 512, C) == (0, 0)
    assert drive.axes_to_drive(512 + 30, 512 - 30, C) == (0, 0)  # ~6 %


def test_full_forward_and_reverse():
    assert drive.axes_to_drive(512, 512 + 500 * F, C)[0] == 100
    assert drive.axes_to_drive(512, 512 - 500 * F, C)[0] == -100


def test_turn_sign_and_fine_control_near_centre():
    assert drive.axes_to_drive(512 + 500 * R, 512, C)[1] == 100
    small = drive.axes_to_drive(512, 512 + 120 * F, C)[0]
    big = drive.axes_to_drive(512, 512 + 240 * F, C)[0]
    assert 0 < small < big / 2 + 1


def test_sender_rate_seq_and_zero_keepalive():
    sent = []
    s = drive.DriveSender(lambda: (512, 512), sent.append, hz=25)
    s.calibrate()
    for ms in range(0, 1000, 5):
        s.tick(ms)
    assert 24 <= len(sent) <= 26
    assert sent[0] == "D,0,0,0" and sent[1] == "D,0,0,1"
