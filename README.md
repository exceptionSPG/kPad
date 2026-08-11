# LAN Trackpad

Turn any phone into a Mac trackpad over your local network. No phone app, no
internet, no cloud — the Mac serves a web page and the phone's browser is the
whole client.

## Status

**Slice 1 — cursor moves end-to-end.** Trackpad surface on the phone drives the
Mac cursor with tunable pointer acceleration. A hidden dev panel (append
`?dev=1` or triple-tap the top-left corner) exposes live sliders for accel `k`,
cap, deadzone, and scroll multiplier, plus a round-trip latency readout. Clicks,
scroll, keyboard, pairing, QR, and the menu bar come in later slices.

## Run (dev)

```bash
make run
```

First launch will tell you if **Accessibility permission** is missing — grant it
to whatever runs the server (your terminal app for `make run`), otherwise macOS
silently drops synthesized events and the cursor won't move.

Then open the printed `http://<hostname>.local:8787/` on a phone on the same
Wi-Fi. (If `.local` doesn't resolve, use the printed IP URL.)

## Tuning the cursor feel

Open the dev panel on the phone, adjust the sliders until it feels right (values
persist in `localStorage`), then tap **copy config** and paste the JSON into
`DEFAULT_POINTER` in `server/config.py` to make it the new default.

## Layout

- `server/protocol.py` — the opcode table, single source of truth. Run
  `make proto` to regenerate `web/protocol.js`; never edit that file by hand.
- `server/` — aiohttp HTTP+WS server, Quartz input synthesis, display clamp.
- `web/` — the phone client (vanilla HTML/CSS/JS, no build step).

## Constraints

LAN only. No cloud/relay/accounts/WebRTC. Works with zero internet. macOS 13+,
iOS Safari 16+, Chrome on Android.
