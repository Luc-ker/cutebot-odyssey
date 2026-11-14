// node --test web/sound/tts.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createTts, pickVoice, voiceSettings } from "./tts.js";

const VOICES = [
  { name: "Thomas", lang: "fr-FR", voiceURI: "Thomas" },
  { name: "Samantha", lang: "en-US", voiceURI: "Samantha", default: true },
  { name: "Daniel", lang: "en-GB", voiceURI: "Daniel" },
  { name: "Fred", lang: "en-US", voiceURI: "Fred" },
];

class FakeUtterance {
  constructor(text) { this.text = text; }
}

function fakeSynth(voices = VOICES) {
  return {
    spoken: [],
    cancelled: 0,
    getVoices() { return voices; },
    speak(u) { this.spoken.push(u); },
    cancel() { this.cancelled += 1; },
  };
}

// Timers that never fire on their own, so only the fake events end a line.
const noTimers = { setTimeout: () => 1, clearTimeout: () => {} };

const tick = () => new Promise((r) => setImmediate(r));

test("speak resolves after the fake onend, not before", async () => {
  const synth = fakeSynth();
  const tts = createTts({ synth, Utterance: FakeUtterance, ...noTimers });
  let resolved = false;
  const p = tts.speak({ id: "n1", text: "The storm rolls in.", voice: "" }).then(() => { resolved = true; });
  await tick();
  assert.equal(synth.spoken.length, 1);
  assert.equal(synth.spoken[0].text, "The storm rolls in.");
  assert.equal(resolved, false);
  synth.spoken[0].onend();
  await p;
  assert.equal(resolved, true);
});

test("speak resolves on error too", async () => {
  const synth = fakeSynth();
  const tts = createTts({ synth, Utterance: FakeUtterance, ...noTimers });
  const p = tts.speak({ id: "n1", text: "Hello." });
  await tick();
  synth.spoken[0].onerror({ error: "synthesis-failed" });
  await p;
});

test("cancel stops speech and resolves the pending line", async () => {
  const synth = fakeSynth();
  const tts = createTts({ synth, Utterance: FakeUtterance, ...noTimers });
  const p = tts.speak({ id: "n1", text: "A long line." });
  await tick();
  tts.cancel();
  await p;
  assert.equal(synth.cancelled, 1);
});

test("a new line cancels the one still speaking", async () => {
  const synth = fakeSynth();
  const tts = createTts({ synth, Utterance: FakeUtterance, ...noTimers });
  const first = tts.speak({ id: "n1", text: "First." });
  await tick();
  const second = tts.speak({ id: "n2", text: "Second." });
  await first;
  await tick();
  assert.equal(synth.cancelled, 1);
  assert.equal(synth.spoken.at(-1).text, "Second.");
  synth.spoken.at(-1).onend();
  await second;
});

test("safety timeout resolves when the browser never fires onend", async () => {
  const synth = fakeSynth();
  let fire;
  const tts = createTts({ synth, Utterance: FakeUtterance, setTimeout: (fn) => { fire = fn; return 7; }, clearTimeout() {} });
  const p = tts.speak({ id: "n1", text: "Silent browser." });
  await tick();
  fire();
  await p;
});

test("empty text resolves without speaking; missing speechSynthesis resolves", async () => {
  const synth = fakeSynth();
  await createTts({ synth, Utterance: FakeUtterance, ...noTimers }).speak({ id: "x", text: "  " });
  assert.equal(synth.spoken.length, 0);
  await createTts({ synth: null, Utterance: null, ...noTimers }).speak({ id: "y", text: "Hi." });
});

test("voice hints adjust pitch and rate and choose a matching English voice", async () => {
  const synth = fakeSynth();
  const tts = createTts({ synth, Utterance: FakeUtterance, ...noTimers });
  const p = tts.speak({ id: "n1", text: "Beep.", voice: "robotic" });
  await tick();
  const u = synth.spoken[0];
  assert.equal(u.voice.name, "Fred");
  assert.equal(u.pitch, voiceSettings("robotic").pitch);
  assert.equal(u.rate, voiceSettings("robotic").rate);
  u.onend();
  await p;
});

test("pickVoice: English only, hint first, then default", () => {
  assert.equal(pickVoice(VOICES, "old").name, "Daniel");
  assert.equal(pickVoice(VOICES, "bright").name, "Samantha");
  assert.equal(pickVoice(VOICES, "").name, "Samantha");
  assert.equal(pickVoice(VOICES, "unknown-hint").lang.startsWith("en"), true);
  assert.equal(pickVoice([], "deep"), null);
  // "Female" must not satisfy the deep voice's \bmale\b pattern.
  assert.equal(pickVoice([{ name: "Google UK English Female", lang: "en-GB" }, { name: "Google UK English Male", lang: "en-GB" }], "deep").name,
    "Google UK English Male");
});

test("server TTS hook is used when given, and falls back to speechSynthesis on failure", async () => {
  const synth = fakeSynth();
  const played = [];
  class FakeAudio {
    constructor(url) { this.url = url; played.push(this); }
    play() { setImmediate(() => this.onended()); return Promise.resolve(); }
    pause() {}
  }
  const ok = createTts({ synth, Utterance: FakeUtterance, Audio: FakeAudio, serverTts: async () => "/tts/n1.wav", ...noTimers });
  await ok.speak({ id: "n1", text: "Server line." });
  assert.equal(played[0].url, "/tts/n1.wav");
  assert.equal(synth.spoken.length, 0);

  const bad = createTts({ synth, Utterance: FakeUtterance, Audio: FakeAudio, serverTts: async () => { throw new Error("down"); }, ...noTimers });
  const p = bad.speak({ id: "n2", text: "Fallback line." });
  await tick();
  assert.equal(synth.spoken.at(-1).text, "Fallback line.");
  synth.spoken.at(-1).onend();
  await p;
});
