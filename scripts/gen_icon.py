#!/usr/bin/env python3
"""
Generate kPad's icons (run occasionally; outputs are committed):
  assets/kPad.icns     app/dmg/Finder icon  (squircle + "k" monogram)
  assets/menubar.png   menu-bar template glyph (trackpad + cursor)
  assets/icon.png      1024px PNG for the README / social

Uses AppKit offscreen drawing — macOS only.
"""

import subprocess
from pathlib import Path

from AppKit import (
    NSApplication, NSBezierPath, NSBitmapImageFileTypePNG, NSBitmapImageRep,
    NSColor, NSFont, NSFontAttributeName, NSForegroundColorAttributeName,
    NSGraphicsContext, NSImage, NSMutableParagraphStyle,
    NSParagraphStyleAttributeName, NSTextAlignmentCenter,
)
from Foundation import NSAutoreleasePool, NSMakeRect, NSString

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"


def _png_bytes(img):
    rep = NSBitmapImageRep.alloc().initWithData_(img.TIFFRepresentation())
    return bytes(rep.representationUsingType_properties_(NSBitmapImageFileTypePNG, {}))


def app_icon(size):
    img = NSImage.alloc().initWithSize_((size, size))
    img.lockFocus()
    NSGraphicsContext.currentContext().setShouldAntialias_(True)
    r = size * 0.2237
    path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        NSMakeRect(0, 0, size, size), r, r)
    NSGradient = __import__("AppKit").NSGradient
    grad = NSGradient.alloc().initWithStartingColor_endingColor_(
        NSColor.colorWithSRGBRed_green_blue_alpha_(0.34, 0.86, 0.53, 1.0),
        NSColor.colorWithSRGBRed_green_blue_alpha_(0.07, 0.52, 0.33, 1.0))
    grad.drawInBezierPath_angle_(path, -60)
    para = NSMutableParagraphStyle.alloc().init()
    para.setAlignment_(NSTextAlignmentCenter)
    attrs = {
        NSFontAttributeName: NSFont.boldSystemFontOfSize_(size * 0.6),
        NSForegroundColorAttributeName: NSColor.whiteColor(),
        NSParagraphStyleAttributeName: para,
    }
    s = NSString.stringWithString_("k")
    th = s.sizeWithAttributes_(attrs).height
    s.drawInRect_withAttributes_(NSMakeRect(0, (size - th) / 2.0, size, th), attrs)
    img.unlockFocus()
    return _png_bytes(img)


def menubar_icon(size=36):
    img = NSImage.alloc().initWithSize_((size, size))
    img.lockFocus()
    NSGraphicsContext.currentContext().setShouldAntialias_(True)
    NSColor.blackColor().set()
    m = size * 0.14
    pad = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        NSMakeRect(m, m, size - 2 * m, size - 2 * m), size * 0.2, size * 0.2)
    pad.setLineWidth_(size * 0.085)
    pad.stroke()
    d = size * 0.17
    NSBezierPath.bezierPathWithOvalInRect_(
        NSMakeRect(size * 0.54, size * 0.30, d, d)).fill()
    img.unlockFocus()
    return _png_bytes(img)


def main():
    NSApplication.sharedApplication()   # graphics context for offscreen drawing
    pool = NSAutoreleasePool.alloc().init()
    ASSETS.mkdir(exist_ok=True)

    iconset = ASSETS / "kPad.iconset"
    iconset.mkdir(exist_ok=True)
    for base in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            name = f"icon_{base}x{base}{'@2x' if scale == 2 else ''}.png"
            (iconset / name).write_bytes(app_icon(base * scale))
    subprocess.run(["iconutil", "-c", "icns", str(iconset),
                    "-o", str(ASSETS / "kPad.icns")], check=True)

    (ASSETS / "menubar.png").write_bytes(menubar_icon(36))
    (ASSETS / "icon.png").write_bytes(app_icon(1024))
    del pool
    print("wrote assets/kPad.icns, assets/menubar.png, assets/icon.png")


if __name__ == "__main__":
    main()
