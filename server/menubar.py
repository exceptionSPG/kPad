"""
Menu-bar UI (rumps). Runs on the main thread; the aiohttp server runs in a
background thread (see main.py).

Menu: the connect URL + pairing code (display-only), Show QR (scan to
connect+pair in one step), a live Accessibility status/grant item, connected
phone count, Unpair all, Quit. A 2s timer refreshes the live items.
"""

import os
import socket
import subprocess
import tempfile

import rumps
import segno

from . import config
from ApplicationServices import (
    AXIsProcessTrusted,
    AXIsProcessTrustedWithOptions,
    kAXTrustedCheckOptionPrompt,
)

from .pairing import STORE_FILE

AX_PANE = "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"


def _current_ip():
    """The Mac's IP on whatever network it's on *right now* (recomputed, not the
    value captured at launch) — so the QR stays correct after switching Wi-Fi or
    joining a phone hotspot. No packets are actually sent."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class MenuBarApp(rumps.App):
    def __init__(self, server, urls):
        super().__init__("LAN Trackpad", title="🖱", quit_button=None)
        self.server = server
        self.pairing = server.pairing
        self.stats = server.stats
        self.urls = urls          # {"host": ..., "ip": ...}
        self._qr_path = None

        self.item_ax = rumps.MenuItem("Accessibility: …", callback=self._grant_ax)
        self.item_status = rumps.MenuItem("Status: waiting for a phone")
        self.menu = [
            rumps.MenuItem(self.urls["host"]),          # display-only (no callback)
            rumps.MenuItem(f"Pairing code:  {self.pairing.code}"),
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
        # Encode the CURRENT IP (+ pairing code), recomputed now so the QR is
        # valid on whatever network the Mac is on this moment (Wi-Fi change,
        # phone hotspot, …), not the address captured at launch.
        url = f"http://{_current_ip()}:{config.PORT}/?code={self.pairing.code}"
        if not self._qr_path:
            self._qr_path = os.path.join(tempfile.gettempdir(), "lan-trackpad-qr.png")
        segno.make(url, error="m").save(self._qr_path, scale=10, border=3)
        subprocess.Popen(["open", self._qr_path])

    def _unpair_all(self, _):
        # Clear tokens AND drop live connections, so a currently-paired phone is
        # kicked and forced to re-enter the code (not just future connections).
        self.pairing.tokens.clear()
        try:
            STORE_FILE.unlink()
        except FileNotFoundError:
            pass
        self.server.disconnect_all()
        try:
            rumps.notification("LAN Trackpad", "Unpaired",
                               "Every phone must enter the code again.")
        except Exception:
            pass

    def _quit(self, _):
        # Close connections cleanly so phones see an immediate disconnect.
        try:
            fut = self.server.disconnect_all()
            if fut is not None:
                fut.result(timeout=1)
        except Exception:
            pass
        rumps.quit_application()


def run_menubar(server, urls):
    MenuBarApp(server, urls).run()
