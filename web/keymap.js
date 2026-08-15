/* THE one place for JS-name -> macOS virtual keycode (kVK_*) mapping.
 * Keep every key mapping here so the two halves can never drift.
 * Values are kVK_* from <HIToolbox/Events.h>. */

// Named / special keys (used by on-screen buttons and the three-finger gesture).
window.KVK = Object.freeze({
  Return: 0x24, Tab: 0x30, Space: 0x31, Backspace: 0x33, Escape: 0x35,
  ArrowLeft: 0x7B, ArrowRight: 0x7C, ArrowDown: 0x7D, ArrowUp: 0x7E,
  Home: 0x73, End: 0x77, PageUp: 0x74, PageDown: 0x79, ForwardDelete: 0x75,
});

// Printable char -> kVK, for modifier combos (e.g. Cmd+C). Letters are matched
// case-insensitively; Shift is carried separately in the modifier bitmask.
window.CHAR_KVK = Object.freeze({
  a: 0x00, s: 0x01, d: 0x02, f: 0x03, h: 0x04, g: 0x05, z: 0x06, x: 0x07,
  c: 0x08, v: 0x09, b: 0x0B, q: 0x0C, w: 0x0D, e: 0x0E, r: 0x0F, y: 0x10,
  t: 0x11, o: 0x1F, u: 0x20, i: 0x22, p: 0x23, l: 0x25, j: 0x26, k: 0x28,
  n: 0x2D, m: 0x2E,
  "1": 0x12, "2": 0x13, "3": 0x14, "4": 0x15, "5": 0x17, "6": 0x16,
  "7": 0x1A, "8": 0x1C, "9": 0x19, "0": 0x1D,
  "-": 0x1B, "=": 0x18, "[": 0x21, "]": 0x1E, "\\": 0x2A, ";": 0x29,
  "'": 0x27, ",": 0x2B, ".": 0x2F, "/": 0x2C, "`": 0x32, " ": 0x31,
});

// Returns kVK for a single printable char, or null if unmapped.
window.charToKvk = function (ch) {
  if (!ch || ch.length !== 1) return null;
  const k = window.CHAR_KVK[ch.toLowerCase()];
  return k === undefined ? null : k;
};
