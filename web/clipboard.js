/* Clipboard panel — both directions.
 *
 * Mac -> phone: the server pushes the Mac's clipboard (OP_CLIPBOARD_SET), which
 * app.js re-broadcasts as a "mac-clipboard" event; we show it and offer Copy.
 * Phone -> Mac: no async Clipboard API on http://*.local, so the user pastes
 * into a field and taps Send (execCommand copy handles the Copy button, which
 * works synchronously on a user gesture without a secure context).
 */

(function () {
  "use strict";

  const NET = window.NET;
  const clip = document.getElementById("clip");
  const toggle = document.getElementById("clipToggle");
  const fromMac = document.getElementById("clipFromMac");
  const toMac = document.getElementById("clipToMac");

  function isOpen() { return !clip.classList.contains("hidden"); }
  function open() {
    window.dispatchEvent(new CustomEvent("panel-open", { detail: "clip" }));
    clip.classList.remove("hidden");
    toggle.classList.add("on");
  }
  function close() { clip.classList.add("hidden"); toggle.classList.remove("on"); }
  toggle.addEventListener("click", () => (isOpen() ? close() : open()));
  document.getElementById("clipDone").addEventListener("click", close);
  window.addEventListener("panel-open", (e) => { if (e.detail !== "clip" && isOpen()) close(); });

  // Mac -> phone: keep the field current even when the panel is closed.
  window.addEventListener("mac-clipboard", (e) => { fromMac.value = e.detail || ""; });

  // Copy the Mac's clipboard onto the phone (sync API, works on http).
  document.getElementById("clipCopy").addEventListener("click", function () {
    fromMac.select();
    fromMac.setSelectionRange(0, fromMac.value.length);
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (_) {}
    fromMac.blur();
    const btn = document.getElementById("clipCopy");
    const old = btn.textContent;
    btn.textContent = ok ? "copied ✓" : "select + copy";
    setTimeout(() => (btn.textContent = old), 1400);
  });

  // Phone -> Mac.
  document.getElementById("clipSend").addEventListener("click", function () {
    const text = toMac.value;
    if (!text) return;
    NET.clipboard(text);
    const btn = document.getElementById("clipSend");
    const old = btn.textContent;
    btn.textContent = "sent ✓";
    setTimeout(() => (btn.textContent = old), 1400);
  });
})();
