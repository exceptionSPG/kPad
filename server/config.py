"""
Server configuration.

Network only. Pointer *feel* (accel k, cap, deadzone, scroll multiplier) is owned
entirely by the client: each phone tunes it live in the dev panel (?dev=1 or
triple-tap the top-left corner) and persists its own curve in localStorage. The
first-run defaults live in web/app.js (DEFAULTS) — there is deliberately no
server-side copy to drift out of sync.
"""

# App version (keep in sync with kPad.spec). Shown in the About dialog.
VERSION = "0.2.10"

# Port for both HTTP and WebSocket (one URL, one QR code).
PORT = 8787

# Bind on all interfaces so the phone can reach us over the LAN.
HOST = "0.0.0.0"
