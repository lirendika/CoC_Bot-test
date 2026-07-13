"""Redline via LONG straight iso lines only (user-specified logic).

Rules (from user):
- only long straight dash lines count; short broken fragments (walls, deco) are ignored
- the redline is one unbroken closed loop
- slopes are always the same two iso directions; corners are always 90 deg (in iso space)

Usage: python scripts/redline_lines.py <frame.png> <out_prefix>
"""
import sys
import cv2
import numpy as np

FRAME = sys.argv[1] if len(sys.argv) > 1 else "debug/smart_attack_1_raw.png"
OUTP = sys.argv[2] if len(sys.argv) > 2 else "debug/redline_lines"

SLOPE = 0.75        # measured screen slope of the redline (NOT 0.5!)
MIN_SPAN = 120      # v/u units along the line (~80 px in x): "garis panjang" only
MIN_DENS = 0.40     # px per unit along the line
GAP = 45            # dash gap tolerance inside one line
WIDTH = 4           # half-thickness tolerance around the line constant

frame = cv2.imread(FRAME)
h, w = frame.shape[:2]

# ---------- UI mask ----------
Xn, Yn = np.meshgrid(np.arange(w) / w, np.arange(h) / h)
ui = (Xn < 0.10) | (Xn > 0.87) | (Yn < 0.05) | (Yn > 0.82)
ui |= (Yn < 0.11) & (Xn > 0.37) & (Xn < 0.63)
ui |= (Yn > 0.38) & (Yn < 0.56) & (Xn > 0.30) & (Xn < 0.70)
ui |= (Yn > 0.70) & (Xn < 0.16)
ui |= (Yn > 0.74) & (Xn < 0.50)
ui |= (Yn > 0.63) & (Xn > 0.72)

# ---------- base footprint (scenery-independent, via edge density) ----------
# Buildings/walls have dense high-frequency edges; grass and even candy/paint
# scenery are relatively smooth. The base is the central high-edge-density blob.
# Its (u,v) extent gates out far scenery red lines (rainbow fields, paint, etc.)
# that would otherwise be picked as "outermost".
gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
edge = (cv2.magnitude(gx, gy) > 100).astype(np.float32)
dens = cv2.blur(edge, (35, 35))
bm = (dens > 0.42).astype(np.uint8)
bm[: int(0.05 * h)] = 0
bm[int(0.85 * h):] = 0
bm = cv2.morphologyEx(bm, cv2.MORPH_OPEN, np.ones((21, 21), np.uint8))
nb, blab, bstats, _ = cv2.connectedComponentsWithStats(bm, 8)
if nb > 1:
    cc = blab[h // 2, w // 2]
    if cc == 0:
        cc = 1 + int(np.argmax(bstats[1:, 4]))
    bm = (blab == cc).astype(np.uint8)

# ---------- thin dash-colored pixels ----------
b_, g_, r_ = [c.astype(np.int16) for c in cv2.split(frame)]
# the line is 1-2px, semi-transparent, blended with the ground; detect as
# LOCALLY redder than the median background (works even on red-brick scenery
# where global red-excess floods), plus global red-excess for grass
med = cv2.medianBlur(frame, 15).astype(np.int16)
db_, dg_, dr_ = (frame.astype(np.int16) - med)[..., 0], (frame.astype(np.int16) - med)[..., 1], (frame.astype(np.int16) - med)[..., 2]
loc = (dr_ - np.maximum(dg_, db_) >= 10)
glob = (r_ - np.maximum(g_, b_) >= 25) & (r_ >= 80)
redm = loc & glob
red8 = redm.astype(np.uint8) * 255
core = cv2.dilate(cv2.erode(red8, np.ones((5, 5), np.uint8)), np.ones((13, 13), np.uint8))
thin = redm & (core == 0) & ~ui

ys, xs = np.where(thin)
# iso coords for slope-±SLOPE lines: u-const lines have screen slope -SLOPE,
# v-const lines +SLOPE. Inverse: x=(u+v)/(2*SLOPE), y=(u-v)/2
u = (SLOPE * xs + ys).astype(np.float64)
v = (SLOPE * xs - ys).astype(np.float64)

def to_xy(uu, vv):
    return int(round((uu + vv) / (2 * SLOPE))), int(round((uu - vv) / 2))

# base extent in (u,v); the redline sits just outside this
bys, bxs = np.where(bm > 0)
bu = SLOPE * bxs + bys
bv = SLOPE * bxs - bys
U0, U1 = np.percentile(bu, [2, 98])
V0, V1 = np.percentile(bv, [2, 98])
MARGIN = 95  # u/v units the redline may sit outside the detected base (~3 tiles)

# ---------- extract LONG straight iso segments ----------
def extract(cc, oo):
    segs = []
    used = np.zeros(len(cc), bool)
    lo, hi = int(cc.min()), int(cc.max())
    def hist():
        hh = np.zeros(hi - lo + 3)
        np.add.at(hh, (cc[~used] - lo).astype(int), 1)
        return np.convolve(hh, np.ones(2 * WIDTH + 1), "same")
    sm = hist()
    tried = np.zeros(len(sm), bool)
    while True:
        idx = int(np.argmax(np.where(tried, -1, sm)))
        if sm[idx] < MIN_SPAN * MIN_DENS * 0.5 or tried[idx]:
            break
        tried[idx] = True
        c0 = idx + lo
        seli = np.where((~used) & (np.abs(cc - c0) <= WIDTH))[0]
        if len(seli) < MIN_SPAN * MIN_DENS * 0.5:
            continue
        srt = seli[np.argsort(oo[seli])]
        ov = oo[srt]
        cuts = np.where(np.diff(ov) > GAP)[0]
        starts = np.concatenate([[0], cuts + 1])
        ends = np.concatenate([cuts, [len(ov) - 1]])
        for s, e in zip(starts, ends):
            span = ov[e] - ov[s]
            n = e - s + 1
            if span >= MIN_SPAN and n / max(span, 1) >= MIN_DENS:
                run = srt[s:e + 1]
                segs.append([float(np.median(cc[run])), float(ov[s]), float(ov[e]), int(n)])
                used[run] = True
        sm = hist()
    return segs

useg = extract(u, v)   # u-const lines: [u0, v_a, v_b, n]
vseg = extract(v, u)   # v-const lines: [v0, u_a, u_b, n]
print(f"long lines: u-const {len(useg)}, v-const {len(vseg)}")

# ---------- merge collinear pieces of the same line ----------
def merge(segs, tol_c=6, tol_gap=140):
    segs = sorted(segs, key=lambda s: (s[0], s[1]))
    out = []
    for s in segs:
        if out and abs(out[-1][0] - s[0]) <= tol_c and s[1] - out[-1][2] <= tol_gap:
            m = out[-1]
            m[0] = (m[0] * m[3] + s[0] * s[3]) / (m[3] + s[3])
            m[2] = max(m[2], s[2])
            m[3] += s[3]
        else:
            out.append(list(s))
    return out

useg = merge(useg)
vseg = merge(vseg)

# ---------- gate to the base collar: drop far-scenery lines ----------
# A u-const line is base-related only if its u is within the base u-extent
# (+MARGIN outward) AND its v-span overlaps the base v-extent (+MARGIN).
def gate(segs, C0, C1, O0, O1):
    out = []
    for c0, a, b, n in segs:
        if not (C0 - MARGIN <= c0 <= C1 + MARGIN):
            continue
        if min(b, O1 + MARGIN) - max(a, O0 - MARGIN) < 0:
            continue
        out.append([c0, a, b, n])
    return out

useg = gate(useg, U0, U1, V0, V1)   # u-const: const=u, span in v
vseg = gate(vseg, V0, V1, U0, U1)   # v-const: const=v, span in u
print(f"base-gated: u-const {len(useg)}, v-const {len(vseg)}")

# ---------- keep only OUTERMOST line per side (walls are interior) ----------
allmidu = [s[0] for s in useg] + [(s[1] + s[2]) / 2 for s in vseg]
allmidv = [(s[1] + s[2]) / 2 for s in useg] + [s[0] for s in vseg]
cu, cvv = np.median(allmidu), np.median(allmidv)

def outermost(segs, center):
    # for overlapping ranges on the same side of center, keep the farther line
    kept = []
    for s in segs:
        drop = False
        for t in segs:
            if t is s:
                continue
            ov = min(s[2], t[2]) - max(s[1], t[1])
            if ov < 0.5 * (s[2] - s[1]):
                continue
            same_side = (s[0] - center) * (t[0] - center) > 0
            if same_side and abs(t[0] - center) > abs(s[0] - center) + 8:
                drop = True
                break
        if not drop:
            kept.append(s)
    return kept

useg = outermost(useg, cu)
vseg = outermost(vseg, cvv)
print(f"outermost: u-const {len(useg)}, v-const {len(vseg)}")

# ---------- assemble closed loop: sort by angle, 90-deg corners ----------
items = []
for u0, a, b, n in useg:
    items.append(["U", u0, a, b])
for v0, a, b, n in vseg:
    items.append(["V", v0, a, b])

def midang(s):
    mu = s[1] if s[0] == "U" else (s[2] + s[3]) / 2
    mv = (s[2] + s[3]) / 2 if s[0] == "U" else s[1]
    return np.arctan2(mv - cvv, mu - cu)

items.sort(key=midang)

corners_uv = []
M = len(items)
for i in range(M):
    s1, s2 = items[i], items[(i + 1) % M]
    if s1[0] != s2[0]:
        uu = s1[1] if s1[0] == "U" else s2[1]
        vv = s2[1] if s1[0] == "U" else s1[1]
        corners_uv.append((uu, vv))
    else:
        # same orientation: insert a 90-deg jump midway between their facing ends
        if s1[0] == "U":
            vj = 0.5 * (s1[3] + s2[2]) if s1[3] < s2[2] else 0.5 * (s1[2] + s2[3])
            corners_uv.append((s1[1], vj))
            corners_uv.append((s2[1], vj))
        else:
            uj = 0.5 * (s1[3] + s2[2]) if s1[3] < s2[2] else 0.5 * (s1[2] + s2[3])
            corners_uv.append((uj, s1[1]))
            corners_uv.append((uj, s2[1]))

# clamp corners to the base collar so a stray line can't spike into the UI/scenery
CLAMP = 70
corners_uv = [(float(np.clip(uu, U0 - CLAMP, U1 + CLAMP)),
               float(np.clip(vv, V0 - CLAMP, V1 + CLAMP))) for uu, vv in corners_uv]

poly = np.array([to_xy(uu, vv) for uu, vv in corners_uv], np.int32)
np.save(f"{OUTP}_poly.npy", poly)
print("corners:", len(poly))

# ---------- render ----------
vis = frame.copy()
vis[thin] = (0, 255, 0)
for typ, c0, a, b in items:
    if typ == "U":
        p1, p2 = to_xy(c0, a), to_xy(c0, b)
    else:
        p1, p2 = to_xy(a, c0), to_xy(b, c0)
    cv2.line(vis, p1, p2, (0, 200, 255), 2)
cv2.polylines(vis, [poly], True, (255, 0, 0), 2)
cv2.imwrite(f"{OUTP}_vs_dash.png", vis)

vis2 = frame.copy()
ov = frame.copy()
cv2.fillPoly(ov, [poly], (0, 0, 255))
vis2 = cv2.addWeighted(ov, 0.12, vis2, 0.88, 0)
cv2.polylines(vis2, [poly], True, (0, 0, 255), 3)
cv2.imwrite(f"{OUTP}_trace.png", vis2)
print("saved", f"{OUTP}_trace.png")
