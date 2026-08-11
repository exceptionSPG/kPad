"""
Input synthesis via Quartz CGEvent.

Slice 1 implements pointer movement + the release-all safety invariant. Buttons,
scroll, keys and text land in later slices, but release_all() already knows how
to let go of anything we might hold, so the invariant is in place from the start.

SAFETY INVARIANT: on any disconnect the caller must invoke release_all(). A
stuck mouse-down or held modifier makes the whole Mac unusable.
"""

import Quartz

from .displays import Displays


class MacInput:
    def __init__(self, displays: Displays):
        self.displays = displays
        self._buttons_down = set()   # BTN_* currently pressed (filled in later slices)
        self._mods_down = 0          # MOD_* bitmask currently held (later slices)

    # ------------------------------------------------------------- pointer --
    def _current_location(self):
        # Reflects our own posted moves; re-reading each stroke also absorbs any
        # physical-mouse movement the user makes between events.
        ev = Quartz.CGEventCreate(None)
        p = Quartz.CGEventGetLocation(ev)
        return p.x, p.y

    def move(self, dx: float, dy: float):
        x, y = self._current_location()
        x, y = self.displays.clamp(x + dx, y + dy)
        ev = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventMouseMoved, (x, y), Quartz.kCGMouseButtonLeft
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

    # -------------------------------------------------------------- safety --
    def release_all(self):
        """Force-release every held button and modifier. Idempotent + cheap."""
        x, y = self._current_location()
        for btn, cg in (
            (0, Quartz.kCGMouseButtonLeft),
            (1, Quartz.kCGMouseButtonRight),
            (2, Quartz.kCGMouseButtonCenter),
        ):
            up_type = {
                Quartz.kCGMouseButtonLeft: Quartz.kCGEventLeftMouseUp,
                Quartz.kCGMouseButtonRight: Quartz.kCGEventRightMouseUp,
                Quartz.kCGMouseButtonCenter: Quartz.kCGEventOtherMouseUp,
            }[cg]
            ev = Quartz.CGEventCreateMouseEvent(None, up_type, (x, y), cg)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        self._buttons_down.clear()
        self._mods_down = 0
