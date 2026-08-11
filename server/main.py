"""
Entry point (Slice 1): AX check -> print LAN URLs -> serve.

The menu-bar UI (rumps) and pairing arrive in later slices. For now the asyncio
server owns the main thread; when rumps is added, the server moves to a
background thread and rumps takes the main thread.
"""

import socket
import sys

from ApplicationServices import AXIsProcessTrusted

from . import config
from .displays import Displays
from .input_mac import MacInput
from .wsserver import Server

AX_PANE = "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"


def _check_accessibility():
    """Warn loudly if we lack Accessibility permission — without it, every
    CGEventPost silently no-ops and the cursor never moves."""
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

    _check_accessibility()

    displays = Displays()
    inp = MacInput(displays)
    server = Server(inp, config.HOST, config.PORT)

    host = socket.gethostname()
    if not host.endswith(".local"):
        host += ".local"
    ip = _lan_ip()
    print("LAN Trackpad — open on your phone (same Wi-Fi):")
    print(f"    http://{host}:{config.PORT}/")
    print(f"    http://{ip}:{config.PORT}/   (if .local doesn't resolve)")
    print("Ctrl-C to stop.\n")

    server.run()


if __name__ == "__main__":
    main()
