#!/usr/bin/env python3
"""
Generate web/protocol.js from server/protocol.py so the opcode table can never
drift between the two sides. Run via `make proto`. Do not edit protocol.js.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server import protocol as P  # noqa: E402

PREFIXES = ("OP_", "MOD_", "BTN_", "MEDIA_")
OUT = ROOT / "web" / "protocol.js"


def main():
    names = [n for n in dir(P) if n.startswith(PREFIXES) and isinstance(getattr(P, n), int)]
    names.sort(key=lambda n: (PREFIXES.index(next(p for p in PREFIXES if n.startswith(p))), getattr(P, n)))
    lines = [
        "// GENERATED from server/protocol.py by `make proto` — DO NOT EDIT.",
        "// Frames are little-endian: [opcode:u8][payload...].",
        "window.PROTO = Object.freeze({",
    ]
    for n in names:
        lines.append(f"  {n}: 0x{getattr(P, n):02X},")
    lines.append("});")
    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(names)} constants)")


if __name__ == "__main__":
    main()
