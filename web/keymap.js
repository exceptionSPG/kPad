/* THE one place for JS-name -> macOS virtual keycode (kVK_*) mapping.
 * Keep every key mapping here so the two halves can never drift. The keyboard
 * slice expands this with letters/digits/etc.; for now it carries what the
 * three-finger Spaces gesture needs. Values are kVK_* from <HIToolbox/Events.h>. */

window.KVK = Object.freeze({
  ArrowLeft: 0x7B,   // kVK_LeftArrow  (123)
  ArrowRight: 0x7C,  // kVK_RightArrow (124)
  ArrowDown: 0x7D,   // kVK_DownArrow  (125)
  ArrowUp: 0x7E,     // kVK_UpArrow    (126)
});
