/* Trackpad surface: pointer acceleration + multi-touch gestures + dev panel.
 *
 * Gestures are derived from pointerId tracking (not a single pointer stream) so
 * a finger landing or lifting mid-gesture stays reliable:
 *   - one-finger drag         -> move cursor (accelerated)
 *   - one-finger tap          -> left click (two quick taps -> double click,
 *                                the server sets click-state)
 *   - two-finger tap          -> right click
 *   - two-finger drag         -> scroll, with inertia that runs on the phone
 *   - tap, then touch+drag     -> drag lock: press-hold-move drags; lifting keeps
 *                                the button down (locked); a tap drops it
 *
 * Safety: on page-hide / phone-lock we release every button here (the socket may
 * still be open); on socket close the server's release_all() is the backstop.
 */

(function () {
  "use strict";

  const pad = document.getElementById("pad");
  const TUNE = window.TUNE;
  const NET = window.NET;
  const BTN = { LEFT: PROTO.BTN_LEFT, RIGHT: PROTO.BTN_RIGHT, MIDDLE: PROTO.BTN_MIDDLE };

  // ---- gesture thresholds --------------------------------------------------
  const TAP_MS = 250;          // max duration of a tap
  const TAP_SLOP = 10;         // max movement (px) for a tap
  const TWO_WINDOW_MS = 140;   // 2nd finger must land within this of the 1st
  const LOCK_WINDOW_MS = 300;  // a touch this soon after a tap can start a drag-lock
  const HALF_NEAR = 22;        // 2nd touch must be this near the tap to arm drag-lock
  const SCROLL_FRICTION = 0.94;
  const SCROLL_MIN_V = 0.15;   // stop inertia below this px/frame
  const LOCK_SAFETY_MS = 6000; // auto-drop a stuck drag-lock

  // ---- move (accelerated, per-rAF batched) ---------------------------------
  const pts = new Map();       // pointerId -> {x0,y0,x,y,t0}
  let accX = 0, accY = 0, rafPending = false;

  function flushMove() {
    rafPending = false;
    const dx = Math.round(accX), dy = Math.round(accY);
    accX -= dx; accY -= dy;
    if (dx !== 0 || dy !== 0) NET.move(dx, dy);
  }
  function accelerate(dx, dy) {
    const speed = Math.hypot(dx, dy);
    if (speed < TUNE.deadzone) return;
    const gain = 1 + Math.min(speed * TUNE.k, TUNE.cap);
    accX += dx * gain; accY += dy * gain;
    if (!rafPending) { rafPending = true; requestAnimationFrame(flushMove); }
  }

  // ---- gesture state -------------------------------------------------------
  let mode = "idle";           // idle | scroll | drag | locked
  let moved = false;           // primary finger moved beyond slop
  let firstDownT = 0;
  let twoFingerActive = false; // 2 fingers touched during this cluster
  let twoTapCandidate = false;
  let twoStartT = 0;
  let twoStartCentroid = null;
  let scrolled = false;
  let lastCentroid = null;
  let scrollVX = 0, scrollVY = 0, inertiaRAF = 0;
  let lastTap = { t: -1e9, x: 0, y: 0 };
  let halfCandidate = false;   // a touch that may become a drag-lock
  let halfTimer = 0;
  let pendingLockTouch = false;
  let lockSafetyTimer = 0;

  function centroid() {
    let x = 0, y = 0;
    for (const p of pts.values()) { x += p.x; y += p.y; }
    const n = pts.size || 1;
    return { x: x / n, y: y / n };
  }

  function leftClick() { NET.button(BTN.LEFT, 1); NET.button(BTN.LEFT, 0); }
  function rightClick() { NET.button(BTN.RIGHT, 1); NET.button(BTN.RIGHT, 0); }

  function startDrag() {
    halfCandidate = false;
    clearTimeout(halfTimer);
    mode = "drag";
    NET.button(BTN.LEFT, 1);
    pad.classList.add("dragging");
  }
  function engageLock() {
    mode = "locked";
    pad.classList.remove("dragging");
    pad.classList.add("locked");
    clearTimeout(lockSafetyTimer);
    lockSafetyTimer = setTimeout(dropLock, LOCK_SAFETY_MS);
  }
  function dropLock() {
    clearTimeout(lockSafetyTimer);
    NET.button(BTN.LEFT, 0);
    mode = "idle";
    pad.classList.remove("locked");
  }

  // ---- inertia (runs on the phone; latency-independent) --------------------
  function cancelInertia() { if (inertiaRAF) { cancelAnimationFrame(inertiaRAF); inertiaRAF = 0; } }
  function startInertia() {
    cancelInertia();
    function step() {
      scrollVX *= SCROLL_FRICTION; scrollVY *= SCROLL_FRICTION;
      if (Math.hypot(scrollVX, scrollVY) < SCROLL_MIN_V) { inertiaRAF = 0; return; }
      const sx = Math.round(scrollVX * TUNE.scrollMult);
      const sy = Math.round(scrollVY * TUNE.scrollMult);
      if (sx || sy) NET.scroll(sx, sy);
      inertiaRAF = requestAnimationFrame(step);
    }
    inertiaRAF = requestAnimationFrame(step);
  }

  // ---- pointer handlers ----------------------------------------------------
  pad.addEventListener("pointerdown", function (e) {
    cancelInertia();
    const now = performance.now();
    pts.set(e.pointerId, { x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY, t0: now });
    pad.setPointerCapture(e.pointerId);
    pad.classList.add("active");
    const count = pts.size;

    if (count === 1) {
      moved = false;
      firstDownT = now;
      if (mode === "locked") {
        pendingLockTouch = true;          // becomes continue-drag on move, drop on tap
      } else if (now - lastTap.t <= LOCK_WINDOW_MS &&
                 Math.hypot(e.clientX - lastTap.x, e.clientY - lastTap.y) <= HALF_NEAR) {
        // "tap and a half": arm a drag-lock, but only commit if it holds or moves
        // (a quick second tap stays a double-click instead).
        halfCandidate = true;
        halfTimer = setTimeout(function () { if (halfCandidate) startDrag(); }, TAP_MS);
      }
    } else if (count === 2) {
      const first = pts.values().next().value;
      twoFingerActive = true;
      twoTapCandidate = (now - first.t0 <= TWO_WINDOW_MS);
      twoStartT = now;
      scrolled = false;
      twoStartCentroid = centroid();
      lastCentroid = twoStartCentroid;
    }
  });

  pad.addEventListener("pointermove", function (e) {
    const p = pts.get(e.pointerId);
    if (!p) return;
    const count = pts.size;

    if (count >= 2) {
      p.x = e.clientX; p.y = e.clientY;
      const c = centroid();
      const cdx = c.x - lastCentroid.x, cdy = c.y - lastCentroid.y;
      lastCentroid = c;
      if (!scrolled && twoStartCentroid &&
          Math.hypot(c.x - twoStartCentroid.x, c.y - twoStartCentroid.y) > TAP_SLOP) {
        scrolled = true;
      }
      mode = "scroll";
      scrollVX = scrollVX * 0.4 + cdx * 0.6;   // smoothed release velocity
      scrollVY = scrollVY * 0.4 + cdy * 0.6;
      const sx = Math.round(cdx * TUNE.scrollMult);
      const sy = Math.round(cdy * TUNE.scrollMult);
      if (sx || sy) NET.scroll(sx, sy);
      return;
    }

    // single finger
    if (twoFingerActive) { p.x = e.clientX; p.y = e.clientY; return; } // stray finger after a 2-finger gesture
    const dx = e.clientX - p.x, dy = e.clientY - p.y;
    p.x = e.clientX; p.y = e.clientY;
    if (!moved && Math.hypot(e.clientX - p.x0, e.clientY - p.y0) > TAP_SLOP) moved = true;
    if (halfCandidate && moved) startDrag();
    if (mode === "locked" && pendingLockTouch && moved) { mode = "drag"; pendingLockTouch = false; }
    accelerate(dx, dy);
  });

  function onUp(e) {
    const p = pts.get(e.pointerId);
    if (!p) return;
    const now = performance.now();
    const wasCount = pts.size;
    pts.delete(e.pointerId);
    try { pad.releasePointerCapture(e.pointerId); } catch (_) {}

    // two-finger tap -> right click (fire once, on the first of the two lifts)
    if (twoTapCandidate && !scrolled && wasCount === 2 && (now - twoStartT) <= TAP_MS) {
      rightClick();
      twoTapCandidate = false;
    }

    if (wasCount === 1 && !twoFingerActive) {
      const dur = now - firstDownT;
      clearTimeout(halfTimer);
      if (mode === "locked" && pendingLockTouch) {
        if (!moved && dur <= TAP_MS) dropLock();   // tap during lock -> drop
        pendingLockTouch = false;
      } else if (mode === "drag") {
        if (moved) engageLock();                   // dragged then lifted -> lock
        else { NET.button(BTN.LEFT, 0); mode = "idle"; pad.classList.remove("dragging"); }
      } else if (halfCandidate) {
        halfCandidate = false;                      // quick 2nd tap -> double click
        leftClick();
        lastTap = { t: now, x: e.clientX, y: e.clientY };
      } else if (!moved && dur <= TAP_MS) {
        leftClick();
        lastTap = { t: now, x: e.clientX, y: e.clientY };
      }
    }

    if (pts.size === 0) {
      if (scrolled && Math.hypot(scrollVX, scrollVY) >= SCROLL_MIN_V * 4) startInertia();
      else { scrollVX = 0; scrollVY = 0; }
      twoFingerActive = false;
      twoTapCandidate = false;
      scrolled = false;
      twoStartCentroid = null;
      if (mode === "scroll") mode = "idle";
      pad.classList.remove("active");
    }
  }
  pad.addEventListener("pointerup", onUp);
  pad.addEventListener("pointercancel", onUp);

  // ---- safety: release everything when the page is backgrounded ------------
  function panic() {
    cancelInertia();
    clearTimeout(halfTimer);
    clearTimeout(lockSafetyTimer);
    NET.releaseButtons();
    pts.clear();
    mode = "idle";
    moved = twoFingerActive = twoTapCandidate = scrolled = false;
    halfCandidate = pendingLockTouch = false;
    scrollVX = scrollVY = 0;
    pad.classList.remove("active", "dragging", "locked");
  }
  document.addEventListener("visibilitychange", function () { if (document.hidden) panic(); });
  window.addEventListener("pagehide", panic);
  window.addEventListener("blur", panic);

  // Belt-and-suspenders: never let the page itself scroll/zoom.
  document.addEventListener("touchmove", (e) => e.preventDefault(), { passive: false });
  document.addEventListener("gesturestart", (e) => e.preventDefault());

  // ------------------------------------------------------------ dev panel --
  const dev = document.getElementById("dev");
  const fields = ["k", "cap", "deadzone", "scrollMult"];
  function syncPanel() {
    fields.forEach(function (f) {
      document.getElementById(f).value = TUNE[f];
      document.getElementById(f + "Out").textContent = TUNE[f];
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
  document.getElementById("closeDev").addEventListener("click", () => dev.classList.add("hidden"));
  document.getElementById("copyCfg").addEventListener("click", function () {
    const cfg = { k: TUNE.k, cap: TUNE.cap, deadzone: TUNE.deadzone, scrollMult: TUNE.scrollMult };
    const ta = document.createElement("textarea");     // no async clipboard on http://
    ta.value = JSON.stringify(cfg, null, 4);
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); } catch (_) {}
    ta.remove();
    const btn = document.getElementById("copyCfg");
    const old = btn.textContent; btn.textContent = "copied ✓";
    setTimeout(() => (btn.textContent = old), 1200);
  });

  if (new URLSearchParams(location.search).get("dev") === "1") openDev();
  // triple-tap the top-left 60x60 corner
  let taps = [];
  document.addEventListener("pointerdown", function (e) {
    if (e.clientX > 60 || e.clientY > 60) { taps = []; return; }
    const now = Date.now();
    taps = taps.filter((t) => now - t < 600);
    taps.push(now);
    if (taps.length >= 3) { taps = []; openDev(); }
  }, true);
})();
