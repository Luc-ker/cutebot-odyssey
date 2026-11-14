// Map store (T85): the latest message per hub topic, for the map layers (contract C9).
//
//   const store = createStore();
//   hub.sub("world.*", store.apply);   // ...and robot.state, vision.state, audio.*, system.*, video.status
//   layer.update(store.state);
//
// `state[topic]` is the latest `data` for that topic, so layers read `state["world.objects"]`,
// `state["robot.state"]`, `state["world.current"]`, `state["vision.state"]`, `state["audio.beat"]`, ...
// Extras the layers need because "latest only" would lose information:
//   state.lastBeatT     local arrival time (s) of the last audio.beat — no sender clock skew
//   state.received[t]   local arrival time (s) of the latest message on topic t
//   state.events        recent world.event payloads, each with `_t` (arrival) and `_seq`, newest last
//   state.transition    the latest world.transition with `_t` (arrival) and `_seq`
//   state.health        {service: {ok, detail, _t}} from system.health, one entry per service
//   state.seq           bumps on every message, so a layer can skip work when nothing changed
//   state.config        the shared config (set by the page)
// system.reset clears everything except config.

const MAX_EVENTS = 40;

export function createStore({ now = () => performance.now() / 1000, config = {} } = {}) {
  const state = {};

  function reset() {
    const seq = state.seq ?? 0;
    for (const k of Object.keys(state)) if (k !== "config") delete state[k];
    Object.assign(state, {
      lastBeatT: null,
      received: {},
      events: [],
      transition: null,
      health: {},
      seq: seq + 1,
    });
    state.config ??= config;
  }

  function apply(env) {
    if (!env || typeof env.topic !== "string") return;
    const { topic } = env;
    const data = env.data ?? {};
    const t = now();
    if (topic === "system.reset") {
      reset();
      state.received[topic] = t;
      return;
    }
    state[topic] = data;
    state.received[topic] = t;
    state.seq += 1;
    switch (topic) {
      case "audio.beat":
        state.lastBeatT = t;
        break;
      case "world.event":
        state.events.push({ ...data, _t: t, _seq: state.seq });
        if (state.events.length > MAX_EVENTS) state.events.splice(0, state.events.length - MAX_EVENTS);
        break;
      case "world.transition":
        state.transition = { ...data, _t: t, _seq: state.seq };
        break;
      case "system.health":
        if (data.service) state.health[data.service] = { ok: Boolean(data.ok), detail: data.detail ?? "", _t: t };
        break;
      default:
    }
  }

  /** world.event payloads newer than `seq` (for layers that react to events). */
  function eventsSince(seq) {
    return state.events.filter((e) => e._seq > seq);
  }

  reset();
  return { state, apply, reset, eventsSince };
}
