"""
Menu-bar UI (rumps). Runs on the main thread; the aiohttp server runs in a
background thread (see main.py).

Menu: the connect URL + pairing code (display-only), Show QR (scan to
connect+pair in one step), a live Accessibility status/grant item, connected
phone count, Unpair all, Quit. A 2s timer refreshes the live items.
"""

import os
import subprocess
import tempfile

import rumps
import segno
from ApplicationServices import (
    AXIsProcessTrusted,
    AXIsProcessTrustedWithOptions,
    kAXTrustedCheckOptionPrompt,
)

from .pairing import STORE_FILE

AX_PANE = "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"


class MenuBarApp(rumps.App):
    def __init__(self, pairing, stats, urls, port):
        super().__init__("LAN Trackpad", title="🖱", quit_button=None)
        self.pairing = pairing
        self.stats = stats
        self.urls = urls          # {"host": ..., "ip": ...}
        self.port = port
        self._qr_path = None

        self.item_ax = rumps.MenuItem("Accessibility: …", callback=self._grant_ax)
        self.item_status = rumps.MenuItem("Status: waiting for a phone")
        self.menu = [
            rumps.MenuItem(self.urls["host"]),          # display-only (no callback)
            rumps.MenuItem(f"Pairing code:  {pairing.code}"),
            None,
            rumps.MenuItem("Show QR code", callback=self._show_qr),
            None,
            self.item_ax,
            self.item_status,
            None,
            rumps.MenuItem("Unpair all phones", callback=self._unpair_all),
            rumps.MenuItem("Quit LAN Trackpad", callback=self._quit),
        ]

        self._timer = rumps.Timer(self._refresh, 2)
        self._timer.start()
        self._refresh(None)

    # ----------------------------------------------------------- live items --
    def _refresh(self, _):
        trusted = AXIsProcessTrusted()
        self.item_ax.title = "Accessibility: granted ✓" if trusted else "Grant Accessibility…"
        self.item_ax.set_callback(None if trusted else self._grant_ax)
        n = self.stats.get("clients", 0)
        self.item_status.title = (
            f"Status: {n} phone{'s' if n != 1 else ''} connected" if n
            else "Status: waiting for a phone"
        )

    # --------------------------------------------------------------- actions --
    def _grant_ax(self, _):
        AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})
        subprocess.Popen(["open", AX_PANE])

    def _show_qr(self, _):
        # Encode the IP URL (most reliable to reach) + the pairing code, so the
        # phone scans straight onto the paired trackpad.
        url = f"{self.urls['ip']}?code={self.pairing.code}"
        if not self._qr_path:
            self._qr_path = os.path.join(tempfile.gettempdir(), "lan-trackpad-qr.png")
        segno.make(url, error="m").save(self._qr_path, scale=10, border=3)
        subprocess.Popen(["open", self._qr_path])

    def _unpair_all(self, _):
        self.pairing.tokens.clear()
        try:
            STORE_FILE.unlink()
        except FileNotFoundError:
            pass
        try:
            rumps.notification("LAN Trackpad", "Unpaired",
                               "Every phone must enter the code again.")
        except Exception:
            pass

    def _quit(self, _):
        rumps.quit_application()


def run_menubar(pairing, stats, urls, port):
    MenuBarApp(pairing, stats, urls, port).run()
