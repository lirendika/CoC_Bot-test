"""Download CoC home-village building sprites from clashofclans.fandom.com.

Usage: python scripts/download_wiki_buildings.py
Saves to assets/wiki_buildings/<Building>/<File>.png
"""
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://clashofclans.fandom.com/api.php"
OUT = Path(__file__).resolve().parent.parent / "assets" / "wiki_buildings"
HEADERS = {"User-Agent": "CoC-Bot-research/1.0 (personal use; contact: rencyclonus@gmail.com)"}

BUILDINGS = [
    "Cannon", "Archer Tower", "Mortar", "Air Defense", "Wizard Tower",
    "Air Sweeper", "Hidden Tesla", "Bomb Tower", "X-Bow", "Inferno Tower",
    "Eagle Artillery", "Scattershot", "Spell Tower", "Monolith",
    "Ricochet Cannon", "Multi-Archer Tower", "Firespitter",
    "Town Hall", "Clan Castle", "Army Camp", "Barracks", "Dark Barracks",
    "Laboratory", "Spell Factory", "Dark Spell Factory", "Workshop",
    "Pet House", "Blacksmith", "Hero Hall",
    "Gold Mine", "Elixir Collector", "Dark Elixir Drill",
    "Gold Storage", "Elixir Storage", "Dark Elixir Storage",
    "Builder's Hut", "Wall",
]


def api(params):
    params = dict(params, format="json")
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def page_image_titles(page):
    titles, cont = [], {}
    while True:
        res = api({"action": "query", "titles": page, "prop": "images",
                   "imlimit": "500", **cont})
        for p in res["query"]["pages"].values():
            for im in p.get("images", []):
                titles.append(im["title"])
        if "continue" in res:
            cont = {"imcontinue": res["continue"]["imcontinue"]}
        else:
            return titles


# pages whose sprite files use a different naming pattern
SPECIAL_PATTERNS = {
    "X-Bow": r"^File:X-Bow\d+ (Ground|Air)\.png$",
    "Inferno Tower": r"^File:Inferno Tower\d+ (Single|Multi)\.png$",
    "Spell Tower": r"^File:Spell Tower\d+ [A-Za-z]+\.png$",
    "Builder's Hut": r"^File:Builders? Hut\d+( Active)?\.png$",
}


def sprite_filter(page, titles):
    # keep e.g. "File:Cannon12.png", "File:Town Hall17.png"; skip Builder Base
    # (B), ruins, seasonal (C), old "pre ..." versions
    if page in SPECIAL_PATTERNS:
        pat = re.compile(SPECIAL_PATTERNS[page], re.IGNORECASE)
    else:
        pat = re.compile(rf"^File:{re.escape(page)}\d+\.png$", re.IGNORECASE)
    return [t for t in titles if pat.match(t)]


def file_urls(file_titles):
    urls = {}
    for i in range(0, len(file_titles), 50):
        batch = file_titles[i:i + 50]
        res = api({"action": "query", "titles": "|".join(batch),
                   "prop": "imageinfo", "iiprop": "url"})
        for p in res["query"]["pages"].values():
            info = p.get("imageinfo")
            if info:
                urls[p["title"]] = info[0]["url"]
        time.sleep(0.3)
    return urls


def main():
    total = 0
    for page in BUILDINGS:
        try:
            titles = page_image_titles(page)
        except Exception as e:
            print(f"!! {page}: {e}")
            continue
        wanted = sprite_filter(page, titles)
        if not wanted:
            print(f"-- {page}: no sprites matched")
            continue
        urls = file_urls(wanted)
        outdir = OUT / page.replace("'", "").replace(" ", "_")
        outdir.mkdir(parents=True, exist_ok=True)
        got = 0
        for title, url in sorted(urls.items()):
            name = title.split(":", 1)[1].replace(" ", "_")
            dest = outdir / name
            if dest.exists():
                got += 1
                continue
            try:
                req = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=60) as r:
                    dest.write_bytes(r.read())
                got += 1
                time.sleep(0.2)
            except Exception as e:
                print(f"  ! {name}: {e}")
        total += got
        print(f"ok {page}: {got}/{len(wanted)} sprites")
    print("TOTAL files:", total)


if __name__ == "__main__":
    main()
