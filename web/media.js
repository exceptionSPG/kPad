/* Media panel — play/pause, track, volume, brightness. Each button sends
 * OP_MEDIA with the MEDIA_* id; the Mac posts the matching system key. */

(function () {
  "use strict";

  const NET = window.NET;
  const media = document.getElementById("media");
  const toggle = document.getElementById("mediaToggle");

  function isOpen() { return !media.classList.contains("hidden"); }
  function open() {
    window.dispatchEvent(new CustomEvent("panel-open", { detail: "media" }));
    media.classList.remove("hidden");
    toggle.classList.add("on");
  }
  function close() { media.classList.add("hidden"); toggle.classList.remove("on"); }
  toggle.addEventListener("click", () => (isOpen() ? close() : open()));
  document.getElementById("mediaDone").addEventListener("click", close);
  window.addEventListener("panel-open", (e) => { if (e.detail !== "media" && isOpen()) close(); });

  media.querySelectorAll("button[data-media]").forEach(function (btn) {
    btn.addEventListener("click", () => NET.media(PROTO[btn.dataset.media]));
  });

  // Desktop / Space switch = the macOS "Move a space" shortcut (Ctrl+Arrow).
  media.querySelectorAll("button[data-space]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const kc = btn.dataset.space === "next" ? window.KVK.ArrowRight : window.KVK.ArrowLeft;
      NET.key(kc, PROTO.MOD_CONTROL);
    });
  });
})();
