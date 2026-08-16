"""
Input synthesis via Quartz CGEvent.

Slice 2: pointer move (drag-aware), mouse buttons with click-state so the OS
recognises double/triple clicks, and pixel-unit scroll. Keys/text arrive later.

SAFETY INVARIANT: on any disconnect the caller must invoke release_all(). A
stuck mouse-down or held modifier makes the whole Mac unusable. Every held
button is tracked so release_all() can let go of exactly what's down.
"""

import time

import Quartz
from AppKit import NSEvent, NSEventTypeSystemDefined

from . import protocol as P
from .displays import Displays

# MEDIA_* -> NX_KEYTYPE_* (the hardware media-key codes macOS listens for).
_NX = {
    P.MEDIA_VOL_UP: 0,
    P.MEDIA_VOL_DOWN: 1,
    P.MEDIA_BRIGHT_UP: 2,
    P.MEDIA_BRIGHT_DOWN: 3,
    P.MEDIA_MUTE: 7,
    P.MEDIA_PLAY_PAUSE: 16,
    P.MEDIA_NEXT: 17,
    P.MEDIA_PREV: 18,
}

# Two synthesized clicks within this window + distance become a double-click.
_DOUBLE_CLICK_SEC = 0.5
_DOUBLE_CLICK_DIST = 6.0

_BTN_CG = {
    P.BTN_LEFT: Quartz.kCGMouseButtonLeft,
    P.BTN_RIGHT: Quartz.kCGMouseButtonRight,
    P.BTN_MIDDLE: Quartz.kCGMouseButtonCenter,
}
_DOWN_TYPE = {
    P.BTN_LEFT: Quartz.kCGEventLeftMouseDown,
    P.BTN_RIGHT: Quartz.kCGEventRightMouseDown,
    P.BTN_MIDDLE: Quartz.kCGEventOtherMouseDown,
}
_UP_TYPE = {
    P.BTN_LEFT: Quartz.kCGEventLeftMouseUp,
    P.BTN_RIGHT: Quartz.kCGEventRightMouseUp,
    P.BTN_MIDDLE: Quartz.kCGEventOtherMouseUp,
}
_DRAG_TYPE = {
    P.BTN_LEFT: Quartz.kCGEventLeftMouseDragged,
    P.BTN_RIGHT: Quartz.kCGEventRightMouseDragged,
    P.BTN_MIDDLE: Quartz.kCGEventOtherMouseDragged,
}

# MOD_* bitmask -> CGEvent flag mask.
_MOD_FLAG = {
    P.MOD_SHIFT: Quartz.kCGEventFlagMaskShift,
    P.MOD_CONTROL: Quartz.kCGEventFlagMaskControl,
    P.MOD_OPTION: Quartz.kCGEventFlagMaskAlternate,
    P.MOD_COMMAND: Quartz.kCGEventFlagMaskCommand,
    P.MOD_FN: Quartz.kCGEventFlagMaskSecondaryFn,
}

# MOD_* bitmask -> kVK_ modifier keycode, so we can press the modifier as a real
# key (some system hotkeys, e.g. "move a space", ignore flags-only events).
_MOD_KV = {
    P.MOD_SHIFT: 0x38,     # kVK_Shift
    P.MOD_CONTROL: 0x3B,   # kVK_Control
    P.MOD_OPTION: 0x3A,    # kVK_Option
    P.MOD_COMMAND: 0x37,   # kVK_Command
    P.MOD_FN: 0x3F,        # kVK_Function
}


def _cg_flags(modifiers: int) -> int:
    flags = 0
    for bit, flag in _MOD_FLAG.items():
        if modifiers & bit:
            flags |= flag
    return flags


class MacInput:
    def __init__(self, displays: Displays):
        self.displays = displays
        self._buttons_down = set()   # BTN_* currently pressed
        self._mods_down = 0          # MOD_* bitmask (keyboard slice)
        self._last_click_t = 0.0
        self._last_click_pos = (0.0, 0.0)
        self._click_state = 0
        # HID-system-state source: synthetic modifier key presses combine with the
        # real modifier state, so a synthetic Control actually "holds" for system
        # hotkeys like Ctrl+Arrow "move a space" (a nil source leaves the arrow a
        # plain arrow — Finder just walks the desktop icons).
        self._src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)

    def _current_location(self):
        p = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
        return p.x, p.y

    def _post(self, ev):
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

    # ------------------------------------------------------------- pointer --
    def move(self, dx: float, dy: float):
        x, y = self._current_location()
        x, y = self.displays.clamp(x + dx, y + dy)
        # If a button is held, emit the matching *Dragged* event so apps see a
        # real drag (text selection, window move), not a plain hover.
        held = next(iter(self._buttons_down), None)
        if held is None:
            ev = Quartz.CGEventCreateMouseEvent(
                None, Quartz.kCGEventMouseMoved, (x, y), Quartz.kCGMouseButtonLeft
            )
        else:
            ev = Quartz.CGEventCreateMouseEvent(
                None, _DRAG_TYPE[held], (x, y), _BTN_CG[held]
            )
        self._post(ev)

    # -------------------------------------------------------------- button --
    def button(self, button: int, down: int):
        if button not in _BTN_CG:
            return
        x, y = self._current_location()
        cg = _BTN_CG[button]
        if down:
            now = time.monotonic()
            lx, ly = self._last_click_pos
            near = abs(x - lx) <= _DOUBLE_CLICK_DIST and abs(y - ly) <= _DOUBLE_CLICK_DIST
            if now - self._last_click_t <= _DOUBLE_CLICK_SEC and near:
                self._click_state += 1
            else:
                self._click_state = 1
            self._last_click_t = now
            self._last_click_pos = (x, y)
            ev = Quartz.CGEventCreateMouseEvent(None, _DOWN_TYPE[button], (x, y), cg)
            Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, self._click_state)
            self._post(ev)
            self._buttons_down.add(button)
        else:
            ev = Quartz.CGEventCreateMouseEvent(None, _UP_TYPE[button], (x, y), cg)
            Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, self._click_state or 1)
            self._post(ev)
            self._buttons_down.discard(button)

    # ----------------------------------------------------------------- key --
    def _post_key(self, keycode, is_down, flags):
        ev = Quartz.CGEventCreateKeyboardEvent(self._src, keycode, is_down)
        Quartz.CGEventSetFlags(ev, flags)
        self._post(ev)

    def key(self, keycode: int, modifiers: int):
        """Tap `keycode` (kVK_*) with `modifiers` (MOD_* bitmask).

        The modifiers are pressed as REAL keys — flags-only events leave macOS's
        modifier state inconsistent (Control could stay "stuck", turning later
        left-clicks into right-clicks) and system hotkeys like Ctrl+Arrow
        "move a space" ignore them. We build the modifier flags up on the way in
        and tear them fully down on the way out, so nothing is left held."""
        # Press modifiers, accumulating the flag mask as each goes down.
        active = 0
        for bit, kv in _MOD_KV.items():
            if modifiers & bit:
                active |= _MOD_FLAG[bit]
                self._post_key(kv, True, active)
        # The key itself, with all modifiers held.
        self._post_key(keycode, True, active)
        self._post_key(keycode, False, active)
        # Release modifiers in reverse, clearing each flag as it lifts (ends at 0).
        for bit, kv in reversed(list(_MOD_KV.items())):
            if modifiers & bit:
                active &= ~_MOD_FLAG[bit]
                self._post_key(kv, False, active)

    # --------------------------------------------------------------- media --
    def media(self, media_id: int):
        """Tap a media/system key (volume, brightness, play/pause, track). These
        are NSSystemDefined events, not kVK_ keys — the OS shows its HUD and acts."""
        nx = _NX.get(media_id)
        if nx is None:
            return
        for down in (True, False):
            data1 = (nx << 16) | ((0xA if down else 0xB) << 8)
            ev = NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
                NSEventTypeSystemDefined, (0, 0), 0xA00 if down else 0xB00, 0, 0, None, 8, data1, -1
            )
            self._post(ev.CGEvent())

    # ---------------------------------------------------------------- text --
    def text(self, s: str):
        """Type a unicode string (typing + native dictation). Uses
        CGEventKeyboardSetUnicodeString so it reproduces any character exactly,
        independent of keyboard layout — the right tool for dictated phrases."""
        if not s:
            return
        for is_down in (True, False):
            ev = Quartz.CGEventCreateKeyboardEvent(None, 0, is_down)
            Quartz.CGEventKeyboardSetUnicodeString(ev, len(s), s)
            self._post(ev)

    # -------------------------------------------------------------- scroll --
    def scroll(self, sx: int, sy: int):
        # Pixel unit for smooth scrolling. wheel1 = vertical, wheel2 = horizontal.
        ev = Quartz.CGEventCreateScrollWheelEvent(
            None, Quartz.kCGScrollEventUnitPixel, 2, int(sy), int(sx)
        )
        self._post(ev)

    # -------------------------------------------------------------- safety --
    def release_all(self):
        """Force-release every held button and modifier. Idempotent + cheap."""
        x, y = self._current_location()
        for button in (P.BTN_LEFT, P.BTN_RIGHT, P.BTN_MIDDLE):
            ev = Quartz.CGEventCreateMouseEvent(None, _UP_TYPE[button], (x, y), _BTN_CG[button])
            self._post(ev)
        # Defensively lift every modifier key too, so a stuck Control/Command
        # (which would turn left-clicks into right-clicks, etc.) can't survive.
        for kv in _MOD_KV.values():
            self._post_key(kv, False, 0)
        self._buttons_down.clear()
        self._mods_down = 0
        self._click_state = 0
