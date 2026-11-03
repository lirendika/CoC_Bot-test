"""Check offline that the app's Pause stops the bot cold.

A fake device records every command the bot sends. While paused, no tap,
swipe, zoom, screenshot, HOME key or force-stop may reach it, fingers the
spam-event drag holds down must be lifted, the bot's exception guards and
@require_exit must pass the pause through, and CoC_Bot.run must wait and
then start a new cycle. Exit 0 when all of that holds:

    .venv/bin/python scripts/pause_eval.py
"""
import sys, threading, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import numpy as np
import utils
from utils import (ADB_Manager, Bot_Paused, Frame_Handler, Input_Handler, Pause_Handler, require_exit,
                   to_system_home, stop_coc)

sent = []

class Conn:
    max_x = max_y = 32767
    def send(self, content): sent.append(content.strip().replace("\nc", ""))   # drop pyminitouch's commit

class Touch:
    connection = Conn()
    def tap(self, points, duration=0): sent.append(f"tap {points}")

class Adb:
    def framebuffer(self): sent.append("framebuffer"); return np.zeros((1080, 1920, 4), np.uint8)
    def shell(self, cmd): sent.append(f"shell {cmd}")

ADB_Manager._minitouch_device = Touch()
ADB_Manager._adbutils_device = Adb()
ADB_Manager._uiautomator_device = object()

results = []
def check(name, cond):
    results.append(bool(cond))
    print(("ok " if cond else "XX ") + name)

def raises_paused(fn):
    try: fn()
    except Bot_Paused: return True
    return False

# Running: touches go out
Pause_Handler.paused = False
Input_Handler.click(0.5, 0.5)
check("running: a click reaches the device", any(c.startswith("d 0") for c in sent))

# Paused: nothing reaches the device
Pause_Handler.paused = True
sent.clear()
check("paused: click raises Bot_Paused", raises_paused(lambda: Input_Handler.click(0.5, 0.5)))
check("paused: swipe raises", raises_paused(lambda: Input_Handler.swipe(0.1, 0.1, 0.5, 0.5, duration=50)))
check("paused: zoom raises", raises_paused(lambda: Input_Handler.zoom("out")))
check("paused: multi_click raises", raises_paused(lambda: Input_Handler.multi_click(0.1, 0.1, 0.2, 0.2)))
check("paused: down raises", raises_paused(lambda: Input_Handler.down(0.3, 0.3)))
check("paused: screenshot raises", raises_paused(lambda: Frame_Handler.get_frame()))
check("paused: HOME key raises", raises_paused(to_system_home))
check("paused: force-stop raises", raises_paused(stop_coc))
check("paused: not a single command was sent", sent == [])
Frame_Handler.cached_frame = np.zeros((1080, 1920, 3), np.uint8)
check("paused: a cached frame is still readable", Frame_Handler.get_frame(use_cached=True) is not None)

# Two fingers held (spam event), then a pause: both are lifted before raising
Pause_Handler.paused = False
Input_Handler.down(0.3, 0.3, pointer=0)
Input_Handler.down(0.6, 0.6, pointer=1)
Input_Handler.move(0.35, 0.35, pointer=0)
sent.clear()
Pause_Handler.paused = True
check("held fingers: move raises", raises_paused(lambda: Input_Handler.move(0.4, 0.4, pointer=1)))
check("held fingers: both lifted", sorted(sent) == ["u 0", "u 1"] and not Input_Handler._held)
sent.clear()
Input_Handler.up(pointer=0)
check("paused: up() still works (never strands a finger)", sent == ["u 0"])

# The bot's usual guards pass it straight through
def guarded():
    try:
        try: Input_Handler.click(0.5, 0.5)
        except (KeyboardInterrupt, SystemExit): raise
        except: return "swallowed"
    except Exception: return "swallowed by except Exception"
check("guards: `except (KeyboardInterrupt, SystemExit): raise` + bare except re-raise it", raises_paused(guarded))

@require_exit()
def decorated():
    Input_Handler.click(0.5, 0.5)
sent.clear()
check("require_exit: re-raises, no clean-up taps", raises_paused(decorated) and sent == [])

# A pause cuts a long sleep short
Pause_Handler.paused = False
threading.Timer(0.3, lambda: setattr(Pause_Handler, "paused", True)).start()
t = time.time()
check("Pause_Handler.sleep(5) ends within ~0.5s of a pause", raises_paused(lambda: Pause_Handler.sleep(5)) and time.time() - t < 0.8)

# CoC_Bot.run: a pause mid-cycle -> wait -> the next cycle starts from the top
import coc_bot
utils.update_status = coc_bot.update_status = lambda s: statuses.append(s)
statuses, cycles = [], []
bot = object.__new__(coc_bot.CoC_Bot)
def cycle():
    cycles.append(time.time())
    if len(cycles) == 1:
        Pause_Handler.paused = True
        threading.Timer(0.6, lambda: setattr(Pause_Handler, "paused", False)).start()
        Input_Handler.click(0.5, 0.5)          # interrupted here
        raise AssertionError("click went through while paused")
    if len(cycles) == 2: raise KeyboardInterrupt  # stop the test loop
bot.run_cycle = cycle
Pause_Handler._thread = threading.current_thread()   # pretend the poller runs: running() reads the flag
try: bot.run()
except KeyboardInterrupt: pass
check("run(): paused, waited, then started a new cycle", len(cycles) == 2 and statuses == ["paused"]
      and cycles[1] - cycles[0] >= 0.55)

print(f"\n{sum(results)}/{len(results)} pause checks passed")
sys.exit(0 if all(results) else 1)
