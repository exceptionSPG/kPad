/* Presenter panel — drive any slideshow with universal keys (no app-specific
 * scripting, so it works in Keynote, PowerPoint, Preview/PDF, Google Slides):
 *   Prev = Left arrow, Next = Right arrow, Black = B, End = Esc. */

(function () {
  "use strict";

  const NET = window.NET;
  const KVK = window.KVK;
  const present = document.getElementById("present");
  const toggle = document.getElementById("presentToggle");

  const notesEl = document.getElementById("notes");

  function isOpen() { return !present.classList.contains("hidden"); }
  function open() {
    window.dispatchEvent(new CustomEvent("panel-open", { detail: "present" }));
    present.classList.remove("hidden");
    toggle.classList.add("on");
    NET.notesSub(true);          // ask the Mac to stream Keynote notes
  }
  function close() {
    present.classList.add("hidden");
    toggle.classList.remove("on");
    NET.notesSub(false);         // stop the notes poll on the Mac
  }
  toggle.addEventListener("click", () => (isOpen() ? close() : open()));
  document.getElementById("presentDone").addEventListener("click", close);
  window.addEventListener("panel-open", (e) => { if (e.detail !== "present" && isOpen()) close(); });

  // Incoming speaker notes for the current slide.
  window.addEventListener("slide-notes", function (e) {
    const t = (e.detail || "").trim();
    notesEl.textContent = t || "(no notes for this slide)";
    notesEl.scrollTop = 0;
  });

  const KEYS = {
    prev: KVK.ArrowLeft,
    next: KVK.ArrowRight,
    black: window.charToKvk("b"),   // toggles a black screen in Keynote/PowerPoint
    end: KVK.Escape,
  };
  present.querySelectorAll("button[data-pkey]").forEach(function (btn) {
    btn.addEventListener("click", () => NET.key(KEYS[btn.dataset.pkey], 0));
  });
})();
