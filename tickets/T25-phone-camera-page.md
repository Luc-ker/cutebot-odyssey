# T25 — Phone camera streaming page

## What Genrator is (read this first)

**Genrator** (repo `sonar-bot-tune`) is our DurHack 2026 project for the theme *Composition*. A player drives a
palm-sized robot car (an ELECFREAKS Cutebot) around a real table with a handheld gamepad, watching a live feed
from a phone strapped to the robot that an AI video model redraws as a fantasy world. **The music decides the
world:** Gemini listens to a few seconds of whatever is playing, looks at an overhead photo of the table, and
composes a world to match. A sea shanty turns the table into an ocean, heavy metal into a volcanic wasteland, a
lullaby into a snowy night. Every real object on the table gets a role in that world (the chair becomes a castle)
and keeps it, because a Jetson with an overhead camera tracks each object and remembers what it is. A second
screen shows the table as a living fantasy map. The robot's lights and the visuals pulse to the beat, hands
reaching over the table appear as giants, threats make the robot recoil, and a narrator announces what happens.
Change the song and the same table becomes a different world.

Full detail: `genrator-whitepaper.md`. Shared interfaces every ticket codes to: `tickets/CONTRACTS.md`.

---

## This ticket

> **Goal:** A web page opened on the phone strapped to the robot that streams its rear camera live to the laptop: the robot's eye.

| Priority | Component | Whitepaper |
|---|---|---|
| P0: needed for the core demo | Robot's-eye view | §7.2, §5 |

**Assigned to:** _unassigned_

**Owns (only edit these):** `web/phone/index.html`, `web/phone/phone.js`, `web/phone/phone.test.js`

## Contracts consumed (stub or fake them in your tests)
C2 (hub), C3 (`webrtc.signal`), hub client (T08)

This ticket does not wait on any other ticket. Code to the contracts in `tickets/CONTRACTS.md` and use local
stubs until the real modules land.

## Implement
- `getUserMedia` with the rear camera (`facingMode: "environment"`), 640×480 or 960×540, 24–30 fps.
- Create a WebRTC peer connection and send the offer/ICE over `webrtc.signal` with `to: "eye"`, `from: "phone"`; apply answers addressed to `phone`.
- Keep the screen awake (Wake Lock API) and show a big "streaming" indicator and battery level.
- Restart the connection automatically if it drops or the eye page reloads (listen for a `{to:"phone", sdp:null}` "hello" from the eye).
- Page must work over HTTPS (served by the hub with TLS, T07) because phone browsers block the camera on plain HTTP.

## Acceptance criteria
- [ ] Unit test with fake RTCPeerConnection: an incoming "hello" triggers a new offer.
- [ ] Manual: open on a phone, the eye page shows the live feed within 3 s; turning the eye page off and on recovers without touching the phone.

## Done when
- Every acceptance criterion is met (automated test, or a written manual check for hardware and visual work).
- Only the files listed under **Owns** were changed (contract changes go in a separate PR to `tickets/CONTRACTS.md`).
