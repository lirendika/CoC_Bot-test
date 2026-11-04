"""Check offline that update_coc reaches the real uiautomator2 device and
presses Update the safe way.

A fake u2 device shows chosen buttons and records every look and click.
update_coc must press only a button reading Update (any case) in CoC or
Google Play, stay silent when CoC shows no update dialog, go home after
opening the Play Store itself, report u2 errors, and never click once the
app's Pause is pressed, even while it waits for the Play Store. Exit 0
when all of that holds:

    .venv/bin/python scripts/update_eval.py
"""
import contextlib, io, re, sys, threading, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from utils import ADB_Manager, Bot_Paused, Pause_Handler, update_coc

COC, PLAY = "com.supercell.clashofclans", "com.android.vending"
MARKET = 'am start -a android.intent.action.VIEW -d "market://details?id=com.supercell.clashofclans"'
HOME = "input keyevent KEYCODE_HOME"

class Ui:
    """The fake u2 device. `screen` holds the (text, package) buttons shown;
    `then` maps a button to (seconds, next screen[, Pause pressed then])
    for what its click brings up."""
    def __init__(self, screen=(), then=None, broken=False):
        self.screen, self.then, self.broken = set(screen), then or {}, broken
        self.looks, self.clicks = 0, []
    def __call__(self, **selector): return Obj(self, selector)

class Obj:
    def __init__(self, ui, selector): self.ui, self.selector = ui, selector
    def find(self):
        s = self.selector
        for text, package in sorted(self.ui.screen):
            if "text" in s and s["text"] != text: continue
            if "textMatches" in s and not re.fullmatch(s["textMatches"], text): continue
            if "packageName" in s and s["packageName"] != package: continue
            if "packageNameMatches" in s and not re.fullmatch(s["packageNameMatches"], package): continue
            return text, package
    def wait(self, exists=True, timeout=None):
        if self.ui.broken: raise ConnectionError("uiautomator2 server not answering")
        self.ui.looks += 1
        end = time.time() + timeout
        while self.find() is None and time.time() < end: time.sleep(0.02)
        return self.find() is not None
    def click(self, timeout=None, offset=None):
        button = self.find()
        if button is None: raise LookupError("UiObjectNotFoundError")
        self.ui.clicks.append(button)
        if button in self.ui.then:
            delay, screen, *pause = self.ui.then[button]
            def change():
                self.ui.screen = set(screen)
                if pause: Pause_Handler.paused = True
            threading.Timer(delay, change).start()

class Adb:
    def __init__(self): self.sent = []
    def shell(self, cmd): self.sent.append(cmd)

class Touch:   # never used: keeps ADB_Manager from connecting to BlueStacks
    class connection: max_x = max_y = 32767

results = []
def check(name, cond):
    results.append(bool(cond))
    print(("ok " if cond else "XX ") + name)

def run(ui, paused=False, pause_after=None, **kwargs):
    """update_coc on the fake device: (result or "paused", output, seconds, shell sent)."""
    ADB_Manager._uiautomator_device, ADB_Manager._adbutils_device = ui, Adb()
    ADB_Manager._minitouch_device = Touch()
    Pause_Handler.paused = paused
    timer = threading.Timer(pause_after or 0, lambda: setattr(Pause_Handler, "paused", True))
    if pause_after is not None: timer.start()
    out, t = io.StringIO(), time.time()
    with contextlib.redirect_stdout(out):
        try: result = update_coc(**kwargs)
        except Bot_Paused: result = "paused"
    took = time.time() - t
    timer.cancel()
    Pause_Handler.paused = False
    return result, out.getvalue(), took, ADB_Manager._adbutils_device.sent

dialog = ("UPDATE", COC)
store = {("Update", PLAY), ("Uninstall", PLAY)}

# 1. start_coc's look on every loading screen. Through the DeviceProxy this
#    was a TypeError, printed as "Failed to click update button" every time
ui = Ui(screen={("Loading", COC)})
result, out, took, sent = run(ui, timeout=5, from_in_game=True)
check(f"no dialog: one quick look on the u2 device ({took:.2f}s), nothing pressed or printed",
      result is False and ui.looks == 1 and ui.clicks == [] and out == "" and sent == [] and took < 0.3)

# 2. CoC asks for an update: its UPDATE, then Google Play's Update once the page is up
ui = Ui(screen={dialog}, then={dialog: (0.7, store)})
result, out, took, sent = run(ui, timeout=5, from_in_game=True)
check("in game: UPDATE pressed, then the Play Store's Update", result is True
      and ui.clicks == [dialog, ("Update", PLAY)] and "Updating CoC" in out)
check("in game: stays in CoC's flow for start_coc (no HOME)", sent == [])

# 3. The dialog's button as newer Android themes write it
ui = Ui(screen={("Update", COC)}, then={("Update", COC): (0.1, store)})
check("in game: an 'Update' (not all caps) is found too", run(ui, timeout=5, from_in_game=True)[0] is True)

# 4. Only Update itself, and only in CoC or Google Play
ui = Ui(screen={("Update", "com.android.systemui"), ("Updated", COC), ("Update now?", COC)})
result, out, took, sent = run(ui, timeout=5, from_in_game=True)
check("in game: a notification's Update, 'Updated', 'Update now?' left alone", result is False and ui.clicks == [])
ui = Ui(screen={("Update all", PLAY), ("Install", PLAY), ("Buy", PLAY), ("Update", "com.android.systemui")})
result, out, took, sent = run(ui, timeout=0.6)
check("Play Store: 'Update all', Install, Buy, other apps left alone", result is False and ui.clicks == [])

# 5. Opened from outside the game: CoC's page, Update, home
ui = Ui(screen=store)
result, out, took, sent = run(ui, timeout=5)
check("Play Store path: page opened, Update pressed, then HOME", result is True and sent == [MARKET, HOME]
      and ui.clicks == [("Update", PLAY)])

# 6. Already up to date: Open instead of Update
ui = Ui(screen={("Open", PLAY), ("Uninstall", PLAY)})
result, out, took, sent = run(ui, timeout=0.6)
check("up to date: nothing pressed, says so, goes home", result is False and ui.clicks == []
      and "no Update" in out and sent == [MARKET, HOME])

# 7. Paused before it starts: no look, no Play Store, no HOME
ui = Ui(screen=store | {dialog})
result, out, took, sent = run(ui, paused=True, timeout=5)
check("paused: Bot_Paused before any look, page or click", result == "paused" and ui.looks == 0
      and ui.clicks == [] and sent == [])

# 8. Pause while it waits for the Play Store page: stops at once, no click
ui = Ui(screen={dialog}, then={dialog: (3, store)})
result, out, took, sent = run(ui, pause_after=0.4, timeout=5, from_in_game=True)
check(f"pause mid-wait: Bot_Paused at once ({took:.2f}s), Update never pressed", result == "paused"
      and ui.clicks == [dialog] and took < 1.2 and sent == [])

# 9. The Update button shows the moment Pause is pressed: the check before the click holds
ui = Ui(screen={dialog}, then={dialog: (0.3, store, True)})
result, out, took, sent = run(ui, timeout=5, from_in_game=True)
check("pause as the button appears: no click, no 'Updating' in the log", result == "paused"
      and ui.clicks == [dialog] and "Updating" not in out)

# 10. u2 broken: said out loud (the old bare except hid a TypeError), still goes home
ui = Ui(broken=True)
result, out, took, sent = run(ui, timeout=5)
check("u2 error: reported with its reason, then HOME", result is False and "Couldn't update CoC" in out
      and "not answering" in out and sent == [MARKET, HOME])

print(f"\n{sum(results)}/{len(results)} update checks passed")
sys.exit(0 if all(results) else 1)
