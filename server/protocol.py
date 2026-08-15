"""
LAN Trackpad wire protocol — THE SINGLE SOURCE OF TRUTH.

Frame layout:  [opcode:u8][payload ...]   — little-endian throughout.

After editing the opcode table below, regenerate the client mirror:

    make proto        # writes web/protocol.js from this file

Never hand-edit web/protocol.js — it is generated so the two sides can never
drift out of sync.

Notes that matter later:

* Key events (0x11): `keycode` is a macOS VIRTUAL keycode (kVK_* from
  <HIToolbox/Events.h>) — NOT a JS KeyboardEvent.key/.code and NOT ASCII.
  The authoritative JS-name -> kVK_ mapping table lives in exactly ONE place on
  the client (web/keymap.js, added in the keyboard slice). Do not scatter
  partial maps across files.
* `modifiers` (0x11) is a bitmask — see MOD_* below.
* Coordinate deltas are pixels in the phone's own space; the client applies
  pointer acceleration before sending, so the server treats them as final.
"""

import struct

# ------------------------------------------------------------------ opcodes --
# Client -> Server
OP_MOVE          = 0x01  # dx:i16, dy:i16
OP_BUTTON        = 0x02  # button:u8 (see BTN_*), down:u8 (1=press,0=release)
OP_SCROLL        = 0x03  # sx:i16, sy:i16
OP_TEXT          = 0x10  # utf8 bytes (typing / native dictation)
OP_KEY           = 0x11  # keycode:u16 (kVK_*), modifiers:u16 (MOD_* bitmask)
OP_MEDIA         = 0x12  # media/system key: key:u8 (see MEDIA_*)
OP_CLIPBOARD_SET = 0x20  # utf8 (bidirectional; also Server -> Client)
OP_PING          = 0x40  # seq:u32   (client latency probe)
OP_PAIR          = 0x7E  # utf8: 6-digit code or stored token (MUST be 1st frame)
OP_HELLO         = 0x7F  # utf8 JSON {name, caps}

# Server -> Client
OP_LAYOUT_HINT   = 0x30  # utf8 JSON (Phase 2 app-aware layouts)
OP_PONG          = 0x41  # seq:u32   (echo of OP_PING)
OP_PAIR_RESULT   = 0x7D  # ok:u8 (0=ok,1=reject) [+ token utf8 when ok]
OP_ERROR         = 0x7C  # utf8

# --------------------------------------------------------------- bitmasks ----
# Modifier bitmask for OP_KEY.
MOD_SHIFT   = 1 << 0
MOD_CONTROL = 1 << 1
MOD_OPTION  = 1 << 2
MOD_COMMAND = 1 << 3
MOD_FN      = 1 << 4

# Mouse buttons for OP_BUTTON.
BTN_LEFT   = 0
BTN_RIGHT  = 1
BTN_MIDDLE = 2

# Media / system keys for OP_MEDIA (mapped to NX_KEYTYPE_* on the Mac).
MEDIA_PLAY_PAUSE  = 0
MEDIA_NEXT        = 1
MEDIA_PREV        = 2
MEDIA_VOL_UP      = 3
MEDIA_VOL_DOWN    = 4
MEDIA_MUTE        = 5
MEDIA_BRIGHT_UP   = 6
MEDIA_BRIGHT_DOWN = 7

# ----------------------------------------------------------------- framing ---
# Small helpers so all packing/unpacking lives in one place.

def opcode(data: bytes) -> int:
    return data[0]

def payload(data: bytes) -> bytes:
    return data[1:]

def read_move(data: bytes):
    return struct.unpack_from("<hh", data, 1)          # dx, dy

def read_scroll(data: bytes):
    return struct.unpack_from("<hh", data, 1)          # sx, sy

def read_button(data: bytes):
    return data[1], data[2]                             # button, down

def read_u32(data: bytes) -> int:
    return struct.unpack_from("<I", data, 1)[0]

def read_key(data: bytes):
    return struct.unpack_from("<HH", data, 1)          # keycode, modifiers

def read_media(data: bytes) -> int:
    return data[1]                                     # MEDIA_* id

def frame_pong(seq: int) -> bytes:
    return bytes([OP_PONG]) + struct.pack("<I", seq)

def frame_clipboard(text: str) -> bytes:
    return bytes([OP_CLIPBOARD_SET]) + text.encode("utf-8")

def frame_pair_result(ok: bool, token: str = "") -> bytes:
    return bytes([OP_PAIR_RESULT, 0 if ok else 1]) + token.encode("utf-8")

def frame_error(msg: str) -> bytes:
    return bytes([OP_ERROR]) + msg.encode("utf-8")

def frame_layout_hint(json_str: str) -> bytes:
    return bytes([OP_LAYOUT_HINT]) + json_str.encode("utf-8")
