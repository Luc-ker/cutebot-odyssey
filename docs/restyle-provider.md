# Restyle provider: which real-time video model redraws the robot's eye (T27)

Status: **candidates researched and adapter written; numbers still to be measured on the venue
network.** The measured columns below are blank on purpose. Fill them from the spike page
(`scripts/restyle_spike/`) before the decision is final. Don't copy numbers from vendor pages.

## What we need (whitepaper §7.2, §10, §14)

- Browser in, browser out: the phone stream arrives in the eye page as a `MediaStream` (T26) and the
  output must be a `MediaStream` we can put in a `<video>` (C9 `createRestyler`).
- A text prompt that changes the style, and changes it again within a second or two (`video.prompt`
  from T29/T30 arrives up to 2×/s, plus the blend steps during a world change).
- Glass-to-glass lag low enough to drive comfortably. Rough target is under 300 ms, with 500 ms the
  worst we accept. The fallback (T33) covers outages, not slowness.
- Survives a weekend of demo use at a cost we can afford, with keys that stay out of the repo.

## Candidates

| | **Decart Lucy Restyle** (hosted, WebRTC) | **Daydream** (hosted StreamDiffusion, Livepeer) | **StreamDiffusion on a rented GPU** |
|---|---|---|---|
| Transport | WebRTC via `@decartai/sdk` in the browser | Create a stream via REST, push video in, play the output back. Exact ingest protocol to confirm | Self-run server; we write the WebRTC/WebSocket glue |
| Prompt change | `realtimeClient.setPrompt(text, {enhance})` | `PATCH` on the stream (the old prompt endpoint is deprecated) | Our own endpoint |
| Prompt weights | No (single prompt, optional reference image) | StreamDiffusion supports prompt blending, but whether the API exposes it is unconfirmed | Yes (we control it) |
| Browser auth | Short-lived client tokens minted server-side, or a static key | API key | Ours |
| Input spec | 1280×704 @ 25 fps per the docs (SDK sizes it) | Unconfirmed | Configurable |
| Setup effort | Low: adapter already written (`web/eye/restyler.js`, provider `decart`) | Medium | High: GPU rental, model weights, glue code, babysitting |
| **Measured: median fps** | | | |
| **Measured: glass-to-glass lag (ms)** | | | |
| **Measured: prompt change takes effect (ms)** | | | |
| **Measured: style strength (1–5, eyeballed)** | | | |
| **Cost for the weekend** | | | |

How to measure each row: open the spike page, pick the provider, press Start, then:

- **fps:** read off the stats line after 30 s of steady video.
- **lag:** press "Measure lag", then cover and uncover the webcam about 10 times. The page records how
  long each brightness edge takes to reach the output.
- **prompt change:** press "Cycle preset" about 8 times. The page times the gap between sending a prompt
  and a clear colour shift in the output.
- **style strength:** judge it by eye on the four presets (ocean, volcano, snow, kingdom). Can a
  player tell which world they're in?
- "Copy results JSON" and paste the output under *Raw results* below.

Measure on the network we'll actually use (venue wifi, or a phone hotspot as backup), with the phone
feed at 960×540.

## Recommendation (provisional, pending the numbers above)

- **Primary: Decart Lucy Restyle.** It's the only candidate with a documented browser WebRTC SDK and a
  one-call prompt change, so the adapter is already written against it. Confirm the lag and prompt
  latency before committing.
- **Backup: Daydream**, if Decart's lag or cost is a problem. It needs a second adapter in
  `restyler.js` (one new entry in `PROVIDERS`).
- **Always available: the `fake` provider.** It tints the raw feed by prompt keywords, needs no network,
  and is the default until Decart is enabled locally. The raw fallback (T33) sits on top of whichever provider runs.

To enable actual rendering, add `DECART_API_KEY` and `GENRATOR_RESTYLE_PROVIDER=decart` to the
ignored repository `.env`, restart the launcher, then refresh the Eye page. Use `--no-music` to keep
the Kingdom theme while transforming the live phone feed. The server serves nonsecret provider/model
settings at `/api/restyle/config`; `/shared/config.json` never contains credentials.

The Eye page requests a five-minute token immediately before each connection or reconnect through
`/api/restyle/token`. The hub keeps the permanent key server-side, restricts tokens to the selected
model and requesting origin, requires a same-origin custom-header request, and marks responses
`no-store`. The local hub is intended for a trusted LAN. The Eye status shows connection failures
while keeping the raw camera usable. Set `GENRATOR_RESTYLE_PROVIDER=fake` for offline tint preview.
The browser SDK is pinned to `@decartai/sdk@0.2.14`. Override the model with `GENRATOR_DECART_MODEL`;
default `lucy-2.6` (1280×720, 30 fps), Decart's realtime editing model: it can replace objects
(a bottle becomes a watchtower), which `lucy-restyle-2` cannot; restyle only changes the look and keeps
every shape. Lucy 2.6 costs $0.02 per second of rendering against $0.01 for `lucy-restyle-2`
(Decart pricing page, 2026-11); set `GENRATOR_DECART_MODEL=lucy-restyle-2` for cheaper style-only runs.
Incoming phone frames are copied into an owned canvas stream at the model’s width, height and frame
rate, scaled to cover the whole frame (overflow cropped). Letterbox bars are avoided because the model
paints them as separate scenery with visible seams. The SDK never owns the original phone camera track.

## Exact calls the adapter makes (Decart)

From docs.platform.decart.ai (JavaScript realtime SDK and the video-restyling page), read 2026-11:

```js
import { createDecartClient, models } from "@decartai/sdk";   // the adapter loads it from esm.sh

const client = createDecartClient({
  apiKeyProvider: async () => {
    const r = await fetch("/api/restyle/token", {headers: {"X-Genrator-Restyle": "1"}, cache: "no-store"});
    if (!r.ok) throw new Error("Renderer token unavailable");
    return (await r.json()).apiKey;
  },
  telemetry: false,
});
const rt = await client.realtime.connect(phoneStream, {
  model: models.realtime("lucy-2.6"),
  onRemoteStream: (styled) => { video.srcObject = styled; },
  initialState: { prompt: { text: firstPrompt, enhance: false } },  // literal prompt
});
rt.setPrompt(nextPrompt, { enhance: false });   // on every video.prompt (never in stable Kingdom mode)
rt.on("stats", s => ...);                       // WebRTC stats incl. glass-to-glass latency
rt.on("error", e => ...);                       // e.code: INVALID_API_KEY, TOKEN_EXPIRED, WEB_RTC_ERROR, ...
rt.disconnect();
```

Notes and open questions:

- `enhance` is off for every model, including Lucy 2.6 (whose guide recommends it): in live tests the
  enhancer turned our prompt into extra scene items, such as a table with bottles inside the castle world. Lucy 2.6 prompts work best as a command
  sentence followed by "The output will show ...", about 40–65 words and at most ~750 characters.
- **Keys:** the hub mints restricted short-lived client tokens; the browser uses `apiKeyProvider` to refresh credentials before connecting or reconnecting. Never place the permanent key in shared config or browser storage.
- **Model id:** default `lucy-2.6`; override with `GENRATOR_DECART_MODEL` in the local environment
  (for example `lucy-restyle-2`).
- **Stats fields:** the adapter reads `latency.medianMs` / `medianMs` from the `stats` event as a best
  guess. Check the real payload in the spike page console and fix the field name if it differs.
- **SDK version:** `DECART_SDK_URL` is pinned to `@decartai/sdk@0.2.14`.
- **Weights for T30:** Decart takes one prompt, so prompt blending stays textual (4 steps), which T30
  already does.

## Raw results

_Paste "Copy results JSON" output here, one block per provider and network._
