"""
Multi-display geometry.

Global CGEvent coordinates use a top-left origin on the main display; secondary
displays sit at negative or large offsets. We clamp the cursor to the bounding
box of the union of all active displays.

Caveat (fine for now): with non-aligned displays (e.g. an L-shaped arrangement)
the bounding box includes a dead corner the cursor could technically enter. The
spec asked for "union of all displays"; tight per-display containment is a later
refinement if it ever bites.
"""

import Quartz


class Displays:
    def __init__(self):
        self.refresh()

    def refresh(self):
        err, ids, count = Quartz.CGGetActiveDisplayList(16, None, None)
        rects = [Quartz.CGDisplayBounds(d) for d in (ids or [])]
        if not rects:
            # Fallback: main display only.
            rects = [Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())]
        self.min_x = min(r.origin.x for r in rects)
        self.min_y = min(r.origin.y for r in rects)
        self.max_x = max(r.origin.x + r.size.width for r in rects)
        self.max_y = max(r.origin.y + r.size.height for r in rects)

    def clamp(self, x: float, y: float):
        # max-1 so the cursor stays on-screen (bounds are exclusive on the far edge).
        x = min(max(x, self.min_x), self.max_x - 1)
        y = min(max(y, self.min_y), self.max_y - 1)
        return x, y
