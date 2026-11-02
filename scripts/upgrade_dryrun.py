"""Drive the bot's real upgrade flows on the live game WITHOUT spending.

Every tap goes through a guard that refuses the taps which would spend
anything — the resource and magic-item Confirm buttons of an upgrade dialog
and the Okay of the "Upgrade Walls" popup (it taps Cancel instead) — and logs
what the flow would have bought, saving that screen as debug/dryrun_<n>.png.
Use it after a CoC update to check the upgrade panel end to end:

    .venv/bin/python scripts/upgrade_dryrun.py            # lab, build, wall
    .venv/bin/python scripts/upgrade_dryrun.py lab wall   # some of them
    .venv/bin/python scripts/upgrade_dryrun.py busy       # opt-in, see below
    .venv/bin/python scripts/upgrade_dryrun.py helpers    # opt-in, see below

"busy" checks what happens when every builder is busy: it really presses
Confirm and Okay, which then only bring up "All builders are busy!" (free one
up for gems). It refuses to start while a builder is free, and the gem button
of that popup is never pressed.

"helpers" walks the Builder's Apprentice and Lab Assistant flows (Available
tag, topmost Assign) up to their Confirm, which is blocked, so nothing gets
assigned. It needs both helpers idle.

Needs BlueStacks running with ADB on and CoC open on the home village.
"""
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

import cv2

import utils
from utils import ADB_Manager, Asset_Manager, Frame_Handler, Input_Handler, Upgrade_Panel

BLOCKED = []
ALLOW_CONFIRM = [False]   # the "busy" scenarios press Confirm/Okay for real
_real_click = Input_Handler.click.__func__
_saved = [0]


def save_blocked(frame):
    _saved[0] += 1
    path = REPO / "debug" / f"dryrun_{_saved[0]}.png"
    path.parent.mkdir(exist_ok=True)
    cv2.imwrite(str(path), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    return path.relative_to(REPO)


def guarded_click(cls, x, y, n=1, delay=0, pointer=0):
    frame = Frame_Handler.get_frame(grayscale=False)
    gray = Frame_Handler.grayscale(frame)
    # The gem button of "All builders are busy!" fills the middle of the screen
    _, _, bc = Frame_Handler.locate(Asset_Manager.upgrader_assets["builders_busy"], frame=gray, return_confidence=True)
    if bc >= 0.85 and 0.30 <= x <= 0.70 and 0.40 <= y <= 0.80:
        BLOCKED.append(f"builders-busy gem button at ({x:.3f},{y:.3f})")
        print(f"      [guard] blocked a GEM tap at ({x:.3f},{y:.3f}), screen in {save_blocked(frame)}")
        return
    if not ALLOW_CONFIRM[0]:
        # Any green Confirm on screen counts, even on a dialog laid out unlike
        # the upgrade dialog (whose whole button row is blocked)
        cx, cy, cc = Frame_Handler.locate(Asset_Manager.upgrader_assets["confirm"], frame=frame, grayscale=False,
                                          return_confidence=True)
        near_confirm = cc >= 0.75 and abs(x - cx) < 0.10 and abs(y - cy) < 0.08
        if near_confirm or (Upgrade_Panel.dialog_open(frame) and 0.45 <= x <= 0.80 and 0.78 <= y <= 0.95):
            BLOCKED.append(f"upgrade dialog Confirm at ({x:.3f},{y:.3f})")
            print(f"      [guard] blocked a Confirm tap at ({x:.3f},{y:.3f}), screen in {save_blocked(frame)}")
            return
        hx, hy, hc = Frame_Handler.locate(Asset_Manager.upgrader_assets["confirm_assistant"], frame=frame,
                                          grayscale=False, return_confidence=True)
        if hc >= 0.9 and abs(x - hx) < 0.10 and abs(y - hy) < 0.06:
            BLOCKED.append(f"helper Confirm at ({x:.3f},{y:.3f})")
            print(f"      [guard] blocked a helper Confirm at ({x:.3f},{y:.3f}), screen in {save_blocked(frame)}")
            return
        ox, oy, oc = Frame_Handler.locate(Asset_Manager.attacker_assets["okay"], frame=gray, return_confidence=True)
        if oc >= 0.85 and abs(x - ox) < 0.12 and abs(y - oy) < 0.08:
            BLOCKED.append(f"wall popup Okay at ({x:.3f},{y:.3f})")
            print(f"      [guard] blocked Okay at ({x:.3f},{y:.3f}), screen in {save_blocked(frame)}; tapping Cancel")
            _real_click(cls, 0.389, 0.642)
            return
    _real_click(cls, x, y, n, delay, pointer)


Input_Handler.click = classmethod(guarded_click)


def home_ok():
    return utils.get_home_builders(0, return_amount=False, raise_exception=False)


def run(label, fn, expect):
    BLOCKED.clear()
    t = time.time()
    result = fn()
    time.sleep(0.8)
    clean = home_ok() and not Upgrade_Panel.is_open() and not Upgrade_Panel.dialog_open()
    ok = expect(result, BLOCKED) and clean
    print(f"{'OK ' if ok else 'XX '} {label}: returned {result!r}, would buy {BLOCKED or 'nothing'}, "
          f"back home={clean} ({time.time() - t:.1f}s)")
    return ok


def all_builders_busy(fn):
    """Run fn with Confirm/Okay allowed, but only while no builder is free."""
    def wrapped():
        _, free, _ = utils.read_counter(utils.HOME_BUILDER_COUNTER)
        if free != 0:
            raise SystemExit(f"busy scenarios need every builder busy, {free} free: they would really upgrade")
        ALLOW_CONFIRM[0] = True
        try: return fn()
        finally: ALLOW_CONFIRM[0] = False
    return wrapped


def main(selected):
    utils.ADB_ADDRESS = "127.0.0.1:5555"
    assert ADB_Manager.connect(30), "ADB not reachable"
    assert home_ok(), "start the game on the home village first"
    import upgrader
    U = upgrader.Upgrader()

    scenarios = {
        "lab": [
            ("research: Minion (affordable)", lambda: U.home_lab_specified_upgrade(["Minion"]),
             lambda r, b: r == "Minion" and len(b) == 1),
            ("research: name that isn't listed -> scroll to the end, None", lambda: U.home_lab_specified_upgrade(["Archer Tower"]),
             lambda r, b: r is None and not b),
            ("research: random", lambda: U.home_lab_random_upgrade(),
             lambda r, b: r is not None and len(b) == 1),
        ],
        "build": [
            ("builders: Laboratory (affordable)", lambda: U.home_specified_upgrade(["Laboratory"]),
             lambda r, b: r == "Laboratory" and len(b) == 1),
            ("builders: Monolith (red price) -> skip", lambda: U.home_specified_upgrade(["Monolith"]),
             lambda r, b: r is None and not b),
            ("builders: name that isn't listed -> scroll to the end, None", lambda: U.home_specified_upgrade(["Eagle Artillery"]),
             lambda r, b: r is None and not b),
            ("builders: Builder's Hut (needs scrolling)", lambda: U.home_specified_upgrade(["Builder's Hut"]),
             lambda r, b: r == "Builder's Hut" and len(b) == 1),
            ("builders: random", lambda: U.home_random_upgrade(),
             lambda r, b: r is not None and len(b) == 1),
        ],
        "wall": [
            ("wall: single wall", lambda: U.home_specified_upgrade(["Wall"]),
             lambda r, b: r == "Wall" and len(b) == 1),
            ("wall: batch (wall focus)", lambda: U.home_specified_upgrade("Wall", wall_batch=True, ignore_insufficient=True),
             lambda r, b: r == "Wall" and len(b) == 1),
        ],
        "busy": [
            ("busy: building Confirm -> 'All builders are busy!', None", all_builders_busy(lambda: U.home_specified_upgrade(["Laboratory"])),
             lambda r, b: r is None and not b),
            ("busy: single wall Confirm -> 'All builders are busy!', None", all_builders_busy(lambda: U.home_specified_upgrade(["Wall"])),
             lambda r, b: r is None and not b),
            ("busy: wall batch Okay -> 'All builders are busy!', None",
             all_builders_busy(lambda: U.home_specified_upgrade("Wall", wall_batch=True, ignore_insufficient=True)),
             lambda r, b: r is None and not b),
        ],
        "helpers": [
            ("helpers: Builder's Apprentice -> Assign -> Confirm", lambda: U.assign_builder_apprentice(),
             lambda r, b: r is False and len(b) == 1),
            ("helpers: Lab Assistant -> Assign -> Confirm", lambda: U.assign_lab_assistant(),
             lambda r, b: r is False and len(b) == 1),
        ],
    }
    results = []
    for group in (selected or ("lab", "build", "wall")):
        for label, fn, expect in scenarios[group]:
            results.append(run(label, fn, expect))
    print(f"\n{sum(results)}/{len(results)} scenarios passed")
    return all(results)


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1:]) else 1)
