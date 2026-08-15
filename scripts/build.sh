#!/usr/bin/env bash
# Build kPad into a self-contained .app and a .dmg you can install.
#
# One idempotent script for both local dev and CI. Defaults to ad-hoc signing,
# which is all a locally-built personal app needs (no Apple Developer account).
# For distribution, set the env vars below and it will Developer ID-sign and
# notarize instead — the script is the same, the environment differs.
#
#   CODESIGN_IDENTITY   "Developer ID Application: Your Name (TEAMID)"  (default: - , ad-hoc)
#   NOTARY_PROFILE      name of a stored `notarytool store-credentials` profile (optional)
#
# Never put identities or credentials in the repo — they come from the env only.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=.venv/bin/python
PIP=.venv/bin/pip
APP="dist/kPad.app"
DMG="dist/kPad.dmg"
IDENTITY="${CODESIGN_IDENTITY:--}"     # "-" == ad-hoc

echo "==> Regenerating client protocol mirror"
"$PY" scripts/gen_protocol.py

echo "==> Ensuring PyInstaller is available"
"$PY" -c "import PyInstaller" 2>/dev/null || "$PIP" install -q pyinstaller

echo "==> Building the .app (PyInstaller)"
rm -rf build dist
.venv/bin/pyinstaller --noconfirm kPad.spec

echo "==> Code signing ($([ "$IDENTITY" = "-" ] && echo ad-hoc || echo "$IDENTITY"))"
if [ "$IDENTITY" = "-" ]; then
  codesign --force --deep --sign - "$APP"
else
  codesign --force --deep --timestamp --options runtime --sign "$IDENTITY" "$APP"
fi
codesign --verify --deep --strict "$APP" && echo "    signature verifies"

echo "==> Creating $DMG"
rm -f "$DMG"
# Stage the app next to an /Applications alias so the DMG window offers the
# familiar drag-to-install layout.
STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "kPad" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
rm -rf "$STAGE"

# Optional: notarize + staple (needs a real Developer ID identity + notary profile).
if [ -n "${NOTARY_PROFILE:-}" ] && [ "$IDENTITY" != "-" ]; then
  echo "==> Notarizing (profile: $NOTARY_PROFILE)"
  xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" --wait
  xcrun stapler staple "$DMG"
  xcrun stapler staple "$APP"
  echo "    notarized + stapled"
else
  echo "==> Skipping notarization (ad-hoc build — fine for local install)"
fi

echo ""
echo "Done:"
echo "  App: $APP"
echo "  DMG: $DMG"
echo ""
echo "Install: open the .dmg and drag kPad onto Applications, then grant"
echo "Accessibility once. A downloaded ad-hoc build is blocked by Gatekeeper —"
echo "open it via System Settings > Privacy & Security > Open Anyway, or run:"
echo "  xattr -dr com.apple.quarantine \"/Applications/kPad.app\""
