"""T14 - line-sensor table edge stop.

TAPE: stick matt BLACK electrical tape (or white, see EDGE_VALUE) in a 2-3 cm band
just inside the table edge, on a light table. Line sensors: P13 (left), P14 (right)
(CHECK vendor docs). To test: hold the robot over the tape, run `line_state()` and
confirm it returns the EDGE_VALUE for the sensors above the tape.
"""
EDGE_VALUE = 1  # reading that means "over the tape". Flip to 0 if your tape reads inverted.


def line_state():
    from microbit import pin13, pin14
    return pin13.read_digital(), pin14.read_digital()


def edge_gate(throttle, turn, l, r):
    """Block forward motion over the tape; reverse and turning stay allowed."""
    if (l == EDGE_VALUE or r == EDGE_VALUE) and throttle > 0:
        return 0, turn
    return throttle, turn
