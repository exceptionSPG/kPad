# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for kPad. Build via scripts/build.sh (or `make dmg`).

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
    datas=[
        ("web", "web"),                        # bundle the phone client
        ("assets/menubar.png", "assets"),      # menu-bar template icon
    ],
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
    name="kPad",
    debug=False,
    strip=False,
    upx=False,
    console=False,                   # menu-bar app, no terminal window
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="kPad")

app = BUNDLE(
    coll,
    name="kPad.app",
    icon="assets/kPad.icns",
    bundle_identifier="com.kailaba.kpad",
    info_plist={
        "LSUIElement": True,                 # menu-bar only, no Dock icon
        "LSMinimumSystemVersion": "13.0",
        "CFBundleShortVersionString": "0.2.7",
        "CFBundleVersion": "9",
        "NSHighResolutionCapable": True,
    },
)
