"""Check offline how the bot reads the gold, elixir and dark elixir it holds
(utils.Storage_Reader) and how full each storage is.

Every frame whose manifest entry has 'resources' shows the counters top
right: the reader must read all three amounts exactly, and the bar alone
must put each storage within 1% of the entry's 'storage' (amount /
capacity). Read in turn, those frames must teach it the capacities within
1%, after which every level follows the digits to within 0.6%. Every other
frame (a panel, popup, dialog, cloud or haze over the counters) must read
as nothing, not a guess. Made-up readings then check the learning (a
misread digit, another account, an upgraded storage, a full or nearly
empty storage) and the decisions built on it: attacks stop only once gold
and elixir are both 90% full, and wall focus waits for its 'Wall Focus ≥ %'.
Exit 0 when all of that holds:

    .venv/bin/python scripts/storage_eval.py
"""
import contextlib
import io
import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FRAMES = REPO / "tests" / "ui_frames"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ui_probe import load_frame, use_frame  # noqa: E402  (puts src on the path)

import numpy as np  # noqa: E402
import utils  # noqa: E402
from utils import Storage_Reader as S  # noqa: E402

NAMES = ("gold", "elixir", "dark")
results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(("ok " if cond else "XX ") + name + (f"\n   {detail}" if detail and not cond else ""))


manifest = json.loads((FRAMES / "manifest.json").read_text())["frames"]
frames = {rel: info for rel, info in manifest.items() if rel.startswith("coc_")}
shown = {rel: info for rel, info in frames.items() if "resources" in info}

# 1. Each frame on its own, nothing learned yet
wrong, bars, guesses = [], [], []
for rel, info in frames.items():
    S.reset()
    got = S.read(load_frame(FRAMES / rel))
    if rel not in shown:
        if any(r["amount"] is not None or r["level"] is not None for r in got.values()):
            guesses.append(f"{rel}: {S.describe(got)}")
        continue
    for name, want in zip(NAMES, info["resources"]):
        if got[name]["amount"] != want:
            wrong.append(f"{rel} {name}: {got[name]['amount']} instead of {want}")
        level = got[name]["level"]
        if level is None or abs(level - info["storage"][name]) > 0.01:
            bars.append(f"{rel} {name}: {level} instead of {info['storage'][name]}")
check(f"amounts: gold, elixir and dark elixir read exactly on all {len(shown)} frames showing the counters",
      not wrong, "; ".join(wrong))
check("bars alone: every storage within 1% of amount / capacity (attack screen 2 px further right, "
      "pink crystals behind attack_5's elixir bar)", not bars, "; ".join(bars))
check(f"no guesses: the other {len(frames) - len(shown)} frames (panels, popups, dialogs, clouds, haze) read as nothing",
      not guesses, "; ".join(guesses))

# 2. The frames in turn: capacities settle, then the levels follow the digits
S.reset()
for rel in shown: S.read(load_frame(FRAMES / rel))
truth = {name: statistics.median(info["resources"][i] / info["storage"][name] for info in shown.values()
                                 if info["storage"][name] >= 0.25) for i, name in enumerate(NAMES)}
learned = {name: statistics.median(S._estimates[name]) if S._estimates.get(name) else None for name in NAMES}
check("capacities learned within 1%: " + ", ".join(
          f"{n} {learned[n] or 0:,.0f} (~{truth[n]:,.0f})" for n in NAMES),
      all(learned[n] and abs(learned[n] / truth[n] - 1) <= 0.01 for n in NAMES))
off = []
for rel, info in shown.items():
    got = S.read(load_frame(FRAMES / rel))
    for name in NAMES:
        if got[name]["level"] is None or abs(got[name]["level"] - info["storage"][name]) > 0.006:
            off.append(f"{rel} {name}: {got[name]['level']} instead of {info['storage'][name]}")
check("levels: amount / learned capacity within 0.6% on every frame", not off, "; ".join(off))
home = S.read(load_frame(FRAMES / "coc_18.647_2026-11/home.webp"))
line = S.describe(home)
check(f"log line: '{line}'", line.startswith("gold 9,388,101 of ~26.") and "elixir 13,935,650 of ~26." in line
      and "dark 83,017 of ~44" in line and "(36%)" in line)

# 3. Learning, on made-up readings: the counter shows `amount`, the bar `bar`
script = []
own = {key: vars(S)[key] for key in ("_on_screen", "_amount", "_bar")}
S._on_screen = classmethod(lambda cls, f, name: True)
S._amount = classmethod(lambda cls, frame, name: script[0][0] if name == "gold" else None)
S._bar = classmethod(lambda cls, f, name: script[0][1] if name == "gold" else None)
blank = np.zeros((1080, 1920, 3), np.uint8)


def gold(amount, bar):
    script[:] = [(amount, bar)]
    return S.read(blank)["gold"]


S.reset()
for a in (9_100_000, 13_000_000, 17_550_000): gold(a, a / 26e6)
r = gold(938_810, 0.361)   # 9 388 101 with its 1 missed
check("a misread digit: the bar decides (36%), the capacity stays", abs(r["level"] - 0.361) < 1e-9
      and abs(r["capacity"] - 26e6) < 1e5)
r = gold(9_388_101, 0.361)
check("the next good reading: amount / capacity again", abs(r["level"] - 9_388_101 / 26e6) < 0.002)
r = gold(2_000_000, 0.5)   # another account: a 4M storage
check("another account: its first reading goes by the bar and keeps the old capacity",
      abs(r["level"] - 0.5) < 1e-9 and abs(r["capacity"] - 26e6) < 2e5)
r = gold(2_100_000, 0.525)
check("its second agreeing reading replaces the capacity (4M)", abs(r["capacity"] - 4e6) < 1e4
      and abs(r["level"] - 0.525) < 0.002)
S.reset()
for a in (9_100_000, 13_000_000, 17_550_000): gold(a, a / 26e6)
for a in (10e6, 12e6, 14e6, 16e6): r = gold(a, a / 26.6e6)    # a storage upgrade: +2.3%
check("an upgraded storage (+2.3%): the capacity follows within 4 readings", abs(r["capacity"] - 26.6e6) < 1e5)
r = gold(26_600_000, 1.0)
check("a full storage reads 100% (and doesn't teach a capacity off the clipped bar end)",
      r["level"] == 1.0 and abs(r["capacity"] - 26.6e6) < 1e5)
r = gold(1_330_000, None)
check("too little fill for the bar: amount / capacity (5%)", abs(r["level"] - 0.05) < 0.001)
script[:] = [(None, None)]
S.reset()
check("nothing readable and nothing learned: no level", S.read(blank)["gold"]["level"] is None)
for key, method in own.items(): setattr(S, key, method)   # back to the real reader

# 4. Decisions: stop attacking only when both are 90% full; wall focus waits
import attacker  # noqa: E402
import upgrader  # noqa: E402
A, U = attacker.Attacker(), upgrader.Upgrader()


def levels(g, e, d=0.4):
    return {name: {"amount": None if v is None else int(v * 26e6), "capacity": 26_000_000,
                   "level": v} for name, v in zip(NAMES, (g, e, d))}


real_read = S.read


def full(g, e):
    S.read = classmethod(lambda cls, frame=None: levels(g, e))
    out = io.StringIO()
    with contextlib.redirect_stdout(out): result = A._storages_full()
    S.read = real_read
    return result, out.getvalue()


got, log = full(0.92, 0.99)
check("gold 92% + elixir 99%: full, attack skipped, amounts in the log", got is True
      and "gold 23,920,000 of ~26.0M (92%)" in log and "skipping attack" in log)
check("gold 89% + elixir 99%: keeps attacking", full(0.89, 0.99)[0] is False)
check("gold unreadable + elixir 99%: keeps attacking", full(None, 0.99)[0] is False)
use_frame(load_frame(FRAMES / "coc_18.647_2026-11/home.webp"))
S.reset()
out = io.StringIO()
with contextlib.redirect_stdout(out): got = A._storages_full()
check(f"home.webp: not full, logged as '{out.getvalue().strip()}'", got is False
      and "gold 9,388,101" in out.getvalue() and "skipping" not in out.getvalue())

closed = []
utils.Upgrade_Panel.close = classmethod(lambda cls, **kw: closed.append(True) or True)
S.reset()
with contextlib.redirect_stdout(io.StringIO()):
    waits = U._wall_storage_ready(0.9)   # home.webp: gold 36%, elixir 53%
    goes = U._wall_storage_ready(0.5)
check("wall focus: closes the panel, waits below 90% (36% / 53%), goes at 50%",
      closed and waits is False and goes is True)
use_frame(load_frame(FRAMES / "coc_18.647_2026-11/build_panel.webp"))
with contextlib.redirect_stdout(io.StringIO()):
    check("wall focus: counters still covered: walls aren't held back", U._wall_storage_ready(0.9) is True)

print(f"\n{sum(results)}/{len(results)} storage checks passed")
sys.exit(0 if all(results) else 1)
