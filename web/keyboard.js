/* Keyboard panel: text + native dictation + special keys + sticky modifiers.
 *
 * Text/voice: a real <input> drives the phone's native keyboard (and its mic
 * button = dictation). We translate its beforeinput events into wire opcodes and
 * keep the field itself empty — what you type lands on the Mac, not the phone.
 *
 * Modifiers are sticky: tap ⌘, then a key, and that one key carries ⌘ (⌘C, ⌘Tab,
 * ⌥⌫ …), after which the modifiers clear. On-screen buttons preventDefault on
 * pointerdown so tapping them never steals focus — the native keyboard stays up.
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
  const modButtons = {};     // bit -> button element

  // ---- open / close --------------------------------------------------------
  function isOpen() { return !kbd.classList.contains("hidden"); }
  function open() {
    kbd.classList.remove("hidden");
    toggle.classList.add("on");
    input.value = "";
    setTimeout(() => input.focus(), 20);
  }
  function close() {
    clearMods();
    input.blur();
    kbd.classList.add("hidden");
    toggle.classList.remove("on");
  }
  toggle.addEventListener("click", () => (isOpen() ? close() : open()));
  document.getElementById("kbdDone").addEventListener("click", close);

  // ---- modifiers -----------------------------------------------------------
  function setModUI() {
    for (const bit in modButtons) {
      modButtons[bit].classList.toggle("on", !!(activeMods & bit));
    }
  }
  function clearMods() { activeMods = 0; setModUI(); }

  // ---- sending -------------------------------------------------------------
  function tapKey(keycode) {
    NET.key(keycode, activeMods);
    clearMods();                 // modifiers apply to a single key, then reset
  }
  function sendText(str) {
    if (!str) return;
    // A single printable char while a modifier is held => a key combo (⌘C…).
    if (activeMods && str.length === 1) {
      const kc = window.charToKvk(str);
      if (kc != null) { NET.key(kc, activeMods); clearMods(); return; }
    }
    NET.text(str);
    if (activeMods) clearMods();  // don't leak modifiers onto later typing
  }

  // ---- native input translation -------------------------------------------
  input.addEventListener("beforeinput", function (e) {
    const t = e.inputType || "";
    if (t.startsWith("delete")) {
      e.preventDefault();
      tapKey(KVK.Backspace);
    } else if (t === "insertLineBreak" || t === "insertParagraph") {
      e.preventDefault();
      tapKey(KVK.Return);
    } else if (t.startsWith("insert")) {
      if (e.data != null) {         // typed text or dictation with data
        e.preventDefault();
        sendText(e.data);
      }                              // else: let the input handler flush it
    }
  });

  // Fallback for insertions that weren't cancelable (some dictation paths):
  // whatever landed in the field gets flushed and the field cleared.
  input.addEventListener("input", function () {
    if (input.value) { sendText(input.value); input.value = ""; }
  });

  // Physical/bluetooth-keyboard special keys that skip beforeinput.
  input.addEventListener("keydown", function (e) {
    const map = { Escape: KVK.Escape, Tab: KVK.Tab, ArrowLeft: KVK.ArrowLeft,
                  ArrowRight: KVK.ArrowRight, ArrowUp: KVK.ArrowUp, ArrowDown: KVK.ArrowDown };
    if (e.key in map) { e.preventDefault(); tapKey(map[e.key]); }
  });

  // ---- on-screen buttons ---------------------------------------------------
  // Keep focus on the input so the native keyboard doesn't dismiss.
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

  // Close the keyboard if we drop the connection (pairing overlay takes over).
  window.addEventListener("pagehide", close);
})();
