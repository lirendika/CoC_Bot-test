"""Check offline when the bot rests with CoC closed, and that a rest ends
the right way.

A round that fights no battle and starts no upgrade must close CoC, post
"resting" with the end time, then wait; a busy round must not rest; the Rest
When Idle switch turns it off; flipping any switch in the app or pressing
Pause cuts a rest short. The desktop app's server must keep the rest time in
range and hand the end time to the dashboard. Exit 0 when all of that holds:

    .venv/bin/python scripts/rest_eval.py
"""
import random, sys, threading, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import coc_bot
from utils import Bot_Paused, Pause_Handler, Task_Handler

results = []
def check(name, cond):
    results.append(bool(cond))
    print(("ok " if cond else "XX ") + name)

calls, statuses = [], []
switches = set()          # exclusions the fake app reports (excluded = OFF)
coc_bot.start_coc = lambda force=True: calls.append("start_coc") or True
coc_bot.stop_coc = lambda: calls.append("stop_coc")
coc_bot.to_home_base = lambda ref_cache=False: calls.append("to_home_base")
coc_bot.update_status = lambda status, **extra: statuses.append((status, extra))
Task_Handler.get_exclusions = classmethod(lambda cls, use_cached=False: sorted(switches))
Task_Handler.setting = classmethod(lambda cls, key, default, **kw: 1 if key == "rest_minutes" else default)
naps = []
real_sleep = Pause_Handler.sleep
Pause_Handler.sleep = classmethod(lambda cls, s: naps.append(s))   # pauses between features: skipped

class Part:
    def __init__(self, result): self.result = result
    def run_home_base(self, *args, **kwargs):
        calls.append(type(self).__name__); return self.result
class Upgrader(Part): pass
class Attacker(Part): pass

def make_bot(upgraded, fought):
    bot = object.__new__(coc_bot.CoC_Bot)
    bot.upgrader, bot.attacker = Upgrader(upgraded), Attacker(fought)
    return bot

UNAVAILABLE = {"builder_base", "builder_base_priority", "builder_lab", "builder_lab_priority", "builder_attacks"}
everything_on = set(UNAVAILABLE)

# 1. Attacks and upgrades on, but nothing happened: CoC closes and the bot rests
switches = set(everything_on)
calls.clear(); statuses.clear(); naps.clear()
rests = []
bot = make_bot(upgraded=False, fought=False)
bot.rest = lambda: rests.append(time.time())
bot.run_cycle()
check("idle round: both parts ran", calls[:4] == ["start_coc", "to_home_base", "Upgrader", "Attacker"])
check("idle round: rests", len(rests) == 1)

# 2. A battle was fought: the next round follows right away, no rest
calls.clear(); rests.clear()
bot = make_bot(upgraded=False, fought=True)
bot.rest = lambda: rests.append(time.time())
bot.run_cycle()
check("battle round: no rest", rests == [])

# 3. An upgrade started: no rest either
rests.clear()
bot = make_bot(upgraded=True, fought=False)
bot.rest = lambda: rests.append(time.time())
bot.run_cycle()
check("upgrade round: no rest", rests == [])

# 4. Rest When Idle switched off: idle rounds keep CoC open
switches = everything_on | {"rest_when_idle"}
rests.clear()
bot = make_bot(upgraded=False, fought=False)
bot.rest = lambda: rests.append(time.time())
bot.run_cycle()
check("switch off: idle round does not rest", rests == [])

# 5. Standby (everything off) never opens or closes CoC
switches = everything_on | {"home_base", "home_lab", "wall_focus", "home_attacks"}
calls.clear(); rests.clear()
bot = make_bot(upgraded=False, fought=False)
bot.rest = lambda: rests.append(time.time())
bot.run_cycle()
check("standby: CoC untouched, no rest", calls == [] and rests == [] and statuses[-1][0] == "idle")

# The rest itself (with the real pause-aware sleep)
Pause_Handler.sleep = real_sleep
Pause_Handler.paused = False
Pause_Handler._thread = threading.current_thread()   # pretend the poller runs
real_uniform = random.uniform

# 6. A full rest: CoC closed first, "resting" posted with the end time, then waits
switches = set(everything_on)
calls.clear(); statuses.clear()
random.uniform = lambda a, b: 0.03          # 1 min x 0.03 = 1.8 s
bot = make_bot(False, False)
t = time.time()
bot.rest()
took = time.time() - t
random.uniform = real_uniform
status, extra = statuses[-1]
check("rest: CoC force-closed before waiting", calls == ["stop_coc"])
check("rest: status 'resting' carries the end time", status == "resting" and abs(extra.get("until", 0) - (t + 1.8)) < 0.3)
check(f"rest: waited the whole rest ({took:.1f}s of 1.8s)", 1.7 <= took < 2.6)

# 7. Pressing Start Attack (any switch) in the app ends the rest early
switches = everything_on | {"home_attacks"}
bot = make_bot(False, False)
threading.Timer(0.5, lambda: switches.discard("home_attacks")).start()
t = time.time()
bot.rest()                                   # 1 min x (0.85-1.15)
took = time.time() - t
check(f"rest: a switch flipped in the app wakes the bot ({took:.1f}s)", took < 4)

# 8. Pause during a rest: Bot_Paused right away (the run loop then waits)
switches = set(everything_on)
bot = make_bot(False, False)
threading.Timer(0.4, lambda: setattr(Pause_Handler, "paused", True)).start()
t = time.time()
try:
    bot.rest(); paused = False
except Bot_Paused: paused = True
took = time.time() - t
Pause_Handler.paused = False
check(f"rest: Pause interrupts it at once ({took:.1f}s)", paused and took < 1)

# 9. The desktop app's server: rest time in range, end time handed over
sys.argv = sys.argv[:1]
from gui_server import gui_server
gui_server.instances["main"] = gui_server.Instance("main")
client = gui_server.app.test_client()
check("server: Rest When Idle is ON by default", "rest_when_idle" not in client.get("/main/exclude").json["exclusions"])
check("server: rest time defaults to CHECK_INTERVAL", client.get("/main/settings").json["settings"]["rest_minutes"] == gui_server.CHECK_INTERVAL)
low = client.post("/main/settings", json={"rest_minutes": 0}).json["settings"]["rest_minutes"]
high = client.post("/main/settings", json={"rest_minutes": 9999}).json["settings"]["rest_minutes"]
pct = client.post("/main/settings", json={"wall_focus_min_storage_pct": 150}).json["settings"]["wall_focus_min_storage_pct"]
check(f"server: rest time kept within 1-240 ({low}, {high}), storage % within 100 ({pct})", (low, high, pct) == (1, 240, 100))
client.post("/main/status", json={"status": "resting", "until": 1234.5})
check("server: status hands the rest's end time to the dashboard", client.get("/main/status").json == {"status": "resting", "until": 1234.5})
client.post("/main/status", json={"status": "now"})
check("server: a new status clears it", client.get("/main/status").json["until"] == 0)
page = client.get("/main").get_data(as_text=True)
check("server: dashboard shows the Rest panel", 'id="rows_rest"' in page and "rest_when_idle" in page)

print(f"\n{sum(results)}/{len(results)} rest checks passed")
sys.exit(0 if all(results) else 1)
