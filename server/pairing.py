"""
Pairing — the only security layer in v1 (and that's fine for a LAN tool).

Model:
* On launch we mint a fresh 6-digit session CODE, shown on the Mac (console now,
  QR + menu bar later). A phone pairs by presenting it.
* On a successful code pairing we issue a long-lived random TOKEN, persist it,
  and hand it to the phone. The phone stores it and presents the token on every
  later connection, so it never has to re-enter the code.
* Tokens live in ~/.lantrackpad/tokens.json (0600). Delete that file to
  un-pair every phone.

Enforcement lives in wsserver: the first frame on a connection must be a valid
OP_PAIR, or no input is acted on.

Threat model: plaintext over the LAN, brute-forceable in principle (10^6 codes).
Acceptable for a personal same-Wi-Fi tool; a wrong code drops the connection so
each guess costs a reconnect. Not a substitute for real auth.
"""

import json
import secrets
from pathlib import Path

STORE_DIR = Path.home() / ".lantrackpad"
STORE_FILE = STORE_DIR / "tokens.json"


class Pairing:
    def __init__(self):
        self.code = f"{secrets.randbelow(1_000_000):06d}"
        self.tokens = self._load()

    def _load(self) -> set:
        try:
            data = json.loads(STORE_FILE.read_text())
            return set(data.get("tokens", []))
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            return set()

    def _save(self):
        STORE_DIR.mkdir(mode=0o700, exist_ok=True)
        STORE_FILE.write_text(json.dumps({"tokens": sorted(self.tokens)}))
        try:
            STORE_FILE.chmod(0o600)
        except OSError:
            pass

    def verify(self, presented: str):
        """Return (ok, issued_token).

        issued_token is a fresh token to hand back when the phone paired via the
        6-digit code; None when it presented an already-valid token.
        """
        presented = (presented or "").strip()
        if presented and presented in self.tokens:
            return True, None
        if presented and secrets.compare_digest(presented, self.code):
            token = secrets.token_hex(16)
            self.tokens.add(token)
            self._save()
            return True, token
        return False, None
