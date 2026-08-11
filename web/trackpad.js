/* Trackpad surface + pointer acceleration + dev panel.
   Slice 1: single-finger move only. Gestures (tap, right-click, scroll,
   drag-lock) come in Slice 2 — pointer state is already keyed by pointerId so
   multi-touch slots in without a rewrite. */

(function () {
  "use strict";

  const pad = document.getElementById("pad");
  const TUNE = window.TUNE;
  const NET = window.NET;

  // Per-pointer last position, keyed by pointerId (multi-touch ready).
  const pointers = new Map();        // id -> {x, y}
  let accX = 0, accY = 0;            // accumulated accelerated delta (with fractional carry)
  let rafPending = false;

  function flush() {
    rafPending = false;
    const dx = Math.round(accX), dy = Math.round(accY);
    accX -= dx; accY -= dy;          // keep sub-pixel remainder for smoothness
    if (dx !== 0 || dy !== 0) NET.move(dx, dy);
  }
  function scheduleFlush() {
    if (!rafPending) { rafPending = true; requestAnimationFrame(flush); }
  }

  function accelerate(dx, dy) {
    const speed = Math.hypot(dx, dy);
    if (speed < TUNE.deadzone) return;          // drop sub-pixel jitter
    const gain = 1 + Math.min(speed * TUNE.k, TUNE.cap);
    accX += dx * gain;
    accY += dy * gain;
    scheduleFlush();
  }

  pad.addEventListener("pointerdown", function (e) {
    pad.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    pad.classList.add("active");
  });

  pad.addEventListener("pointermove", function (e) {
    const p = pointers.get(e.pointerId);
    if (!p) return;
    // Only single-finger moves the cursor for now.
    if (pointers.size === 1) accelerate(e.clientX - p.x, e.clientY - p.y);
    p.x = e.clientX; p.y = e.clientY;
  });

  function endPointer(e) {
    pointers.delete(e.pointerId);
    if (pointers.size === 0) pad.classList.remove("active");
  }
  pad.addEventListener("pointerup", endPointer);
  pad.addEventListener("pointercancel", endPointer);

  // Belt-and-suspenders: never let the page itself scroll/zoom.
  document.addEventListener("touchmove", (e) => e.preventDefault(), { passive: false });
  document.addEventListener("gesturestart", (e) => e.preventDefault());

  // ------------------------------------------------------------ dev panel --
  const dev = document.getElementById("dev");
  const fields = ["k", "cap", "deadzone", "scrollMult"];

  function syncPanel() {
    fields.forEach(function (f) {
      const input = document.getElementById(f);
      const out = document.getElementById(f + "Out");
      input.value = TUNE[f];
      out.textContent = TUNE[f];
    });
  }
  fields.forEach(function (f) {
    const input = document.getElementById(f);
    input.addEventListener("input", function () {
      TUNE[f] = parseFloat(input.value);
      document.getElementById(f + "Out").textContent = input.value;
      TUNE.save();
    });
  });

  function openDev() { syncPanel(); dev.classList.remove("hidden"); }
  function closeDev() { dev.classList.add("hidden"); }
  document.getElementById("closeDev").addEventListener("click", closeDev);
  document.getElementById("copyCfg").addEventListener("click", function () {
    const cfg = { k: TUNE.k, cap: TUNE.cap, deadzone: TUNE.deadzone, scrollMult: TUNE.scrollMult };
    const json = JSON.stringify(cfg, null, 4);
    const ta = document.createElement("textarea");   // no async clipboard on http://
    ta.value = json; document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (_) {}
    ta.remove();
    const btn = document.getElementById("copyCfg");
    const old = btn.textContent; btn.textContent = "copied ✓";
    setTimeout(() => (btn.textContent = old), 1200);
  });

  // Open via ?dev=1 …
  if (new URLSearchParams(location.search).get("dev") === "1") openDev();

  // … or triple-tap the top-left corner (60×60 zone).
  let taps = [];
  document.addEventListener("pointerdown", function (e) {
    if (e.clientX > 60 || e.clientY > 60) { taps = []; return; }
    const now = Date.now();
    taps = taps.filter((t) => now - t < 600);
    taps.push(now);
    if (taps.length >= 3) { taps = []; openDev(); }
  }, true);
})();
