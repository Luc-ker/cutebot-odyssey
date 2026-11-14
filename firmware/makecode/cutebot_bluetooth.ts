// Genrator Cutebot: Bluetooth controller program (MakeCode, micro:bit V2).
//
// Lets a phone drive the Cutebot over Bluetooth from the page at web/pad/ (Chrome on Android, or Chrome on a
// laptop). MicroPython can't use Bluetooth on the micro:bit, so this replaces firmware/cutebot/ on the robot.
//
// How to put it on the micro:bit (full steps in firmware/makecode/README.md):
//   1. makecode.microbit.org -> New Project -> switch the editor to JavaScript.
//   2. Gear icon -> Extensions -> add "bluetooth" (accept removing "radio" if asked).
//   3. Gear icon -> Project Settings -> "No Pairing Required: Anyone can connect via Bluetooth" -> Save.
//   4. Replace everything in the editor with this file, then Download and copy the .hex to the MICROBIT drive.
//
// No Cutebot extension is needed: the motors, headlights and ultrasonic sensor are driven directly, with the
// same I2C bytes and pins as ELECFREAKS' own library (github.com/elecfreaks/pxt-cutebot, cutebot.ts).
//
// Messages, one per line over the Bluetooth UART (the same text packets as contract C6):
//   D,<throttle -100..100>,<turn -100..100>,<seq>   drive. Send at least every 300 ms or the robot stops.
//   L,<S|F|P>,<r>,<g>,<b>,<ms>                       headlights: S = stay this colour, F/P = flash for ms
//   H                                                horn (micro:bit V2 speaker)
// The robot replies five times a second with
//   T,<distance_cm>,0,0,<blocked 0|1>                blocked = 1 while the ultrasonic stop holds it back

const CUTEBOT = 0x10       // I2C address of the Cutebot's controller chip
const FAILSAFE_MS = 300    // no drive message for this long -> stop
const STOP_CM = 8          // refuse to drive forward into anything closer than this
const NO_ECHO_CM = 999

let throttle = 0
let turn = 0
let lastDrive = 0
let distance = NO_ECHO_CM
let connected = false
let lastLeft = 1000        // impossible values, so the first drive() always writes
let lastRight = 1000
let baseR = 0
let baseG = 0
let baseB = 0
let flashUntil = 0

function clamp(v: number, lo: number, hi: number): number {
    return Math.max(lo, Math.min(hi, v))
}

function num(s: string, lo: number, hi: number): number {
    const n = parseInt(s)
    if (isNaN(n)) return 0
    return clamp(n, lo, hi)
}

// One wheel: register 0x01 = left, 0x02 = right; direction 0x02 = forward, 0x01 = backward; speed 0..100.
function wheel(reg: number, speed: number) {
    const buf = pins.createBuffer(4)
    buf[0] = reg
    buf[1] = speed > 0 ? 0x02 : 0x01
    buf[2] = Math.min(100, Math.abs(speed))
    buf[3] = 0
    pins.i2cWriteBuffer(CUTEBOT, buf)
}

// Both headlights: register 0x04 = left, 0x08 = right, then R, G, B.
function headlights(r: number, g: number, b: number) {
    const buf = pins.createBuffer(4)
    buf[0] = 0x04
    buf[1] = r
    buf[2] = g
    buf[3] = b
    pins.i2cWriteBuffer(CUTEBOT, buf)
    buf[0] = 0x08
    pins.i2cWriteBuffer(CUTEBOT, buf)
}

// Ultrasonic sensor: trigger P8, echo P12. Returns NO_ECHO_CM when nothing answers.
function readDistance(): number {
    pins.setPull(DigitalPin.P8, PinPullMode.PullNone)
    pins.digitalWritePin(DigitalPin.P8, 0)
    control.waitMicros(2)
    pins.digitalWritePin(DigitalPin.P8, 1)
    control.waitMicros(10)
    pins.digitalWritePin(DigitalPin.P8, 0)
    const us = pins.pulseIn(DigitalPin.P12, PulseValue.High, 25000)
    if (us <= 0) return NO_ECHO_CM
    return Math.idiv(us * 34, 2000)
}

function blocked(): boolean {
    return throttle > 0 && distance < STOP_CM
}

// Differential mix: turn > 0 turns right. Only writes to the motors when the speeds change.
function drive() {
    const t = blocked() ? 0 : throttle
    let left = t + turn
    let right = t - turn
    const biggest = Math.max(Math.abs(left), Math.abs(right))
    if (biggest > 100) {
        left = Math.idiv(left * 100, biggest)
        right = Math.idiv(right * 100, biggest)
    }
    if (left != lastLeft) {
        wheel(0x01, left)
        lastLeft = left
    }
    if (right != lastRight) {
        wheel(0x02, right)
        lastRight = right
    }
}

function stopAll() {
    throttle = 0
    turn = 0
    drive()
}

function handle(line: string) {
    const f = line.trim().split(",")
    const kind = f[0]
    if (kind == "D" && f.length >= 3) {
        throttle = num(f[1], -100, 100)
        turn = num(f[2], -100, 100)
        lastDrive = control.millis()
    } else if (kind == "L" && f.length >= 6) {
        const r = num(f[2], 0, 255)
        const g = num(f[3], 0, 255)
        const b = num(f[4], 0, 255)
        if (f[1] == "S") {
            baseR = r
            baseG = g
            baseB = b
            flashUntil = 0
        } else {
            flashUntil = control.millis() + num(f[5], 0, 5000)
        }
        headlights(r, g, b)
    } else if (kind == "H") {
        control.inBackground(function () {
            music.playTone(Note.C5, music.beat(BeatFraction.Quarter))
            music.playTone(Note.G4, music.beat(BeatFraction.Quarter))
        })
    }
}

bluetooth.onBluetoothConnected(function () {
    connected = true
    basic.showIcon(IconNames.Happy)
})

bluetooth.onBluetoothDisconnected(function () {
    connected = false
    stopAll()
    basic.showIcon(IconNames.Asleep)
})

bluetooth.onUartDataReceived(serial.delimiters(Delimiters.NewLine), function () {
    handle(bluetooth.uartReadUntil(serial.delimiters(Delimiters.NewLine)))
})

// Motors: failsafe, ultrasonic stop, and the end of a headlight flash.
basic.forever(function () {
    const now = control.millis()
    if (now - lastDrive > FAILSAFE_MS) {
        throttle = 0
        turn = 0
    }
    drive()
    if (flashUntil > 0 && now > flashUntil) {
        flashUntil = 0
        headlights(baseR, baseG, baseB)
    }
    basic.pause(20)
})

// Distance sensor and telemetry, five times a second.
loops.everyInterval(200, function () {
    distance = readDistance()
    if (connected) {
        bluetooth.uartWriteLine("T," + Math.min(distance, NO_ECHO_CM) + ",0,0," + (blocked() ? 1 : 0))
    }
})

bluetooth.startUartService()
headlights(0, 0, 0)
stopAll()
basic.showIcon(IconNames.Asleep)
