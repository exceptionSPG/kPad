/* Connection + framing + tuning store. Exposes window.NET and window.TUNE.
   Slice 1: move frames out, ping/pong RTT, auto-reconnect with backoff.
   Pairing and full visibility handling come in later slices. */

(function () {
  "use strict";

  // ---- tuning store — the single source of pointer-feel defaults ----------
  // Each phone persists its own tuned curve in localStorage; these are only the
  // values a brand-new phone starts from. There is no server-side copy.
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
  function frameButton(button, down) {
    const b = new ArrayBuffer(3), v = new DataView(b);
    v.setUint8(0, PROTO.OP_BUTTON);
    v.setUint8(1, button);
    v.setUint8(2, down ? 1 : 0);
    return b;
  }
  function frameScroll(sx, sy) {
    const b = new ArrayBuffer(5), v = new DataView(b);
    v.setUint8(0, PROTO.OP_SCROLL);
    v.setInt16(1, clamp16(sx), true);
    v.setInt16(3, clamp16(sy), true);
    return b;
  }
  function frameKey(keycode, modifiers) {
    const b = new ArrayBuffer(5), v = new DataView(b);
    v.setUint8(0, PROTO.OP_KEY);
    v.setUint16(1, keycode & 0xffff, true);
    v.setUint16(3, (modifiers || 0) & 0xffff, true);
    return b;
  }
  function framePair(str) {
    const bytes = new TextEncoder().encode(str);
    const b = new Uint8Array(1 + bytes.length);
    b[0] = PROTO.OP_PAIR;
    b.set(bytes, 1);
    return b.buffer;
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

  // ---- pairing -------------------------------------------------------------
  let paired = false;                // per-connection; re-run on every reconnect
  let lastPairWasToken = false;      // did we present a stored token or a code?
  const pairEl = document.getElementById("pair");
  const pairInput = document.getElementById("pairCode");
  const pairErr = document.getElementById("pairErr");

  function showPair(err) {
    pairErr.textContent = err || "";
    pairInput.value = "";
    pairEl.classList.remove("hidden");
    setTimeout(() => pairInput.focus(), 50);
  }
  function hidePair() { pairEl.classList.add("hidden"); }

  function sendPair(str) {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(framePair(str));
  }
  function beginPairing() {
    paired = false;
    const token = localStorage.getItem("pairToken");
    const urlCode = new URLSearchParams(location.search).get("code");
    if (token) { lastPairWasToken = true; sendPair(token); }
    else if (urlCode) { lastPairWasToken = false; sendPair(urlCode); }
    else showPair("");           // first-time: ask for the code
  }
  function onPairResult(ok, token) {
    if (ok) {
      paired = true;
      if (token) localStorage.setItem("pairToken", token);
      hidePair();
      setStatus("connected", "ok");
      return;
    }
    paired = false;
    if (lastPairWasToken) {
      // A stored token was rejected -> the Mac forgot us. Drop it, ask for code.
      localStorage.removeItem("pairToken");
      lastPairWasToken = false;
      showPair("This Mac no longer recognizes this phone — enter the code again.");
    } else {
      showPair("Wrong code. Check your Mac and try again.");
    }
  }

  function submitCode() {
    const c = pairInput.value.replace(/\D/g, "").slice(0, 6);
    if (c.length !== 6) { pairErr.textContent = "Enter all 6 digits."; return; }
    lastPairWasToken = false;
    sendPair(c);
  }
  document.getElementById("pairBtn").addEventListener("click", submitCode);
  pairInput.addEventListener("input", function () {
    if (pairInput.value.replace(/\D/g, "").length >= 6) submitCode();
  });

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
      setStatus("pairing…", "");
      beginPairing();                 // must be the first frame we send
    };
    ws.onmessage = function (ev) {
      if (typeof ev.data === "string") return;
      const v = new DataView(ev.data);
      const op = v.getUint8(0);
      if (op === PROTO.OP_PAIR_RESULT) {
        const ok = v.getUint8(1) === 0;
        const token = new TextDecoder().decode(new Uint8Array(ev.data, 2));
        onPairResult(ok, token);
        return;
      }
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
    // Input is gated on `paired` — nothing reaches the Mac until the handshake
    // succeeds (the server ignores it too, but gating here avoids wasted frames).
    move: (dx, dy) => { if (paired) send(frameMove(dx, dy)); },
    button: (button, down) => { if (paired) send(frameButton(button, down)); },
    scroll: (sx, sy) => { if (paired) send(frameScroll(sx, sy)); },
    key: (keycode, modifiers) => { if (paired) send(frameKey(keycode, modifiers)); },
    // Safety: let go of every button (used on page-hide / phone-lock, when the
    // socket may still be open so the server's own release_all hasn't fired).
    releaseButtons: () => {
      if (!paired) return;
      send(frameButton(PROTO.BTN_LEFT, 0));
      send(frameButton(PROTO.BTN_RIGHT, 0));
      send(frameButton(PROTO.BTN_MIDDLE, 0));
    },
    isOpen: () => !!ws && ws.readyState === WebSocket.OPEN,
    isPaired: () => paired,
    rtt: () => rttEMA,
  };

  connect();
})();
