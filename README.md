# LAN Trackpad

Turn any phone into a Mac trackpad over your local network. No phone app, no
internet, no cloud — the Mac serves a web page and the phone's browser is the
whole client.

## Status

**Slice 2 — full pointer + gestures.** On top of the moving cursor:

- one-finger **tap = left click** (two quick taps = double-click, via server
  click-state); **two-finger tap = right click**
- **two-finger scroll with inertia** (momentum runs on the phone, so it feels
  right regardless of Wi-Fi latency)
- **tap-and-a-half drag lock**: tap, then touch-and-drag holds the button; lift
  and it stays locked (amber border) until you tap to drop
- drags emit real *Dragged* events (text selection, window moves work)
- **release-all safety** on every disconnect path: socket close (server-side)
  and page-hide / phone-lock (client-side) both force every button up

**Pairing (Slice 3).** The Mac prints a fresh 6-digit code on launch; the phone
enters it once. On success the Mac issues a long-lived token the phone stores, so
it never re-prompts (reconnects re-pair silently). Unpaired clients can't drive
input — enforced server-side. Wrong codes keep the socket open to retry (error
stays visible), capped at 5 tries per connection. Tokens live in
`~/.lantrackpad/tokens.json` (0600); delete it to un-pair every phone.

A hidden dev panel (append `?dev=1` or triple-tap the top-left corner) exposes
live sliders for accel `k`, cap, deadzone, scroll multiplier, plus a round-trip
latency readout. Keyboard, voice, clipboard, QR, and the menu bar come in later
slices.

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

Pointer feel is owned by the client — a permanent per-user feature, not a
build-time setting. Open the dev panel on the phone (`?dev=1` or triple-tap the
top-left corner) and adjust the sliders until it feels right; each phone persists
its own curve in `localStorage`. **copy config** dumps the JSON so you can back
up a good curve or seed a fresh phone's first-run defaults (in `web/app.js`
`DEFAULTS`).

## Layout

- `server/protocol.py` — the opcode table, single source of truth. Run
  `make proto` to regenerate `web/protocol.js`; never edit that file by hand.
- `server/` — aiohttp HTTP+WS server, Quartz input synthesis, display clamp.
- `web/` — the phone client (vanilla HTML/CSS/JS, no build step).

## Constraints

LAN only. No cloud/relay/accounts/WebRTC. Works with zero internet. macOS 13+,
iOS Safari 16+, Chrome on Android.
