"""Run the bot's real detection code against saved screenshots, offline.

Frame_Handler.get_frame is swapped for a screenshot file, so every bot
function sees exactly that screen — no BlueStacks or ADB needed. Use it to
check whether a CoC update broke a template or a screen position.

Usage (from the repo root):
    .venv/bin/python scripts/ui_probe.py <shot.png> scan
        best match of every template asset (grayscale and color)
    .venv/bin/python scripts/ui_probe.py <shot.png> eval "<python expression>"
        evaluate an expression; utils, attacker, upgrader, A (an Attacker)
        and U (an Upgrader) are available, e.g.
        "utils.get_home_builders(0, return_amount=False, raise_exception=False)"
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

import cv2

import utils
from utils import Frame_Handler, Asset_Manager

ASSET_SETS = {
    "misc": Asset_Manager.misc_assets,
    "upgrader": Asset_Manager.upgrader_assets,
    "attacker": Asset_Manager.attacker_assets,
}


def load_frame(path):
    """Read a screenshot as the RGB frame the bot would capture."""
    bgr = cv2.imread(str(path))
    if bgr is None:
        raise SystemExit(f"cannot read {path}")
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return cv2.resize(rgb, utils.WINDOW_DIMS, interpolation=cv2.INTER_NEAREST)


def use_frame(rgb):
    """Make every Frame_Handler.get_frame call return this frame."""
    def fake_get_frame(cls, grayscale=True, high_contrast=False, thresh=200, use_cached=False):
        frame = rgb.copy()
        cls.cached_frame = frame.copy()
        if high_contrast:
            return cls.high_contrast(frame, thresh)
        return cls.grayscale(frame) if grayscale else frame

    Frame_Handler.get_frame = classmethod(fake_get_frame)
    Frame_Handler.cached_frame = rgb.copy()


def scan():
    for group, assets in ASSET_SETS.items():
        for name in sorted(assets):
            x, y, cg = Frame_Handler.locate(assets[name], grayscale=True, return_confidence=True, use_cached=True)
            _, _, cc = Frame_Handler.locate(assets[name], grayscale=False, return_confidence=True, use_cached=True)
            loc = f"({x:.3f},{y:.3f})" if x is not None else ""
            print(f"  {group:9s} {name:20s} gray={cg:.2f} color={cc:.2f} {loc}")


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    shot, cmd, *args = sys.argv[1:]
    use_frame(load_frame(shot))
    if cmd == "scan":
        scan()
    elif cmd == "eval":
        import attacker, upgrader
        # as globals, so comprehensions inside the expression can see them too
        names = {**globals(), "attacker": attacker, "upgrader": upgrader,
                 "A": attacker.Attacker(), "U": upgrader.Upgrader()}  # constructors only load assets
        print(eval(args[0], names))
    else:
        raise SystemExit(f"unknown command {cmd!r}\n{__doc__}")


if __name__ == "__main__":
    main()
