# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for LAN Trackpad. Build via scripts/build.sh (or `make dmg`).

from PyInstaller.utils.hooks import collect_submodules

# pyobjc is lazily loaded; pull in the frameworks we touch so nothing is missing
# at runtime inside the frozen bundle.
hiddenimports = []
for mod in ("objc", "Foundation", "AppKit", "Cocoa", "Quartz",
            "ApplicationServices", "CoreFoundation"):
    hiddenimports += collect_submodules(mod)

a = Analysis(
    ["app_entry.py"],
    pathex=[],
    binaries=[],
    datas=[("web", "web")],          # bundle the phone client
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="LANTrackpad",
    debug=False,
    strip=False,
    upx=False,
    console=False,                   # menu-bar app, no terminal window
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="LANTrackpad")

app = BUNDLE(
    coll,
    name="LAN Trackpad.app",
    icon=None,
    bundle_identifier="com.lantrackpad.app",
    info_plist={
        "LSUIElement": True,                 # menu-bar only, no Dock icon
        "LSMinimumSystemVersion": "13.0",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "1",
        "NSHighResolutionCapable": True,
    },
)
