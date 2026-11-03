"""Check on the live game that the bot's taps, swipes and pinch still land.

Run it after changing BlueStacks' frame rate, CPU cores or memory. From the
home village it pinches the view out, then opens the Build panel again and
again, switching tabs and closing it with single taps, and swipes the
builders list down and back up. Each gesture is tried once and checked on
screen, so a gesture the game missed shows up as a miss instead of being
retried away. Nothing is bought and no battle starts:

    .venv/bin/python scripts/touch_check.py [rounds]    # default 10

Exit 0 when the game took every gesture.
"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import utils
from utils import ADB_Manager, Input_Handler, Upgrade_Panel


def wait(cond, timeout=3):
    start = time.time()
    while time.time() - start < timeout:
        if cond(): return True
        time.sleep(0.2)
    return False


def main(rounds):
    utils.ADB_ADDRESS = "127.0.0.1:5555"
    assert ADB_Manager.connect(30), "ADB not reachable"
    home = lambda: utils.get_home_builders(0, return_amount=False, raise_exception=False)
    assert home(), "start the game on the home village first"

    missed, gestures = [], 0
    def miss(what):
        missed.append(what)
        print(f"XX {what}")

    gestures += 1
    Input_Handler.zoom(dir="out")
    if not wait(home): miss("pinch: the village counters were gone afterwards")

    for i in range(rounds):
        tab = ("builders", "research")[i % 2]
        # Build button: one tap, the panel has to show
        gestures += 1
        Input_Handler.click(*Upgrade_Panel.BUILD_BUTTON)
        if not wait(Upgrade_Panel.is_open):
            miss(f"round {i + 1}: Build button tap")
            continue
        # Tab: one tap
        if Upgrade_Panel.active_tab() != tab:
            gestures += 1
            j = Upgrade_Panel.TABS.index(tab)
            Input_Handler.click(sum(Upgrade_Panel._TAB_X[j]) / 2 / utils.WINDOW_DIMS[0],
                                sum(Upgrade_Panel._TAB_Y) / 2 / utils.WINDOW_DIMS[1])
            if not wait(lambda: Upgrade_Panel.active_tab() == tab): miss(f"round {i + 1}: {tab} tab tap")
        # Swipes: the long builders list has to move down, then back up
        if tab == "builders" and i % 4 == 0:
            Upgrade_Panel._settle()
            for down in (True, False):
                gestures += 1
                if not Upgrade_Panel.scroll(down=down): miss(f"round {i + 1}: list swipe {'down' if down else 'up'}")
        # Red X: one tap, the panel has to go
        gestures += 1
        Input_Handler.click(*Upgrade_Panel.CLOSE)
        if not wait(lambda: not Upgrade_Panel.is_open() and not Upgrade_Panel.dialog_open()):
            miss(f"round {i + 1}: close tap")
            Upgrade_Panel.close()
        print(f"ok round {i + 1} ({tab})")
        time.sleep(0.5)

    print(f"\nthe game took {gestures - len(missed)}/{gestures} gestures")
    return not missed


if __name__ == "__main__":
    sys.exit(0 if main(int(sys.argv[1]) if len(sys.argv) > 1 else 10) else 1)
