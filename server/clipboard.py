"""
Clipboard bridge over NSPasteboard.

The server polls changeCount (~500ms) and, when the Mac's clipboard changes to
new text, broadcasts it to paired phones. Phones can also push text back. To
avoid an echo loop, we remember the last value we broadcast or set and skip it.
"""

from AppKit import NSPasteboard, NSPasteboardTypeString


class Clipboard:
    def __init__(self):
        self.pb = NSPasteboard.generalPasteboard()
        self._last_count = self.pb.changeCount()
        self._last_text = self.get_text() or ""

    def get_text(self):
        return self.pb.stringForType_(NSPasteboardTypeString)

    def set_text(self, text: str):
        self.pb.clearContents()
        self.pb.setString_forType_(text, NSPasteboardTypeString)
        # Remember it so our own poll doesn't echo it back out.
        self._last_count = self.pb.changeCount()
        self._last_text = text

    def poll(self):
        """Return new clipboard text if it changed since last poll, else None."""
        count = self.pb.changeCount()
        if count == self._last_count:
            return None
        self._last_count = count
        text = self.get_text()
        if not text or text == self._last_text:
            return None
        self._last_text = text
        return text
