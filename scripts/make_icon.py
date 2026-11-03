"""Build the app icon from the dashboard's sword logo (macOS only).

    .venv/bin/python scripts/make_icon.py                     # media/CoC_Bot.icns
    .venv/bin/python scripts/make_icon.py --app "CoC Bot.app" # and the launcher's icon

Renders src/gui_server/static/logo.svg at every iconset size with macOS's own
SVG renderer (NSImage reads SVG natively), adds a soft shadow so the sword
stands out in the Dock, and packs the sizes with iconutil. media/CoC_Bot.icns
is what the Dock (gui.py), the desktop launcher and scripts/build.sh use.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from AppKit import (NSBitmapImageRep, NSCompositingOperationSourceOver, NSDeviceRGBColorSpace,
                    NSGraphicsContext, NSImage, NSMakeRect, NSPNGFileType)
from PIL import Image, ImageFilter

REPO = Path(__file__).resolve().parent.parent
LOGO = REPO / "src" / "gui_server" / "static" / "logo.svg"
ICNS = REPO / "media" / "CoC_Bot.icns"
SIZES = (16, 32, 64, 128, 256, 512, 1024)
ART = 0.94   # the sword's share of the canvas, inside Apple's icon grid


def render(svg, size, out):
    image = NSImage.alloc().initWithContentsOfFile_(str(svg))
    if image is None:
        raise SystemExit(f"macOS can't read {svg}")
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, size, size, 8, 4, True, False, NSDeviceRGBColorSpace, 0, 0)
    context = NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(context)
    image.drawInRect_fromRect_operation_fraction_(NSMakeRect(0, 0, size, size), NSMakeRect(0, 0, 0, 0),
                                                  NSCompositingOperationSourceOver, 1.0)
    context.flushGraphics()
    NSGraphicsContext.restoreGraphicsState()
    rep.representationUsingType_properties_(NSPNGFileType, {}).writeToFile_atomically_(str(out), True)


def icon(size, tmp):
    art = max(1, round(size * ART))
    raw = tmp / f"raw_{size}.png"
    render(LOGO, art, raw)
    sword = Image.open(raw).convert("RGBA")
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    offset = ((size - art) // 2, (size - art) // 2)
    if size >= 64:   # tiny sizes stay crisp without it
        alpha = Image.new("L", (size, size), 0)
        alpha.paste(sword.getchannel("A"), (offset[0], offset[1] + size // 64))
        alpha = alpha.filter(ImageFilter.GaussianBlur(size / 100)).point(lambda a: a * 0.4)
        canvas.paste(Image.new("RGBA", (size, size), (0, 0, 0, 255)), (0, 0), alpha)
    canvas.alpha_composite(sword, offset)
    return canvas


def main():
    tmp = Path(tempfile.mkdtemp())
    iconset = tmp / "CoC_Bot.iconset"
    iconset.mkdir()
    images = {size: icon(size, tmp) for size in SIZES}
    for size in SIZES[:-1]:
        images[size].save(iconset / f"icon_{size}x{size}.png")
        images[size * 2].save(iconset / f"icon_{size}x{size}@2x.png")
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(ICNS)], check=True)
    print(f"wrote {ICNS.relative_to(REPO)}")

    if "--app" in sys.argv:
        app = Path(sys.argv[sys.argv.index("--app") + 1]).resolve()
        target = app / "Contents" / "Resources" / "icon.icns"
        shutil.copyfile(ICNS, target)
        subprocess.run(["touch", str(app)], check=True)   # makes Finder pick the new icon up
        print(f"installed {target}")
    shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
