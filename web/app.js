/* Connection + framing + tuning store. Exposes window.NET and window.TUNE.
   Slice 1: move frames out, ping/pong RTT, auto-reconnect with backoff.
   Pairing and full visibility handling come in later slices. */

(function () {
  "use strict";

  // ---- tuning store (mirrors server/config.py DEFAULT_POINTER) -------------
  const DEFAULTS = { k: 0.08, cap: 3.0, deadzone: 0.4, scrollMult: 1.0 };
  const TUNE = Object.assign({}, DEFAULTS);
  try {
    const saved = JSON.parse(localStorage.getItem("tune") || "{}");
    Object.assign(TUNE, saved);
  } catch (_) {}
  TUNE.save = function () {
    localStorage.setItem("tune", JSON.stringify({
      k: TUNE.k, cap: TUNE.cap, deadzone: TUNE.deadzone, scrollMult: TUNE.scrollMult,
    }));
  };
  window.TUNE = TUNE;

  // ---- frame builders ------------------------------------------------------
  const clamp16 = (n) => Math.max(-32768, Math.min(32767, n | 0));

  function frameMove(dx, dy) {
    const b = new ArrayBuffer(5), v = new DataView(b);
    v.setUint8(0, PROTO.OP_MOVE);
    v.setInt16(1, clamp16(dx), true);
    v.setInt16(3, clamp16(dy), true);
    return b;
  }
  function framePing(seq) {
    const b = new ArrayBuffer(5), v = new DataView(b);
    v.setUint8(0, PROTO.OP_PING);
    v.setUint32(1, seq >>> 0, true);
    return b;
  }

  // ---- connection ----------------------------------------------------------
  const statusText = document.getElementById("statusText");
  const dot = document.getElementById("dot");
  const rttEl = document.getElementById("rtt");
  const devRtt = document.getElementById("devRtt");

  let ws = null;
  let backoff = 300;                 // ms, grows to a cap on repeated failures
  let pingSeq = 0;
  const pingTimes = new Map();       // seq -> performance.now()
  let rttEMA = null;

  function setStatus(text, cls) {
    statusText.textContent = text;
    dot.className = "dot" + (cls ? " " + cls : "");
  }

  function showRtt() {
    const t = rttEMA == null ? "—" : Math.round(rttEMA) + " ms";
    rttEl.textContent = t === "—" ? "" : t;
    if (devRtt) devRtt.textContent = "rtt " + t;
  }

  function connect() {
    const url = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws";
    setStatus("connecting…", "");
    try {
      ws = new WebSocket(url);
    } catch (_) {
      return scheduleReconnect();
    }
    ws.binaryType = "arraybuffer";

    ws.onopen = function () {
      backoff = 300;
      setStatus("connected", "ok");
    };
    ws.onmessage = function (ev) {
      if (typeof ev.data === "string") return;
      const v = new DataView(ev.data);
      const op = v.getUint8(0);
      if (op === PROTO.OP_PONG) {
        const seq = v.getUint32(1, true);
        const t0 = pingTimes.get(seq);
        if (t0 != null) {
          pingTimes.delete(seq);
          const rtt = performance.now() - t0;
          rttEMA = rttEMA == null ? rtt : rttEMA * 0.8 + rtt * 0.2;
          showRtt();
        }
      }
      // Other server->client opcodes handled in later slices.
    };
    ws.onclose = function () {
      setStatus("disconnected", "bad");
      rttEl.textContent = "";
      scheduleReconnect();
    };
    ws.onerror = function () {
      try { ws.close(); } catch (_) {}
    };
  }

  function scheduleReconnect() {
    setTimeout(connect, backoff);
    backoff = Math.min(backoff * 1.7, 5000);
  }

  // Latency probe every 500 ms while open.
  setInterval(function () {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const seq = (pingSeq = (pingSeq + 1) >>> 0);
    pingTimes.set(seq, performance.now());
    if (pingTimes.size > 32) pingTimes.delete(pingTimes.keys().next().value);
    ws.send(framePing(seq));
  }, 500);

  function send(buf) {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(buf);
  }

  window.NET = {
    send: send,
    move: (dx, dy) => send(frameMove(dx, dy)),
    isOpen: () => !!ws && ws.readyState === WebSocket.OPEN,
    rtt: () => rttEMA,
  };

  connect();
})();
