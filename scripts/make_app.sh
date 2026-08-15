#!/usr/bin/env bash
# Build a *development* kPad.app that runs the source in place.
#
# Purpose: give Accessibility permission a stable target that is the app itself,
# instead of granting your terminal. Grant "kPad" once in
# System Settings > Privacy & Security > Accessibility and it sticks across runs.
#
# This is NOT the shipping bundle — it references this repo + its .venv by
# absolute path. The self-contained, signed, notarized bundle comes later via
# PyInstaller (scripts/build.sh). If granting this app still doesn't move the
# cursor, that PyInstaller bundle is the definitive fix.
set -euo pipefail

PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$PROJECT/.venv/bin/python"
APP="$PROJECT/dist/kPad.app"
LOG="$HOME/Library/Logs/kPad.log"

if [ ! -x "$PY" ]; then
  echo "No venv found. Run 'make venv' first." >&2
  exit 1
fi

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>            <string>kPad</string>
  <key>CFBundleDisplayName</key>     <string>kPad</string>
  <key>CFBundleIdentifier</key>      <string>com.kailaba.kpad.dev</string>
  <key>CFBundleExecutable</key>      <string>launcher</string>
  <key>CFBundlePackageType</key>     <string>APPL</string>
  <key>CFBundleInfoDictionaryVersion</key> <string>6.0</string>
  <key>CFBundleShortVersionString</key>    <string>0.1</string>
  <key>CFBundleVersion</key>         <string>1</string>
  <key>LSMinimumSystemVersion</key>  <string>13.0</string>
  <key>LSUIElement</key>             <true/>
</dict>
</plist>
PLIST

# Launcher: exec (not subprocess) so the process LaunchServices started — the
# one TCC attributes to this bundle — becomes the server itself.
cat > "$APP/Contents/MacOS/launcher" <<LAUNCH
#!/bin/bash
mkdir -p "\$(dirname "$LOG")"
cd "$PROJECT" || exit 1
echo "--- launched \$(date) ---" >> "$LOG"
exec "$PY" -m server.main >> "$LOG" 2>&1
LAUNCH
chmod +x "$APP/Contents/MacOS/launcher"

# Ad-hoc sign so TCC has a stable identity (cdhash) across rebuilds.
codesign --force --sign - --identifier com.kailaba.kpad.dev "$APP"

echo "Built: $APP"
echo "Log:   $LOG"
