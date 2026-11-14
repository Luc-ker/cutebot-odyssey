// Hub client for browser pages (T08, contracts C2/C9).
//
//   const hub = await connectHub();             // or connectHub(url, src)
//   hub.pub("narration.say", {text: "hi", priority: 1});
//   const off = hub.sub("vision.*", env => ...);  // off() removes this callback
//   hub.onStatus(s => ...);                       // "open" | "closed"
//
// Reconnects with backoff (0.5 s doubling to 5 s) and re-sends every subscription after a reconnect.
// Messages published while disconnected are dropped, except the last `webrtc.signal`, which is retried
// once after the next reconnect.

const RETRY_ONCE_TOPICS = new Set(["webrtc.signal"]);

export function defaultHubUrl(loc = globalThis.location) {
  if (!loc) return "ws://localhost:8765/hub";
  const scheme = loc.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${loc.host}/hub`;
}

export function topicMatches(pattern, topic) {
  if (pattern.endsWith("*")) return topic.startsWith(pattern.slice(0, -1));
  return pattern === topic;
}

export function connectHub(url, src, opts = {}) {
  const hub = createHub(url || defaultHubUrl(), src || defaultSrc(), opts);
  return hub.ready.then(() => hub);
}

function defaultSrc() {
  const path = globalThis.location?.pathname || "";
  const page = path.split("/").filter(Boolean)[0];
  return page ? `web.${page}` : "web";
}

export function createHub(url, src, opts = {}) {
  const WS = opts.WebSocket || globalThis.WebSocket;
  const minDelay = opts.minDelay ?? 500;
  const maxDelay = opts.maxDelay ?? 5000;
  const setTimer = opts.setTimeout || globalThis.setTimeout.bind(globalThis);
  const now = opts.now || (() => Date.now() / 1000);

  const handlers = new Map(); // pattern -> Set(callback)
  const statusCbs = new Set();
  let ws = null;
  let isOpen = false;
  let delay = minDelay;
  let closedByUser = false;
  let pendingRetry = null; // last webrtc.signal published while disconnected
  let resolveReady;
  const ready = new Promise((r) => (resolveReady = r));

  function emitStatus(s) {
    for (const cb of statusCbs) {
      try {
        cb(s);
      } catch (e) {
        console.error("hub status callback failed", e);
      }
    }
  }

  function rawSend(obj) {
    if (!isOpen || !ws) return false;
    try {
      ws.send(JSON.stringify(obj));
      return true;
    } catch {
      return false;
    }
  }

  function sendSub(patterns) {
    if (patterns.length) rawSend({ op: "sub", topics: patterns });
  }

  function dispatch(raw) {
    let env;
    try {
      env = JSON.parse(typeof raw === "string" ? raw : String(raw));
    } catch {
      return;
    }
    if (!env || typeof env.topic !== "string") return;
    for (const [pattern, cbs] of handlers) {
      if (!topicMatches(pattern, env.topic)) continue;
      for (const cb of cbs) {
        try {
          cb(env);
        } catch (e) {
          console.error(`hub callback for ${pattern} failed`, e);
        }
      }
    }
  }

  function open() {
    if (closedByUser) return;
    let sock;
    try {
      sock = new WS(url);
    } catch {
      scheduleReconnect();
      return;
    }
    ws = sock;
    sock.onopen = () => {
      if (ws !== sock) return;
      isOpen = true;
      delay = minDelay;
      sendSub([...handlers.keys()]);
      if (pendingRetry) {
        rawSend(pendingRetry);
        pendingRetry = null;
      }
      emitStatus("open");
      resolveReady();
    };
    sock.onmessage = (ev) => {
      if (ws === sock) dispatch(ev.data);
    };
    sock.onerror = () => {}; // onclose follows
    sock.onclose = () => {
      if (ws !== sock) return;
      const wasOpen = isOpen;
      isOpen = false;
      ws = null;
      if (wasOpen) emitStatus("closed");
      scheduleReconnect();
    };
  }

  function scheduleReconnect() {
    if (closedByUser) return;
    const d = delay;
    delay = Math.min(delay * 2, maxDelay);
    setTimer(open, d);
  }

  const hub = {
    ready,
    url,
    src,
    get isOpen() {
      return isOpen;
    },
    pub(topic, data = {}) {
      const env = { op: "pub", topic, ts: now(), src, data };
      if (rawSend(env)) return true;
      if (RETRY_ONCE_TOPICS.has(topic)) pendingRetry = env;
      return false;
    },
    sub(pattern, cb) {
      let cbs = handlers.get(pattern);
      if (!cbs) {
        cbs = new Set();
        handlers.set(pattern, cbs);
        sendSub([pattern]);
      }
      cbs.add(cb);
      return () => cbs.delete(cb);
    },
    onStatus(cb) {
      statusCbs.add(cb);
      return () => statusCbs.delete(cb);
    },
    close() {
      closedByUser = true;
      const sock = ws;
      ws = null;
      if (isOpen) {
        isOpen = false;
        emitStatus("closed");
      }
      try {
        sock?.close();
      } catch {
        /* ignore */
      }
    },
  };

  open();
  return hub;
}
