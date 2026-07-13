"""Redline detection lab — self-contained pipeline, reference for _get_red_area().

Usage: python scripts/redline_lab.py <frame.png> <out_prefix>

Approach (validated on La Cantera 2026-07-10, see memory redline-pipeline-state):
plate-color segmentation + rectilinear contour fit in iso (u,v) space; dashes are
used only to cut misclassified strips and to snap final segment positions.
u = x + 2y, v = x - 2y;  x = (u+v)/2, y = (u-v)/4;  1 tile ~ 27 u/v units.
"""
import sys
import cv2
import numpy as np

FRAME = sys.argv[1] if len(sys.argv) > 1 else "debug/smart_attack_1_raw.png"
OUTP = sys.argv[2] if len(sys.argv) > 2 else "debug/redline_lab"

frame = cv2.imread(FRAME)
h, w = frame.shape[:2]

# ---------------- UI mask (normalized boxes) ----------------
X, Y = np.meshgrid(np.arange(w) / w, np.arange(h) / h)
ui = (X < 0.10) | (X > 0.87) | (Y < 0.05) | (Y > 0.82)
ui |= (Y < 0.11) & (X > 0.37) & (X < 0.63)               # battle-starts banner
ui |= (Y > 0.38) & (Y < 0.56) & (X > 0.30) & (X < 0.70)  # mid notification
ui |= (Y > 0.70) & (X < 0.16)                            # End Battle
ui |= (Y > 0.74) & (X < 0.50)                            # boost banners
ui |= (Y > 0.63) & (X > 0.72)                            # Next button

# ---------------- thin red (dashes; roofs removed) ----------------
b_, g_, r_ = [c.astype(np.int16) for c in cv2.split(frame)]
rawred = (r_ > g_ + 45) & (r_ > b_ + 45) & (r_ > 90)
red8 = rawred.astype(np.uint8) * 255
core = cv2.dilate(cv2.erode(red8, np.ones((5, 5), np.uint8)), np.ones((13, 13), np.uint8))
thin = rawred & (core == 0) & ~ui

# ---------------- dash chains: iso closing + long-component filter ----------------
def line_kernel(length, slope_sign):
    kh = length // 2 + 1
    k = np.zeros((kh, length), np.uint8)
    for i in range(length):
        y = i // 2
        k[y if slope_sign > 0 else kh - 1 - y, i] = 1
    return k

thin8 = thin.astype(np.uint8) * 255
closed = cv2.morphologyEx(thin8, cv2.MORPH_CLOSE, line_kernel(29, +1))
closed = cv2.morphologyEx(closed, cv2.MORPH_CLOSE, line_kernel(29, -1))
ncc, lbl, stats, _ = cv2.connectedComponentsWithStats(closed)
keep = np.zeros(ncc, bool)
for i in range(1, ncc):
    ww, hh, area = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT], stats[i, cv2.CC_STAT_AREA]
    diag = np.hypot(ww, hh)
    fill = area / max(ww * hh, 1)
    if diag >= 220 and fill <= 0.35:
        keep[i] = True
chain = thin & keep[lbl]

# ---------------- bootstrap prior diamond from dash percentiles ----------------
cys, cxs = np.where(chain if chain.sum() > 3000 else thin)
uu_ = cxs + 2 * cys
vv_ = cxs - 2 * cys
u1, u2 = np.percentile(uu_, [2, 98])
v1, v2 = np.percentile(vv_, [2, 98])

def uv2xy(u, v):
    return (int(round((u + v) / 2)), int(round((u - v) / 4)))

poly0 = np.array([uv2xy(u1, v1), uv2xy(u1, v2), uv2xy(u2, v2), uv2xy(u2, v1)], np.int32)
inside0 = np.zeros((h, w), np.uint8)
cv2.fillPoly(inside0, [poly0], 255)

# ---------------- LDA plate-vs-grass classification ----------------
lab = cv2.cvtColor(frame, cv2.COLOR_BGR2Lab).astype(np.float32)
hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.float32)
F = np.dstack([lab, hsv[:, :, 0:2]]).reshape(-1, 5)
inner = (cv2.erode(inside0, np.ones((61, 61), np.uint8)) > 0) & ~ui
outer = (cv2.dilate(inside0, np.ones((61, 61), np.uint8)) == 0) & ~ui
H_, S_, V_ = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
grassy = (H_ > 25) & (H_ < 55) & (S_ > 60) & (V_ > 70)
Xi = F[(inner & grassy).ravel()]
Xo = F[(outer & grassy).ravel()]
mi, mo = Xi.mean(0), Xo.mean(0)
cov = (np.cov(Xi.T) * len(Xi) + np.cov(Xo.T) * len(Xo)) / (len(Xi) + len(Xo))
wv = np.linalg.solve(cov + np.eye(5) * 1e-3, mi - mo)
score = (F @ wv).reshape(h, w)
thr = 0.5 * ((mi @ wv) + (mo @ wv))
cls = np.full((h, w), 2, np.uint8)          # 0 out, 1 plate, 2 unknown
cls[(score > thr) & grassy & ~ui] = 1
cls[(score <= thr) & grassy & ~ui] = 0

# ---------------- plate ring, band-restricted ----------------
plate = ((cls == 1).astype(np.uint8)) * 255
plate = cv2.morphologyEx(plate, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
plate = cv2.morphologyEx(plate, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
band = cv2.dilate(inside0, np.ones((121, 121), np.uint8)) > 0
plate[~band] = 0
ncc, lbl, stats, _ = cv2.connectedComponentsWithStats(plate)
keep = np.zeros(ncc, bool)
keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= 1500
plate = keep[lbl]

# filler: prior interior, minus outside-classified areas (preserves real notches)
filler = cv2.erode(inside0, np.ones((121, 121), np.uint8))
outm = cv2.morphologyEx(((cls == 0).astype(np.uint8)) * 255, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
outm = cv2.dilate(outm, np.ones((5, 5), np.uint8))
filler[outm > 0] = 0
region_scr = plate | (filler > 0)

# ---------------- rasterize to (u,v) grid ----------------
ST = 4
ys, xs = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
U = xs + 2 * ys
V = xs - 2 * ys
U0, V0 = int(U.min()), int(V.min())
GU = (int(U.max()) - U0) // ST + 1
GV = (int(V.max()) - V0) // ST + 1
gu = ((U - U0) // ST).ravel()
gv = ((V - V0) // ST).ravel()
Rcnt = np.zeros((GU, GV), np.float32)
Tot = np.zeros((GU, GV), np.float32)
Ucnt = np.zeros((GU, GV), np.float32)
np.add.at(Rcnt, (gu, gv), region_scr.ravel().astype(np.float32))
np.add.at(Tot, (gu, gv), 1)
np.add.at(Ucnt, (gu, gv), ui.ravel().astype(np.float32))
valid = Tot > 0
R = np.zeros((GU, GV), np.uint8)
R[valid & (Rcnt / np.maximum(Tot, 1) > 0.5)] = 255
UIg = valid & (Ucnt / np.maximum(Tot, 1) > 0.4)

# UI-occlusion completion: big rect close applied only inside UI zone
UIz = cv2.dilate(UIg.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
big = cv2.morphologyEx(R, cv2.MORPH_CLOSE, np.ones((90, 90), np.uint8))
R2 = R.copy()
R2[UIz & (big > 0)] = 255
R2 = cv2.morphologyEx(R2, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
ncc, lbl, stats, _ = cv2.connectedComponentsWithStats(R2)
best = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
R2 = ((lbl == best) * 255).astype(np.uint8)

# ---------------- cuts along strict contrast-validated dash segments ----------------
pys, pxs = np.where(chain)
pu = (pxs + 2 * pys).astype(np.float64)
pv = (pxs - 2 * pys).astype(np.float64)

def extract(cc, oo, width=3, gap=35, min_span=35, min_dens=0.6):
    segs = []
    used = np.zeros(len(cc), bool)
    lo, hi = int(cc.min()), int(cc.max())
    def build_hist():
        hh = np.zeros(hi - lo + 3)
        for val in cc[~used]:
            hh[int(val) - lo] += 1
        return np.convolve(hh, np.ones(2 * width + 1), "same")
    sm = build_hist()
    tried = np.zeros(len(sm), bool)
    while True:
        idx = int(np.argmax(np.where(tried, -1, sm)))
        if sm[idx] < 30 or tried[idx]:
            break
        tried[idx] = True
        c0 = idx + lo
        seli = np.where((~used) & (np.abs(cc - c0) <= width))[0]
        if len(seli) < 20:
            continue
        srt = seli[np.argsort(oo[seli])]
        ov = oo[srt]
        cut = np.where(np.diff(ov) > gap)[0]
        starts = np.concatenate([[0], cut + 1])
        ends = np.concatenate([cut, [len(ov) - 1]])
        for s, e in zip(starts, ends):
            span = ov[e] - ov[s]
            n = e - s + 1
            if span >= min_span and n / max(span, 1) >= min_dens:
                run = srt[s:e + 1]
                segs.append((float(np.median(cc[run])), float(ov[s]), float(ov[e])))
                used[run] = True
        sm = build_hist()
    return segs

def strict_boundary(axis, c, a, b):
    ts = np.arange(a, b, 6.0)
    fr = []
    for sign in (+1, -1):
        out = pl = 0
        for d in range(8, 28, 4):
            if axis == 0:
                qu = np.full_like(ts, c + sign * d); qv = ts
            else:
                qu = ts; qv = np.full_like(ts, c + sign * d)
            xq = ((qu + qv) / 2).astype(int)
            yq = ((qu - qv) / 4).astype(int)
            m = (xq >= 0) & (xq < w) & (yq >= 0) & (yq < h)
            ccl = cls[yq[m], xq[m]]
            out += (ccl == 0).sum(); pl += (ccl == 1).sum()
        t = out + pl
        fr.append(out / t if t > 10 else np.nan)
    f1, f2 = fr
    if np.isnan(f1) or np.isnan(f2):
        return False
    return (f1 >= 0.7 and f2 <= 0.3) or (f2 >= 0.7 and f1 <= 0.3)

cutm = np.zeros_like(R2)
ncut = 0
if len(pu) > 100:
    for axis, (cc, oo) in ((0, (pu, pv)), (1, (pv, pu))):
        for c, a, b in extract(cc, oo):
            if b - a >= 40 and strict_boundary(axis, c, a, b):
                ncut += 1
                if axis == 0:
                    g1 = (int(c) - U0) // ST
                    o1, o2 = (int(a) - V0) // ST, (int(b) - V0) // ST
                    cutm[max(g1 - 1, 0):g1 + 2, max(o1, 0):o2 + 1] = 255
                else:
                    g1 = (int(c) - V0) // ST
                    o1, o2 = (int(a) - U0) // ST, (int(b) - U0) // ST
                    cutm[max(o1, 0):o2 + 1, max(g1 - 1, 0):g1 + 2] = 255
R2[cutm > 0] = 0
ncc, lbl, stats, _ = cv2.connectedComponentsWithStats(R2)
best = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
R2 = ((lbl == best) * 255).astype(np.uint8)

# neck-cut (false outward bulges): erode + geodesic reconstruct
seed = cv2.erode(R2, np.ones((13, 13), np.uint8))
prev = np.zeros_like(seed)
cur = seed
k3 = np.ones((3, 3), np.uint8)
while not np.array_equal(cur, prev):
    prev = cur
    cur = cv2.bitwise_and(cv2.dilate(cur, k3), R2)
R2 = cur
ncc, lbl, stats, _ = cv2.connectedComponentsWithStats(R2)
best = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
R2 = ((lbl == best) * 255).astype(np.uint8)
R2 = cv2.morphologyEx(R2, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))  # fill bites
inv = cv2.bitwise_not(R2)
nb, lb = cv2.connectedComponents(inv)
bl = set(lb[0, :]) | set(lb[-1, :]) | set(lb[:, 0]) | set(lb[:, -1])
R2[np.isin(lb, list(set(range(nb)) - bl))] = 255                        # fill holes

# ---------------- contour -> rectilinear segments ----------------
cont, _ = cv2.findContours(R2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
cont = max(cont, key=cv2.contourArea)[:, 0, :]           # (gv, gu) order
approx = cv2.approxPolyDP(cont.reshape(-1, 1, 2), 2.5, True)[:, 0, :].astype(float)

segs = []
N = len(approx)
for i in range(N):
    p, q = approx[i], approx[(i + 1) % N]
    d = q - p
    if abs(d[0]) >= abs(d[1]):
        segs.append(["H", (p[1] + q[1]) / 2, p[0], q[0]])   # gu const, spans gv
    else:
        segs.append(["V", (p[0] + q[0]) / 2, p[1], q[1]])   # gv const, spans gu

def merge_consec(segs):
    out = []
    for s in segs:
        if out and out[-1][0] == s[0]:
            m = out[-1]
            l1, l2 = abs(m[3] - m[2]), abs(s[3] - s[2])
            m[1] = (m[1] * l1 + s[1] * l2) / max(l1 + l2, 1e-9)
            m[3] = s[3]
        else:
            out.append(list(s))
    if len(out) > 1 and out[0][0] == out[-1][0]:
        a = out.pop()
        m = out[0]
        l1, l2 = abs(m[3] - m[2]), abs(a[3] - a[2])
        m[1] = (m[1] * l1 + a[1] * l2) / max(l1 + l2, 1e-9)
        m[2] = a[2]
    return out

segs = merge_consec(segs)

MINLEN = 6
def absorb(segs):
    while len(segs) > 4:
        lens = [abs(s[3] - s[2]) for s in segs]
        k = int(np.argmin(lens))
        if lens[k] >= MINLEN:
            break
        M = len(segs)
        p, nx = segs[(k - 1) % M], segs[(k + 1) % M]
        if p[0] == nx[0]:
            l1, l2 = abs(p[3] - p[2]), abs(nx[3] - nx[2])
            p[1] = (p[1] * l1 + nx[1] * l2) / max(l1 + l2, 1e-9)
            p[3] = nx[3]
            for i in sorted([k, (k + 1) % M], reverse=True):
                del segs[i]
        else:
            del segs[k]
            segs[:] = merge_consec(segs)
    return segs

def merge_close(segs):
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(segs) and len(segs) > 4:
            j = (i + 1) % len(segs)
            if i != j and segs[i][0] == segs[j][0] and abs(segs[i][1] - segs[j][1]) <= 1.5:
                l1, l2 = abs(segs[i][3] - segs[i][2]), abs(segs[j][3] - segs[j][2])
                segs[i][1] = (segs[i][1] * l1 + segs[j][1] * l2) / max(l1 + l2, 1e-9)
                segs[i][3] = segs[j][3]
                del segs[j]
                changed = True
            else:
                i += 1
    return segs

segs = absorb(segs)

# ---------------- snap to thin dashes (two passes) ----------------
D = np.zeros((GU, GV), np.float32)
tys, txs = np.where(thin)
np.add.at(D, ((txs + 2 * tys - U0) // ST, (txs - 2 * tys - V0) // ST), 1)
Db = cv2.dilate((D > 0).astype(np.float32), np.ones((3, 3), np.uint8))

def snap(segs, rng=8, thresh=0.22):
    n = 0
    for s in segs:
        lo, hi = int(min(s[2], s[3])), int(max(s[2], s[3]))
        span = max(hi - lo + 1, 1)
        if span < 6:
            continue
        bd, bs = 0, -1.0
        for d in range(-rng, rng + 1):
            cg = int(round(s[1])) + d
            if s[0] == "H":
                if not (0 <= cg < GU):
                    continue
                sup = Db[cg, lo:hi + 1].sum()
            else:
                if not (0 <= cg < GV):
                    continue
                sup = Db[lo:hi + 1, cg].sum()
            sup -= 0.05 * abs(d)
            if sup > bs:
                bs, bd = sup, d
        if bs >= thresh * span and bd != 0:
            s[1] = round(s[1]) + bd
            n += 1
    return n

snap(segs)
segs = merge_close(segs)
segs = absorb(segs)
snap(segs)
segs = merge_close(segs)
segs = absorb(segs)

# ---------------- remove unsupported occlusion boxes ----------------
def seg_support(s):
    lo, hi = int(min(s[2], s[3])), int(max(s[2], s[3]))
    span = max(hi - lo + 1, 1)
    cg = int(round(s[1]))
    if s[0] == "H":
        return (Db[cg, lo:hi + 1].sum() / span, span) if 0 <= cg < GU else (0.0, span)
    return (Db[lo:hi + 1, cg].sum() / span, span) if 0 <= cg < GV else (0.0, span)

def seg_ui_frac(s):
    ts = np.linspace(s[2], s[3], 12)
    if s[0] == "H":
        qu = np.full_like(ts, s[1] * ST + U0); qv = ts * ST + V0
    else:
        qv = np.full_like(ts, s[1] * ST + V0); qu = ts * ST + U0
    xq = np.clip(((qu + qv) / 2).astype(int), 0, w - 1)
    yq = np.clip(((qu - qv) / 4).astype(int), 0, h - 1)
    return ui[yq, xq].mean()

changed, iters = True, 0
while changed and iters < 60:
    iters += 1
    changed = False
    M = len(segs)
    good = [len(s) > 4 or seg_support(s)[0] >= 0.35 or seg_ui_frac(s) > 0.35 for s in segs]
    if all(good):
        break
    i = 0
    while i < M:
        if good[i]:
            i += 1
            continue
        j = i
        while j + 1 < M and not good[j + 1]:
            j += 1
        tot = sum(abs(s[3] - s[2]) for s in segs[i:j + 1])
        pi, ni = (i - 1) % M, (j + 1) % M
        if tot <= 70 and pi != ni and good[pi] and good[ni]:
            P, Nx = segs[pi], segs[ni]
            if P[0] == Nx[0] and abs(P[1] - Nx[1]) <= 5:
                l1, l2 = abs(P[3] - P[2]), abs(Nx[3] - Nx[2])
                P[1] = (P[1] * l1 + Nx[1] * l2) / max(l1 + l2, 1e-9)
                P[3] = Nx[3]
                for k in sorted(set(list(range(i, j + 1)) + [ni]), reverse=True):
                    if k != pi:
                        del segs[k]
            elif P[0] != Nx[0]:
                for k in range(j, i - 1, -1):
                    del segs[k]
            else:
                jmid = 0.5 * (P[3] + Nx[2])
                other = "V" if P[0] == "H" else "H"
                segs[i:j + 1] = [[other, jmid, P[1], Nx[1], True]]
                P[3] = jmid
                segs[(i + 1) % len(segs)][2] = jmid
            changed = True
            break
        i = j + 1

segs = merge_close(segs)
segs = absorb(segs)

# ---------------- corners -> screen polygon ----------------
corners = []
M = len(segs)
for i in range(M):
    s1, s2 = segs[i], segs[(i + 1) % M]
    if s1[0] == s2[0]:
        continue
    if s1[0] == "H":
        cg_u, cg_v = s1[1], s2[1]
    else:
        cg_u, cg_v = s2[1], s1[1]
    corners.append(uv2xy(cg_u * ST + U0 + ST / 2, cg_v * ST + V0 + ST / 2))
poly = np.array(corners, np.int32)
np.save(f"{OUTP}_poly.npy", poly)

# ---------------- audit + renders ----------------
distt = cv2.distanceTransform(1 - thin.astype(np.uint8), cv2.DIST_L2, 3)
nbad = 0
for i in range(len(poly)):
    p, q = poly[i], poly[(i + 1) % len(poly)]
    L = int(np.hypot(*(q - p)))
    if L < 4:
        continue
    ts = np.linspace(0, 1, max(L // 4, 3))
    pts = (p[None, :] * (1 - ts[:, None]) + q[None, :] * ts[:, None]).astype(int)
    pts[:, 0] = np.clip(pts[:, 0], 0, w - 1)
    pts[:, 1] = np.clip(pts[:, 1], 0, h - 1)
    med = float(np.median(distt[pts[:, 1], pts[:, 0]]))
    if med > 6 and ui[pts[:, 1], pts[:, 0]].mean() < 0.4:
        nbad += 1
print(f"corners: {len(poly)}  cuts: {ncut}  off-dash non-UI edges: {nbad}")

vis = frame.copy()
ov = frame.copy()
cv2.fillPoly(ov, [poly], (0, 0, 255))
vis = cv2.addWeighted(ov, 0.12, vis, 0.88, 0)
cv2.polylines(vis, [poly], True, (0, 0, 255), 3)
cv2.imwrite(f"{OUTP}_trace.png", vis)
vis2 = frame.copy()
vis2[thin] = (0, 255, 0)
cv2.polylines(vis2, [poly], True, (255, 0, 0), 2)
cv2.imwrite(f"{OUTP}_vs_dash.png", vis2)
print("saved", f"{OUTP}_trace.png")
