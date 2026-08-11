"""
Server configuration.

Network + timing live here. Pointer *feel* (accel k, cap, deadzone, scroll
multiplier) is tuned live in the client dev panel (?dev=1 or triple-tap the
top-left corner) and persisted in the phone's localStorage. The DEFAULT_POINTER
block below is only the paste target: tune on the phone, hit "copy config", and
paste the JSON here to bake in new client defaults.
"""

# Port for both HTTP and WebSocket (one URL, one QR code).
PORT = 8787

# Bind on all interfaces so the phone can reach us over the LAN.
HOST = "0.0.0.0"

# Client pointer defaults (mirrored by web/trackpad.js). Paste dev-panel output
# here to change what a fresh phone starts with.
DEFAULT_POINTER = {
    "k": 0.08,          # acceleration coefficient: gain = 1 + min(speed*k, cap)
    "cap": 3.0,         # max added gain
    "deadzone": 0.4,    # ignore per-event moves smaller than this (px)
    "scrollMult": 1.0,  # scroll speed multiplier
}
