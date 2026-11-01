"""Check Upgrade_Panel against the reference frames.

Every frame's manifest entry says whether the upgrade panel is open (and on
which tab), whether an upgrade dialog is up, and for hand-checked panel
frames the name/affordable/new state of each purchasable row, and for home
frames how full the gold and elixir storages are. Exit 0 when everything
agrees:

    .venv/bin/python scripts/panel_eval.py
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FRAMES = REPO / "tests" / "ui_frames"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ui_probe import load_frame, use_frame  # noqa: E402


def main():
    import utils
    from utils import Upgrade_Panel as P

    manifest = json.loads((FRAMES / "manifest.json").read_text())["frames"]
    names = sorted({r["name"] for info in manifest.values() for r in info.get("panel", {}).get("rows", [])}
                   | {"Town Hall", "Hero Hall", "Dragon", "Dark Barracks", "Spell Factory", "Barbarian King"})
    errors = checks = 0
    for rel, info in manifest.items():
        if not rel.startswith("coc_"): continue   # the pre-update UI had no panel
        frame = load_frame(FRAMES / rel)
        panel = info.get("panel")
        state = (P.is_open(frame), P.active_tab(frame), P.dialog_open(frame))
        want = (panel is not None, panel["tab"] if panel else None, bool(info.get("dialog")))
        checks += 1
        if state != want:
            errors += 1
            print(f"XX {rel}: open/tab/dialog {state}, expected {want}")
        for i, (row, truth) in enumerate(zip(P.rows(frame), (panel or {}).get("rows", []))):
            checks += 1
            matched = [] if row["new"] else [n for n in names if P.matches(row, n, frame)]
            got = (row["affordable"], row["new"], matched)
            exp = (truth["affordable"], truth["new"], [] if truth["new"] else [truth["name"]])
            if got != exp:
                errors += 1
                print(f"XX {rel} row {i} ({truth['name']}): got {got}, expected {exp}")
        if panel and "rows" in panel and len(P.rows(frame)) != len(panel["rows"]):
            errors += 1
            print(f"XX {rel}: {len(P.rows(frame))} rows parsed, expected {len(panel['rows'])}")
        if "storage" in info:
            use_frame(frame)
            levels = utils.get_storage_fill_levels()
            for res, want_level in info["storage"].items():
                checks += 1
                if abs(levels[res] - want_level) > 0.02:
                    errors += 1
                    print(f"XX {rel}: {res} storage {levels[res]:.3f} full, expected {want_level}")
    print(f"panel checks: {checks - errors}/{checks} ok")
    return errors == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
