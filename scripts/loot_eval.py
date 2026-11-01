"""Score the bot's loot reader against reference attack screens.

Every frame in tests/ui_frames/manifest.json that records its true
"loot": [gold, elixir, dark] is read with Attacker._read_available_loot and
compared value by value. Run it after any change to the loot reader, and
after a CoC update (add fresh attack screens to the manifest first):

    .venv/bin/python scripts/loot_eval.py
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FRAMES = REPO / "tests" / "ui_frames"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ui_probe import load_frame, use_frame  # noqa: E402


def main():
    import attacker

    reader = attacker.Attacker()
    manifest = json.loads((FRAMES / "manifest.json").read_text())
    ok = total = 0
    for rel, info in manifest["frames"].items():
        if "loot" not in info:
            continue
        use_frame(load_frame(FRAMES / rel))
        loot = reader._read_available_loot()
        got = (loot["gold"], loot["elixir"], loot["dark"]) if loot else (None, None, None)
        marks = ["ok" if g == t else "XX" for g, t in zip(got, info["loot"])]
        ok += marks.count("ok")
        total += 3
        print(f"{rel:42s} truth={tuple(info['loot'])} got={got} {' '.join(marks)}")
    print(f"score: {ok}/{total} values")
    return ok == total


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
