# Network runbook: laptop, phone and Jetson on the day

Goal: the phone on the robot streams to the eye page, the Jetson publishes to the hub, and the demo still
runs if the venue wifi dies. Follow it top to bottom. It takes about 15 minutes the first time.

```
            our own network (laptop hotspot, recommended)
  ┌───────────────┐   wss://192.168.137.1:8765   ┌──────────────┐
  │ Laptop        │ ◄──────────────────────────── │ Phone on bot │  camera page /phone/
  │ hub :8765     │ ◄──────────────────────────── │ Jetson       │  vision.state; snapshot :8080
  │ brain, bridge │ ──── internet (optional) ───► Gemini, video model
  └───────────────┘
  Gamepad ⇄ Cutebot ⇄ bridge micro:bit: micro:bit radio, never the network.
```

## 1. Make our own network

Don't rely on venue wifi (eduroam and similar often block device-to-device traffic). Pick one option:

**A. Laptop hotspot (recommended, Windows).** The laptop is always `192.168.137.1`.
1. Connect the laptop to the venue wifi or a phone's hotspot (this is only for internet).
2. Settings → Network & internet → **Mobile hotspot** → share *Wi-Fi*, band *2.4 GHz* (better range and
   compatibility) → Edit: name `genrator`, a password → turn **on**.
3. Connect the robot phone and the Jetson to `genrator`.

**B. A spare phone's hotspot.** Everyone joins it. The laptop's IP changes per network, so read it from the
launcher's output and re-run `make_cert.sh` if it changed.

**Jetson address.** `JETSON_HOST` defaults to `jetson.local` (mDNS, works out of the box on JetPack). If
it doesn't resolve, find the Jetson's IP (`hostname -I` on the Jetson, or the hotspot's device list) and
set `GENRATOR_JETSON_HOST=<ip>` on the laptop.

## 2. HTTPS certificate (the phone camera needs it)

Browsers only allow the camera on `https://` pages (or `localhost`). Once per laptop, and again if the
laptop's IP changes:

1. Install mkcert: `winget install FiloSottile.mkcert` (macOS `brew install mkcert`).
2. In Git Bash, from the repo: `bash scripts/make_cert.sh`. Accept the "install certificate" dialog.
3. Copy the two `GENRATOR_TLS_CERT` / `GENRATOR_TLS_KEY` lines it prints and run them in the terminal you
   launch from (or put the two paths in `TLS_CERT` / `TLS_KEY` in `shared/config.json` locally; don't commit them).

### Trust the certificate on the phone (once per phone)

Run `bash scripts/make_cert.sh --serve`. It prints a URL like `http://192.168.137.1:8000/genrator-rootCA.crt`.

- **Android (Chrome):** open the URL and download the file. Settings → Security & privacy → More security
  settings → Encryption & credentials → **Install a certificate** → **CA certificate** → Install anyway →
  pick `genrator-rootCA.crt`. (Menu names vary a little by brand; search settings for "CA certificate".)
- **iPhone (Safari only):** open the URL → Allow the profile download. Settings → **Profile Downloaded** →
  Install. Then Settings → General → About → **Certificate Trust Settings** → turn on full trust for
  "mkcert ...".

Press Ctrl-C in the `--serve` terminal when done.

*Emergency shortcut (Android Chrome only):* open `https://<laptop>:8765/phone/`, tap Advanced →
Proceed. The camera usually works after that. Trusting the CA is more reliable, so use it for the demo.

## 3. Ports

| Where | Port | What | Action |
|---|---|---|---|
| Laptop | 8765/TCP in | hub: pages + WebSocket | Windows asks to allow Python the first time you launch: tick **Private** *and* **Public** networks. Otherwise, in an admin PowerShell: `New-NetFirewallRule -DisplayName Genrator -Direction Inbound -Protocol TCP -LocalPort 8765 -Action Allow` |
| Laptop | 8000/TCP in | only while `make_cert.sh --serve` runs | same prompt |
| Jetson | 8080/TCP in | `snapshot.jpg` for Gemini | open by default on JetPack |
| Jetson | 22/TCP in | SSH (`launch.py --jetson`) | open by default |
| Laptop | 443/TCP out | Gemini, video model | needs internet |

## 4. Start and check every link

1. `python scripts/launch.py --jetson` (or without `--jetson`, starting `python3 jetson/main.py --hub wss://192.168.137.1:8765/hub` on the Jetson by hand).
2. Tick each one:

| ✓ | Link | How to check |
|---|---|---|
| ☐ | Laptop hub up | launcher shows `OK hub`; `https://192.168.137.1:8765/status/` opens on the laptop with no warning |
| ☐ | Phone reaches the hub | on the phone, `https://192.168.137.1:8765/status/` opens with a padlock and shows "Hub connected" |
| ☐ | Phone camera | open `/phone/` on the phone, allow the camera; status page shows `webrtc.signal` messages |
| ☐ | Eye page gets video | `/eye/` on the main screen shows the robot's view; status page shows `video.status` |
| ☐ | Jetson reaches the hub | status page: `vision.state` at ~10 msg/s, Jetson service ok |
| ☐ | Laptop reaches the Jetson | on the laptop, open `http://jetson.local:8080/snapshot.jpg` (or the IP): you see the table, people blurred |
| ☐ | Bridge micro:bit | status page: `serial_bridge` ok; `robot.telemetry` ~10 msg/s with the robot on |
| ☐ | Internet | status page: `brain.scheduler` ok, a world arrives a few seconds after music starts |

The Jetson connects with `wss://`. Copy `genrator-rootCA.crt` to it and run
`sudo cp genrator-rootCA.crt /usr/local/share/ca-certificates/ && sudo update-ca-certificates`, or point
it at `ws://` if the hub runs without TLS.

## 5. When the venue wifi fails

The laptop hotspot keeps the local network up even without internet, so only the cloud parts stop:

| Still works | Stops |
|---|---|
| Driving (radio, no network at all) | Gemini composing new worlds; new objects get roles from the local picker instead of Gemini |
| Beat → lights and visual pulses (local) | AI restyling of the robot view: the eye page falls back to the raw camera with a world tint and role labels |
| Overhead tracking, the map, giants, threats and recoil | |
| Fallback worlds: status page → world buttons | |
| Narration and sounds (browser speech on the laptop) | |

What to do: keep going and pick worlds with the status page buttons. To get internet back, connect the
laptop to a phone's hotspot. The Windows hotspot keeps sharing, and the phone and Jetson stay connected.

If the hotspot itself won't start without internet (some Windows versions), use option B (a phone hotspot)
and re-run `make_cert.sh` for the new IP. The phone CA doesn't need to be reinstalled.

## 6. Two-minute pre-demo checklist

- [ ] Laptop on mains power, sleep off, hotspot on
- [ ] Robot phone: on charge until the demo, auto-lock **off**, brightness low, Do Not Disturb on
- [ ] `TLS_CERT`/`TLS_KEY` set, the launcher shows `https://` URLs
- [ ] Status page all green (or known reds understood)
- [ ] One fallback world button tested
