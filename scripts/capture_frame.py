"""Save the current BlueStacks screen as a reference frame for offline tests.

    .venv/bin/python scripts/capture_frame.py <folder/name> [adb-address]

Writes tests/ui_frames/<folder/name>.webp (lossless, pixel-exact, ~30%
smaller than PNG). Afterwards describe the frame in
tests/ui_frames/manifest.json so it isn't a mystery later.
"""
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

FRAMES = Path(__file__).resolve().parent.parent / "tests" / "ui_frames"


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    name = sys.argv[1]
    addr = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1:5555"
    png = subprocess.run(["adb", "-s", addr, "exec-out", "screencap", "-p"],
                         capture_output=True, check=True).stdout
    frame = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise SystemExit("no screenshot received — is BlueStacks running with ADB on?")
    out = FRAMES / f"{name}.webp"
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), frame, [cv2.IMWRITE_WEBP_QUALITY, 101])  # >100 = lossless
    print(f"saved {out.relative_to(FRAMES.parent.parent)} ({frame.shape[1]}x{frame.shape[0]})")


if __name__ == "__main__":
    main()
