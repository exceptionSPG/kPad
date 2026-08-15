/* Keyboard panel: text + native dictation + special keys + sticky modifiers.
 *
 * Text/voice capture is DIFF-BASED and single-path: the field keeps what you
 * type (and dictate), and on every `input` we diff old vs new value and forward
 * only the delta. This is robust across platforms — iOS Safari, Android/Samsung
 * IMEs, and predictive/composition input all funnel through one code path — so a
 * keystroke can't be double-sent (the old beforeinput+input dual path doubled
 * characters on Android), and native Backspace works because the field has real
 * content to delete (the diff turns that deletion into a Backspace key).
 *
 * What you type lands on the Mac wherever its cursor is; the field is just a
 * capture buffer. Modifiers are sticky: tap ⌘, then a key => ⌘C, then clear.
 * On-screen buttons preventDefault on pointerdown so they never steal focus and
 * dismiss the native keyboard.
 */

(function () {
  "use strict";

  const NET = window.NET;
  const KVK = window.KVK;
  const MODBIT = {
    CONTROL: PROTO.MOD_CONTROL,
    OPTION: PROTO.MOD_OPTION,
    SHIFT: PROTO.MOD_SHIFT,
    COMMAND: PROTO.MOD_COMMAND,
  };

  const kbd = document.getElementById("kbd");
  const input = document.getElementById("kbdInput");
  const toggle = document.getElementById("kbdToggle");

  let activeMods = 0;
  let prev = "";                 // last-seen field value, for diffing
  const modButtons = {};         // bit -> button element

  // ---- open / close --------------------------------------------------------
  function isOpen() { return !kbd.classList.contains("hidden"); }
  function resetBuffer() { input.value = ""; prev = ""; }
  function open() {
    kbd.classList.remove("hidden");
    toggle.classList.add("on");
    resetBuffer();
    setTimeout(() => input.focus(), 20);
  }
  function close() {
    clearMods();
    input.blur();
    kbd.classList.add("hidden");
    toggle.classList.remove("on");
    resetBuffer();
  }
  toggle.addEventListener("click", () => (isOpen() ? close() : open()));
  document.getElementById("kbdDone").addEventListener("click", close);

  // ---- modifiers -----------------------------------------------------------
  function setModUI() {
    for (const bit in modButtons) modButtons[bit].classList.toggle("on", !!(activeMods & bit));
  }
  function clearMods() { activeMods = 0; setModUI(); }

  // ---- key / text out ------------------------------------------------------
  function tapKey(keycode) {
    NET.key(keycode, activeMods);
    clearMods();
    resetBuffer();               // a command key breaks the text buffer; start fresh
    if (isOpen()) input.focus();
  }

  // ---- diff-based text capture (single path) -------------------------------
  input.addEventListener("input", function () {
    const val = input.value;
    // common prefix / suffix vs the previous value
    const minLen = Math.min(val.length, prev.length);
    let cp = 0;
    while (cp < minLen && val[cp] === prev[cp]) cp++;
    let cs = 0;
    while (cs < minLen - cp && val[val.length - 1 - cs] === prev[prev.length - 1 - cs]) cs++;
    const removed = prev.slice(cp, prev.length - cs);
    const added = val.slice(cp, val.length - cs);

    if (added) {
      // single char while a modifier is held => a combo (⌘C, ⌥←, …)
      if (added.length === 1 && activeMods) {
        const kc = window.charToKvk(added);
        if (kc != null) { NET.key(kc, activeMods); clearMods(); resetBuffer(); return; }
      }
      // forward text; newlines become Return keypresses
      const parts = added.split("\n");
      for (let i = 0; i < parts.length; i++) {
        if (parts[i]) NET.text(parts[i]);
        if (i < parts.length - 1) NET.key(KVK.Return, 0);
      }
      if (activeMods) clearMods();
      if (added.includes("\n")) { resetBuffer(); return; }
    } else if (removed) {
      for (let i = 0; i < removed.length; i++) NET.key(KVK.Backspace, 0);
    }

    prev = val;
    if (val.length > 200) resetBuffer();   // keep the buffer from growing forever
  });

  // Special keys from a physical/bluetooth keyboard (soft IMEs use the buttons).
  input.addEventListener("keydown", function (e) {
    const map = { Escape: KVK.Escape, Tab: KVK.Tab, ArrowLeft: KVK.ArrowLeft,
                  ArrowRight: KVK.ArrowRight, ArrowUp: KVK.ArrowUp, ArrowDown: KVK.ArrowDown };
    if (e.key in map) { e.preventDefault(); tapKey(map[e.key]); }
  });

  // ---- on-screen buttons ---------------------------------------------------
  // preventDefault on pointerdown keeps focus on the field (native keyboard stays up).
  kbd.querySelectorAll(".kbdKeys button, .kbdMods button").forEach(function (btn) {
    btn.addEventListener("pointerdown", (e) => e.preventDefault());
  });
  kbd.querySelectorAll(".kbdKeys button").forEach(function (btn) {
    btn.addEventListener("click", () => tapKey(KVK[btn.dataset.key]));
  });
  kbd.querySelectorAll(".kbdMods button").forEach(function (btn) {
    const bit = MODBIT[btn.dataset.mod];
    modButtons[bit] = btn;
    btn.addEventListener("click", function () {
      activeMods ^= bit;
      setModUI();
      input.focus();
    });
  });

  window.addEventListener("pagehide", close);
})();
