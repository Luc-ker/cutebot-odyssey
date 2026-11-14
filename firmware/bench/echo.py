"""T24 - radio bench echo firmware for a SPARE micro:bit standing in for the Cutebot.

Answers every D,<throttle>,<turn>,<seq> with T,<seq>,0,0,0 (the distance field carries the seq), so
the bridge forwards it to the laptop and scripts/radio_bench.py can count loss and round trips.
"""
RADIO_GROUP = 42   # same as shared/config.json
RADIO_CHANNEL = 7


def echo_reply(msg):
    """Pure helper (host-testable): reply packet for a received message, or None."""
    if msg and msg.startswith("D,"):
        p = msg.split(",")
        if len(p) == 4:
            return "T,%s,0,0,0" % p[3]
    return None


def main():
    from microbit import sleep
    import radio
    radio.config(group=RADIO_GROUP, channel=RADIO_CHANNEL, length=32, queue=8)
    radio.on()
    while True:
        m = radio.receive()
        if m is None:
            sleep(1)
            continue
        r = echo_reply(m)
        if r:
            radio.send(r)


if __name__ == "__main__":
    main()
