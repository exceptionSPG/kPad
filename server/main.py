"""
Entry point (Slice 1): AX check -> print LAN URLs -> serve.

The menu-bar UI (rumps) and pairing arrive in later slices. For now the asyncio
server owns the main thread; when rumps is added, the server moves to a
background thread and rumps takes the main thread.
"""

import os
import socket
import sys

from ApplicationServices import AXIsProcessTrusted

from . import config
from .displays import Displays
from .input_mac import MacInput
from .pairing import Pairing
from .wsserver import Server

AX_PANE = "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"


def _check_accessibility():
    """Warn loudly if we lack Accessibility permission — without it, every
    CGEventPost silently no-ops and the cursor never moves.

    The menu-bar "Grant Accessibility" item does the interactive prompt on
    demand; here we only check (no dialog) so repeated launches stay quiet."""
    if AXIsProcessTrusted():
        return
    print("=" * 68)
    print("  Accessibility permission is NOT granted.")
    print("  Without it, macOS silently drops every synthesized event and the")
    print("  cursor will not move.")
    print()
    print("  Grant it to whatever runs this (your terminal app for `make run`):")
    print("  System Settings > Privacy & Security > Accessibility")
    print(f"  Open directly:  open '{AX_PANE}'")
    print("  Then quit and re-run.  (A proper in-app prompt lands in a later slice.)")
    print("=" * 68)


def _lan_ip():
    """Best-effort primary LAN IP (no packets actually sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 1))  # TEST-NET-1, unroutable
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    if sys.platform != "darwin":
        sys.exit("LAN Trackpad server only runs on macOS.")

    # Line-buffer stdout so startup info (URLs, pairing code) shows immediately —
    # important when running as a long-lived process or logging to a file (.app).
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

    _check_accessibility()

    displays = Displays()
    inp = MacInput(displays)
    pairing = Pairing()
    stats = {"clients": 0}
    server = Server(inp, pairing, config.HOST, config.PORT, stats)

    host = socket.gethostname()
    if not host.endswith(".local"):
        host += ".local"
    ip = _lan_ip()
    host_url = f"http://{host}:{config.PORT}/"
    ip_url = f"http://{ip}:{config.PORT}/"
    print("LAN Trackpad — open on your phone (same Wi-Fi):")
    print(f"    {host_url}")
    print(f"    {ip_url}   (if .local doesn't resolve)")
    print()
    print(f"    Pairing code:  {pairing.code}   (or scan the QR from the menu bar)")
    print("Menu-bar icon 🖱 has the QR, status, and controls.  Ctrl-C to stop.\n")

    # rumps must own the main thread, so the server runs in a background thread.
    # LANTRACKPAD_NO_MENUBAR runs it headless on the main thread (dev/testing).
    if os.environ.get("LANTRACKPAD_NO_MENUBAR"):
        server.run()
    else:
        server.start_in_thread()
        from .menubar import run_menubar
        run_menubar(pairing, stats, {"host": host_url, "ip": ip_url}, config.PORT)


if __name__ == "__main__":
    main()
