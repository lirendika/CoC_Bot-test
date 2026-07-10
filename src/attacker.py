from utils import *
import configs
from configs import *

class Attacker:
    def __init__(self):
        self.assets = Asset_Manager.attacker_assets
        self.misc_assets = Asset_Manager.misc_assets
    
    # ============================================================
    # 📱 Screen Interaction
    # ============================================================
    
    def _click_okay(self, timeout=5):
        return click_with_timeout(
            lambda: Frame_Handler.locate(self.assets["okay"], thresh=0.9),
            timeout=timeout,
        )
    
    def _click_surrender(self, timeout=5):
        return click_with_timeout(
            lambda: Frame_Handler.locate(self.assets["surrender"], thresh=0.9),
            timeout=timeout
        )
    
    def _click_end_battle(self, timeout=5):
        return click_with_timeout(
            lambda: Frame_Handler.locate(self.assets["end_battle"], thresh=0.9),
            timeout=timeout
        )
    
    def _click_return_home(self, timeout=5):
        return click_with_timeout(
            lambda: Frame_Handler.locate(self.assets["return_home"], thresh=0.9),
            timeout=timeout
        )

    def wait_battle_end(self, timeout=300, poll=2):
        """
        Wait for the battle to finish naturally, then click "Return Home" —
        force-closing CoC to skip the battle triggers CoC's attack cooldown.
        Also clicks the x1 speed-up button when it appears (last 1 minute).
        """
        import time, cv2, numpy as np

        start = time.time()
        clicked_speedup = False
        while time.time() - start < timeout:
            Frame_Handler.get_frame()
            # "Return Home" appears on the battle result screen
            x, y = Frame_Handler.locate(self.assets["return_home"], thresh=0.85, use_cached=True)
            if x is not None and y is not None:
                Input_Handler.click(x, y)
                time.sleep(3)
                return True
            # Dismiss intermediate popups (e.g. star bonus / achievements)
            x, y = Frame_Handler.locate(self.assets["okay"], thresh=0.9, use_cached=True)
            if x is not None and y is not None:
                Input_Handler.click(x, y)
            # Click the big green "1x" speed-up button (right edge, mid-screen,
            # appears when <1 minute remains) so the battle finishes at 4x
            if not clicked_speedup:
                try:
                    frame = Frame_Handler.get_frame(grayscale=False, use_cached=True)
                    fh, fw = frame.shape[:2]
                    y0, x0 = int(fh * 0.48), int(fw * 0.90)
                    sec = frame[y0:int(fh * 0.68), x0:]
                    r, g, b = sec[..., 0].astype(int), sec[..., 1].astype(int), sec[..., 2].astype(int)
                    green = (g > 150) & (g > r + 60) & (g > b + 60)
                    if green.sum() > 2500:
                        ys, xs = np.nonzero(green)
                        Input_Handler.click((x0 + xs.mean()) / fw, (y0 + ys.mean()) / fh)
                        clicked_speedup = True
                        print("⏩ Clicked 1x speed-up button → 4x")
                except (KeyboardInterrupt, SystemExit): raise
                except: pass
            time.sleep(poll * np.random.uniform(0.7, 1.6))
        return False

    def start_normal_attack(self, timeout=60):
        import time
        
        # Click attack
        Input_Handler.click(0.07, 0.9)
        
        # Find a match
        def locate_find_a_match():
            xys = Frame_Handler.locate(self.assets["find_a_match"], thresh=0.9, return_all=True)
            if len(xys) == 0: return None, None
            xys = sorted(xys, key=lambda xy: xy[0])
            x, y = xys[0]
            if x > 0.5: return None, None
            return x, y
        if not click_with_timeout(
            locate_find_a_match,
            timeout=5
        ):
            # Close whatever opened (attack screen / "army not ready" popup)
            # so the bot isn't left blind on a non-village screen
            Input_Handler.click_exit(2, 0.3)
            return False

        # Confirm attack
        if not click_with_timeout(
            lambda: Frame_Handler.locate(self.assets["confirm_attack"], thresh=0.9),
            timeout=5
        ):
            Input_Handler.click_exit(2, 0.3)
            return False

        # Wait until "end battle" button is found
        start_time = time.time()
        while time.time() - start_time < timeout:
            x, y = Frame_Handler.locate(self.assets["end_battle"], thresh=0.9)
            if x is not None and y is not None: return True
            time.sleep(0.1)
        Input_Handler.click_exit(2, 0.3)
        return False
    
    def start_builder_attack(self, timeout=60):
        import time
        
        # Click attack
        Input_Handler.click(0.07, 0.9)
        
        # Find a match
        if not click_with_timeout(
            lambda: Frame_Handler.locate(self.assets["find_now"], thresh=0.9),
            timeout=5
        ):
            Input_Handler.click_exit(2, 0.3)
            return False

        # Wait until "battle starts in" text is found
        start_time = time.time()
        while time.time() - start_time < timeout:
            section = Frame_Handler.get_frame_section(0, 0, 1, 0.1, grayscale=True, high_contrast=True, thresh=150)
            x, y = Frame_Handler.locate(self.assets["battle_starts_in"], section, thresh=0.9)
            if x is not None and y is not None: return True
            time.sleep(0.1)
        Input_Handler.click_exit(2, 0.3)
        return False
    
    @staticmethod
    def _card_pairing_valid(peaks_norm, cw_rng=(0.055, 0.08), gap_rng=(0.003, 0.025)):
        # A valid troop bar parse alternates card-width and gap distances
        # (after trimming partially visible cards at either end)
        import numpy as np
        dists = np.diff(peaks_norm)
        if len(dists) == 0: return False
        is_cw = (dists >= cw_rng[0]) & (dists <= cw_rng[1])
        if not is_cw.any(): return False
        left = np.argmax(is_cw)
        right = len(dists) - 1 - np.argmax(is_cw[::-1])
        seg = dists[left:right + 1]
        if len(seg) % 2 == 0: return False
        for i, d in enumerate(seg):
            lo, hi = cw_rng if i % 2 == 0 else gap_rng
            if not (lo <= d <= hi): return False
        return True

    @classmethod
    def _repair_card_edges(cls, peaks_norm, cw=0.068):
        """
        The two edges between adjacent cards sit only ~13px apart and sometimes
        merge into a single Sobel peak, leaving an odd number of edges and
        breaking the pairwise parse. A span of ~(card width + gap) between
        consecutive peaks marks a lost edge — try reinserting one card-width
        after the left peak of each suspect span and keep the first candidate
        that yields a globally consistent alternating structure.
        """
        import itertools, numpy as np
        if cls._card_pairing_valid(peaks_norm): return peaks_norm
        dists = np.diff(peaks_norm)
        suspects = [i for i, d in enumerate(dists) if cw + 0.003 <= d <= cw + 0.025]
        for k in range(1, min(len(suspects), 3) + 1):
            for combo in itertools.combinations(suspects, k):
                cand = list(peaks_norm)
                for i in sorted(combo, reverse=True):
                    cand.insert(i + 1, peaks_norm[i] + cw)
                cand = np.array(cand)
                if cls._card_pairing_valid(cand): return cand
        return peaks_norm

    def detect_troop_positions(self, frame, clip_left=0.0, clip_right=1.0, type_gaps_seen=0, return_boundaries=False, return_types=False, return_counts=False):
        import cv2, scipy, numpy as np
        
        # Look for vertical card edges
        assert len(frame.shape) == 3 and frame.shape[2] == 3
        frame_color = frame.copy()
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        orig_h, orig_w = frame_gray.shape
        frame_color = frame_color[:, max(0, int(orig_w*clip_left)-10):min(orig_w, int(orig_w*clip_right)+10)]
        frame_gray = frame_gray[:, max(0, int(orig_w*clip_left)-10):min(orig_w, int(orig_w*clip_right)+10)]
        frame_gray_raw = frame_gray.copy() # un-equalized copy for reading card counts
        frame_gray = cv2.equalizeHist(frame_gray)
        edges = cv2.convertScaleAbs(np.abs(cv2.Sobel(frame_gray, cv2.CV_64F, 1, 0, ksize=3)))
        profile = np.sum(edges, axis=0)
        profile = (profile - profile.min()) / (profile.max() - profile.min())
        peaks = scipy.signal.find_peaks(profile, height=0.8, distance=10)[0]
        peaks_norm =  peaks / orig_w + clip_left

        # Reinsert card edges that merged into a single peak
        peaks_norm = self._repair_card_edges(peaks_norm)
        peaks = ((peaks_norm - clip_left) * orig_w).astype(int)

        # Compute distances between edges and discretize
        dists = np.diff(peaks_norm)
        dist_categories = np.array([0.007, 0.015, 0.068]) # normal gap, type change gap, card width
        tol = 0.01
        diffs = np.abs(dists[:, None] - dist_categories)
        closest_idx = np.argmin(diffs, axis=1)
        closest_dist = diffs[np.arange(len(dists)), closest_idx]
        dists_discrete = dist_categories[closest_idx]
        dists_discrete[closest_dist > tol] = np.nan
        
        # Remove partially visible card edges
        remove_left = 0
        remove_right = len(dists_discrete) - 1
        while dists_discrete[remove_left] != dist_categories[2]: remove_left += 1
        while dists_discrete[remove_right] != dist_categories[2]: remove_right -= 1
        peaks = peaks[remove_left:remove_right+2]
        peaks_norm = peaks_norm[remove_left:remove_right+2]
        dists_discrete = dists_discrete[remove_left:remove_right+1]
        
        assert len(peaks) % 2 == 0, "Uneven number of troop slot edges detected"
        
        # Convert edge distances to card locations
        card_types = []
        card_centers = []
        card_boundaries = []
        card_counts = []
        for i in range(0, len(peaks_norm), 2):
            x = (peaks_norm[i] + peaks_norm[i+1]) / 2
            card_centers.append(x)
            card_boundaries.extend([peaks_norm[i], peaks_norm[i+1]])
            prev_gap = dists_discrete[i-1] if i-1 > 0 else dist_categories[0]
            next_gap = dists_discrete[i+1] if i+1 < len(dists_discrete) else dist_categories[0]
            if prev_gap == dist_categories[1]: type_gaps_seen += 1
            
            # Figure out whether card is a normal troop, clan troop, or hero
            card_section = frame_color[:, peaks[i]:peaks[i+1]]
            card_section_gray = frame_gray[:, peaks[i]:peaks[i+1]]
            h, w = card_section_gray.shape[:2]
            card_texture = cv2.Canny(card_section_gray, 50, 150) / 255
            x_asset = render_text("x", "SupercellMagic", 25)
            x_h, x_w = x_asset.shape[:2]
            x_sign_loc = Frame_Handler.locate(x_asset, card_section_gray, grayscale=True, thresh=0.75, ref="lc")
            if x_sign_loc[0] is not None and x_sign_loc[1] is not None: # Only troops, clan troops, or spells have multiplicity
                # Read the multi-digit count from the raw (un-equalized) grayscale,
                # binarized so the white digits match cleanly on any background.
                # Extend a few px past the card's right edge in case a repaired
                # edge sits slightly short and would clip the last digit.
                row_end = int(h*x_sign_loc[1]+0.5*x_h)+1
                col_start = peaks[i] + int(w*x_sign_loc[0]) + x_w - 1
                count_section = frame_gray_raw[:row_end, col_start:min(peaks[i+1] + 8, frame_gray_raw.shape[1])]
                count_section = ((count_section >= 220) * 255).astype(np.uint8)
                digit_assets = []
                for d in range(10):
                    t = Frame_Handler.grayscale(render_text(str(d), "SupercellMagic", 25))
                    digit_assets.append(((t >= 128) * 255).astype(np.uint8))
                digit_locs = Frame_Handler.batch_locate(digit_assets, frame=count_section, grayscale=True, thresh=0.72, ref="lc", return_confidence=True, return_all=True)
                found = []
                for d, locs in enumerate(digit_locs):
                    for loc in locs: found.append((loc[0], loc[2], d))
                found.sort()
                # Cluster overlapping hits by x (keep the most confident), compose left-to-right
                digit_w = 0.5 * x_w / max(count_section.shape[1], 1)
                digits = []
                for x_d, conf, d in found:
                    if digits and x_d - digits[-1][0] < digit_w:
                        if conf > digits[-1][1]: digits[-1] = (x_d, conf, d)
                    else:
                        digits.append((x_d, conf, d))
                count = int("".join(str(d) for _, _, d in digits)) if digits else 1
                
                # Clan troops either have a clan badge rather than a smooth background
                # or will have wider card edge gaps compared to typical troops
                if max(card_texture[int(h*x_sign_loc[1])-10:int(h*x_sign_loc[1])+10, :int(w*x_sign_loc[0]-1)].mean(1)) > 0.1:
                    card_type = "clan"
                    card_counts.append(1)
                elif prev_gap == dist_categories[1] and next_gap == dist_categories[1]:
                    card_type = "clan"
                    card_counts.append(1)
                elif type_gaps_seen > 0:
                    card_type = "spell"
                    card_counts.append(count)
                else:
                    card_type = "troop"
                    card_counts.append(count)
            else:
                card_section_border = card_section.copy()
                card_section_border[int(h*0.1):int(h*0.9), int(w*0.1):int(w*0.9)] = 0
                mask = filter_color((68, 202, 222), card_section_border, tol=100, return_mask=True)[1]
                blue_pct = mask.mean()
                # Seige machine doesn't have multiplicity anymore
                if blue_pct > 0.1:
                    card_type = "clan"
                    card_counts.append(1)
                else:
                    card_type = "hero"
                    card_counts.append(1)
            card_types.append(card_type)

        card_centers = np.array(card_centers)
        
        if not return_boundaries and not return_types: return card_centers
        
        output = [card_centers]
        if return_boundaries: output.append(card_boundaries)
        if return_types: output.append(card_types)
        if return_counts: output.append(card_counts)
        output.append(type_gaps_seen)
        return output
    
    # ============================================================
    # 🧠 Smart Attack Analysis (ported from MyBot.run/ClashAttack)
    # ============================================================

    SIDES = ["TL", "TR", "BL", "BR"]
    VILLAGE_CENTER = (0.5, 0.45)

    def _side_of_point(self, x, y):
        # Ported from MyBot.run SmartFarm.au3 → Side(): screen-half quadrant split
        cx, cy = self.VILLAGE_CENTER
        if x <= cx: return "TL" if y <= cy else "BL"
        return "TR" if y <= cy else "BR"

    def _get_red_area(self, min_points=800):
        """
        Detect the red no-deploy border drawn by the game while a troop card
        is selected. Ported from MyBot.run _GetRedArea() + getRedAreaSideBuilding().

        Returns:
            dict side -> Nx2 array of normalized (x, y) redline points sorted
            along the edge direction, or None per side if not enough points.
            Returns None entirely if no redline is visible.
        """
        import cv2, numpy as np

        self._last_redline_poly = None  # cleared so a failed detection doesn't draw stale data
        frame = Frame_Handler.get_frame(grayscale=False)
        h, w = frame.shape[:2]

        # The redline is a thin red-orange line that pops with strong CONTRAST
        # against the ground. Detect it by relative channel dominance (red far
        # above green and blue) instead of a fixed HSV window — absolute hue
        # shifts with scenery lighting, contrast does not.
        R = frame[..., 0].astype(np.int16)
        G = frame[..., 1].astype(np.int16)
        B = frame[..., 2].astype(np.int16)
        mask = (R > G + 45) & (R > B + 45) & (R > 90)

        # Ignore UI margins. Kept tight so the corners of large bases are not
        # clipped — only the actual UI areas are blocked.
        mask[:, :int(w * 0.10)] = False
        mask[:, int(w * 0.87):] = False
        mask[:int(h * 0.05), :] = False
        mask[int(h * 0.82):, :] = False
        # "Battle starts in" banner (top center) — kept tight so tall bases'
        # top corner isn't clipped
        mask[:int(h * 0.11), int(w * 0.37):int(w * 0.63)] = False
        # Red notification banners (e.g. "Not enough housing space") pop up
        # mid-screen and would poison the redline points. Keep this strip as
        # tight as the banner itself — small centered bases have their whole
        # redline near the middle and an oversized mask would erase it.
        mask[int(h * 0.38):int(h * 0.56), int(w * 0.30):int(w * 0.70)] = False
        # End Battle button (bottom-left, above troop bar) — solid red blob
        mask[int(h * 0.70):, :int(w * 0.16)] = False
        # Army/Heroes Boosted banners (red potion icons, bottom strip)
        mask[int(h * 0.74):, :int(w * 0.50)] = False

        mask_u8 = mask.astype(np.uint8) * 255

        # === Thinness filter ===
        # The redline is always a ~2-3px thin line. Anything with a thick core
        # (gold storages, dirt paths, orange roofs, wall stripes) is not it.
        core = cv2.erode(mask_u8, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
        thick = cv2.dilate(core, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)))
        mask_u8 = cv2.bitwise_and(mask_u8, cv2.bitwise_not(thick))

        # === Continuity filter ===
        # The line runs along the isometric grid (screen slope ±0.5) with small
        # gaps. Bridge the gaps with a directional closing, then require a long
        # continuous run — small orange decorations don't survive this.
        def _line_kernel(length, slope_sign):
            kl = np.zeros((length // 2 + 3, length), np.uint8)
            mid = kl.shape[0] // 2
            for i in range(length):
                r = mid + slope_sign * (i - length // 2) // 2
                if 0 <= r < kl.shape[0]: kl[r, i] = 1
            return kl
        kp, kn = _line_kernel(11, 1), _line_kernel(11, -1)
        kp_l, kn_l = _line_kernel(21, 1), _line_kernel(21, -1)
        c1 = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, kp)
        c2 = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, kn)
        band = cv2.bitwise_or(cv2.morphologyEx(c1, cv2.MORPH_OPEN, kp_l),
                              cv2.morphologyEx(c2, cv2.MORPH_OPEN, kn_l))
        band = cv2.dilate(band, np.ones((5, 5), np.uint8))
        mask_u8 = cv2.bitwise_and(mask_u8, band)

        ys, xs = np.nonzero(mask_u8)
        if len(xs) < min_points: return None

        # === Isometric staircase envelope ===
        # The redline always runs along the isometric tile grid: straight
        # segments at screen slope ±0.5. Rotate into grid coordinates
        # u = x + 2y, v = x - 2y — there the no-deploy zone becomes a
        # rectilinear (axis-aligned staircase) region, so its boundary maps
        # back to perfectly straight isometric lines on screen.
        u = xs + 2.0 * ys
        v = xs - 2.0 * ys

        N_BINS = 36
        TRIM = 5  # absolute pixel trim (not percentile — interior red is dense)
        u_edges = np.linspace(u.min(), u.max() + 1e-6, N_BINS + 1)
        vmax = np.full(N_BINS, np.nan)
        vmin = np.full(N_BINS, np.nan)
        for b in range(N_BINS):
            sel = (u >= u_edges[b]) & (u < u_edges[b + 1])
            if sel.sum() < 2 * TRIM + 5: continue
            vb = np.sort(v[sel])
            # Nth-outermost pixel: robust to a few stray pixels but not diluted
            # by the mass of interior red (wall stripes) the way a percentile is
            vmax[b] = vb[-TRIM]
            vmin[b] = vb[TRIM - 1]

        if (~np.isnan(vmax)).sum() < 8:
            return None

        # Median filter across bins kills bumps caused by red decorations
        # sitting outside the redline
        def _medfilt(a, k=5):
            out = a.copy()
            r = k // 2
            for i in range(len(a)):
                vals = a[max(0, i - r):i + r + 1]
                vals = vals[~np.isnan(vals)]
                if len(vals) >= 2: out[i] = np.median(vals)
            return out
        vmax = _medfilt(vmax)
        vmin = _medfilt(vmin)

        # Drop bins where the chains (nearly) cross — garbage data
        bad = ~np.isnan(vmax) & ~np.isnan(vmin) & (vmax - vmin < 40)
        vmax[bad] = np.nan
        vmin[bad] = np.nan

        valid_idx = np.where(~np.isnan(vmax) & ~np.isnan(vmin))[0]
        if len(valid_idx) < 8: return None
        first, last = valid_idx[0], valid_idx[-1]
        # OUTWARD-biased gap fill: where the line is locally missing (masked
        # UI, occluding buildings) never cut inward — take the outermost of
        # the flanking valid bins instead of interpolating across.
        for i in range(len(valid_idx) - 1):
            a, b2 = valid_idx[i], valid_idx[i + 1]
            if b2 - a > 1:
                vmax[a + 1:b2] = max(vmax[a], vmax[b2])
                vmin[a + 1:b2] = min(vmin[a], vmin[b2])

        # Local dip guard: narrow inward valleys in a chain are detection
        # failures (line hidden behind the banner or tall buildings), not real
        # base shape — lift them to the neighbours' level via grey closing.
        # Global thresholds would wrongly clip the diamond's corners.
        def _running(a, k, fn):
            r = k // 2
            out = a.copy()
            for i in range(len(a)):
                out[i] = fn(a[max(0, i - r):i + r + 1])
            return out
        sl = slice(first, last + 1)
        vm = vmax[sl].copy()
        closed = _running(_running(vm, 7, np.max), 7, np.min)
        vm[vm < closed - 80] = closed[vm < closed - 80]
        vmax[sl] = vm
        vn = vmin[sl].copy()
        opened = _running(_running(vn, 7, np.min), 7, np.max)
        vn[vn > opened + 80] = opened[vn > opened + 80]
        vmin[sl] = vn

        # Merge adjacent bins that sit on the same line segment into plateaus,
        # then snap each plateau EXACTLY onto the line: median v of the actual
        # detected pixels near the estimate. This turns the wobbly per-bin
        # staircase into long straight segments lying on the real redline.
        def _plateaus(vals):
            groups = [[first]]
            for b in range(first + 1, last + 1):
                if abs(vals[b] - np.median([vals[x] for x in groups[-1]])) < 30:
                    groups[-1].append(b)
                else:
                    groups.append([b])
            out = []
            for g in groups:
                gmed = np.median([vals[x] for x in g])
                sel = (u >= u_edges[g[0]]) & (u < u_edges[g[-1] + 1]) & (np.abs(v - gmed) < 22)
                val = float(np.median(v[sel])) if sel.sum() >= 8 else float(gmed)
                out.append((u_edges[g[0]], u_edges[g[-1] + 1], val))
            return out

        top_chain = _plateaus(vmax)
        bot_chain = _plateaus(vmin)

        # Build the closed polygon: out along the upper (vmax) chain, back
        # along the lower (vmin) chain. Every segment is a straight isometric
        # line: constant v (screen slope +0.5) or constant u (slope -0.5).
        def _to_xy(uu, vv):
            return ((uu + vv) / 2.0 / w, (uu - vv) / 4.0 / h)

        poly = []
        for u0, u1, val in top_chain:
            poly.append(_to_xy(u0, val))
            poly.append(_to_xy(u1, val))
        for u0, u1, val in reversed(bot_chain):
            poly.append(_to_xy(u1, val))
            poly.append(_to_xy(u0, val))
        pts = np.array(poly)

        # Stash the ordered polygon for the debug overlay (side split below
        # loses the drawing order)
        self._last_redline_poly = pts

        cx, cy = self.VILLAGE_CENTER
        selectors = {
            "TL": (pts[:, 0] <= cx) & (pts[:, 1] <= cy),
            "TR": (pts[:, 0] > cx) & (pts[:, 1] <= cy),
            "BL": (pts[:, 0] <= cx) & (pts[:, 1] > cy),
            "BR": (pts[:, 0] > cx) & (pts[:, 1] > cy),
        }
        # Projection along each edge: TL/BR edges run along x-y, TR/BL along x+y
        sort_keys = {
            "TL": lambda p: p[:, 0] - p[:, 1],
            "TR": lambda p: p[:, 0] + p[:, 1],
            "BL": lambda p: p[:, 0] + p[:, 1],
            "BR": lambda p: p[:, 0] - p[:, 1],
        }
        red_area = {}
        for side in self.SIDES:
            side_pts = pts[selectors[side]]
            if len(side_pts) < 5:
                red_area[side] = None
                continue
            red_area[side] = side_pts[np.argsort(sort_keys[side](side_pts))]
        return red_area

    # HSV ranges (OpenCV scale) for gold and elixir colored pixels.
    # NOTE: grass texture sits at H 34-37 with similar S/V to gold, so the
    # gold hue range must stay below ~30 (real gold measures H 15-25).
    # Dirt paths share gold's hue but sit at S~155 vs real gold's S~200+
    RESOURCE_COLORS = {
        "gold": {"h": (10, 28), "s": 190, "v": 110},
        "elixir": {"h": (140, 168), "s": 90, "v": 130},
    }

    def _detect_resources(self, red_area=None, min_blob_area=300, inout_dist=0.05):
        """
        Detect gold/elixir resource buildings (collectors, mines, storages) by
        color blobs. Ported from MyBot.run SmartFarmDetection() — the original
        uses encrypted imgloc templates, so this uses color segmentation instead.

        Each resource is classified by screen side (TL/TR/BL/BR) and In/Out:
        "In" = far from the redline (deep inside the base), "Out" = near the
        deployable border (easy pickings), mirroring the REDLINEDISTANCE check.

        Returns:
            list of dicts: {"x", "y", "side", "type", "in"}
        """
        import cv2, numpy as np

        frame = Frame_Handler.get_frame(grayscale=False, use_cached=True)
        h, w = frame.shape[:2]
        hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
        H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]

        all_red = None
        if red_area:
            side_pts = [p for p in red_area.values() if p is not None]
            if side_pts: all_red = np.concatenate(side_pts)

        resources = []
        for res_type, c in self.RESOURCE_COLORS.items():
            mask = ((H >= c["h"][0]) & (H <= c["h"][1]) & (S >= c["s"]) & (V >= c["v"])).astype(np.uint8)

            # Ignore UI margins
            mask[:, :int(w * 0.12)] = 0
            mask[:, int(w * 0.85):] = 0
            mask[:int(h * 0.15), :] = 0
            mask[int(h * 0.80):, :] = 0

            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
            contours = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
            for cnt in contours:
                if cv2.contourArea(cnt) < min_blob_area: continue
                m = cv2.moments(cnt)
                if m["m00"] == 0: continue
                x, y = m["m10"] / m["m00"] / w, m["m01"] / m["m00"] / h

                # Skip anything outside the village diamond (trees, beach, decorations)
                if abs(x - 0.5) / 0.36 + abs(y - 0.43) / 0.33 > 1: continue

                # Skip double detections (ported from DoublePoint(), 18px ≈ 0.02)
                if any((r["x"] - x) ** 2 + (r["y"] - y) ** 2 < 0.02 ** 2 for r in resources): continue

                inside = True
                if all_red is not None:
                    dist = np.sqrt(((all_red - [x, y]) ** 2).sum(1)).min()
                    inside = dist > inout_dist

                resources.append({
                    "x": x, "y": y,
                    "side": self._side_of_point(x, y),
                    "type": res_type,
                    "in": inside,
                })
        return resources

    def _choose_attack_sides(self, resources):
        """
        Decide which side(s) to attack. Ported from MyBot.run ChkSmartFarm():
        - If most resources are deep inside the base, attack the single side
          holding the most of them (troops must funnel in from one direction).
        - Otherwise the loot is exposed near the border, so attack every side
          that holds a meaningful share of the resources.

        Returns:
            (attack_inside, sides, counts)
        """
        counts = {s: 0 for s in self.SIDES}
        n_in = 0
        for r in resources:
            counts[r["side"]] += 1
            if r["in"]: n_in += 1
        total = len(resources)
        pct_in = 100 * n_in / total
        pct_out = 100 - pct_in

        attack_inside = pct_in > SMART_ATTACK_INSIDE_PCT
        if attack_inside:
            sides = [max(counts, key=counts.get)]
        else:
            one_side = total // 4
            sides = [
                s for s in self.SIDES
                if counts[s] > 0 and (counts[s] >= one_side or pct_out > SMART_ATTACK_OUTSIDE_PCT)
            ]
            if not sides: sides = [max(counts, key=counts.get)]

        if SMART_ATTACK:
            print(f"🎯 Smart Attack: {total} resources ({n_in} in / {total - n_in} out), "
                  f"per side {counts} → attacking {'inside at' if attack_inside else 'outside at'} {sides}")
        return attack_inside, sides, counts

    # UI safe zone: deploy points must avoid End Battle (bottom-left),
    # Next button (bottom-right), resource text (top-right), troop bar
    DEPLOY_SAFE_X = (0.14, 0.84)
    DEPLOY_SAFE_Y = (0.15, 0.72)

    def _redline_deploy_points(self, side, red_area, num_points, offset=0.055):
        """
        Sample deploy points along the actual redline of a side, nudged outward
        so troops land just outside the no-deploy zone. Ported from MyBot.run
        GetPixelDropTroop() + GetVectorPixelOnEachSide(). Falls back to the
        fixed diamond edge if the redline wasn't detected on this side.
        """
        import numpy as np

        pts = red_area.get(side) if red_area else None
        if pts is None or len(pts) < 5:
            return self._get_deploy_points(side, num_points)

        cx, cy = self.VILLAGE_CENTER
        idxs = np.linspace(0, len(pts) - 1, num_points + 2)[1:-1].astype(int)
        points = []
        for i in idxs:
            x, y = pts[i]
            vx, vy = x - cx, y - cy
            norm = (vx ** 2 + vy ** 2) ** 0.5 or 1.0
            x += vx / norm * offset + np.random.uniform(-0.005, 0.005)
            y += vy / norm * offset + np.random.uniform(-0.005, 0.005)
            x = float(np.clip(x, self.DEPLOY_SAFE_X[0], self.DEPLOY_SAFE_X[1]))
            y = float(np.clip(y, self.DEPLOY_SAFE_Y[0], self.DEPLOY_SAFE_Y[1]))
            points.append((x, y))

        # If clamping collapsed the points into a pile (garbage redline data
        # pushed everything into a safe-zone corner), the samples are useless —
        # fall back to the fixed diamond edge instead
        spread = max(
            max(p[0] for p in points) - min(p[0] for p in points),
            max(p[1] for p in points) - min(p[1] for p in points),
        )
        if spread < 0.05:
            return self._get_deploy_points(side, num_points)
        return points

    _ai_backoff_time = 0

    def _ai_choose_sides(self):
        """
        Ask a Groq vision model which side(s) hold the most loot and the
        weakest defenses. Returns a list of sides (subset of TL/TR/BL/BR) or
        None on failure, in which case the caller falls back to the color-blob
        heuristic. Mirrors OCR_Handler's Groq + backoff pattern.
        """
        import time, json, cv2, base64

        if configs.GROQ_API_KEY == "": return None
        if time.time() < type(self)._ai_backoff_time: return None
        try:
            from groq import Groq

            frame = Frame_Handler.get_frame(grayscale=False, use_cached=True)
            h, w = frame.shape[:2]
            small = cv2.resize(frame, (w // 2, h // 2)) # smaller payload = faster
            buf = cv2.imencode(".jpg", cv2.cvtColor(small, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 80])[1]
            b64 = base64.b64encode(buf).decode("utf-8")

            prompt = (
                "This is a Clash of Clans attack-preparation screen: an enemy village in "
                "isometric (diamond) view. The village has 4 deployable edges:\n"
                "- TL = top-left edge, TR = top-right edge, BL = bottom-left edge, BR = bottom-right edge.\n"
                "Goal: farm resources. Find where the gold storages, elixir storages and "
                "collectors/mines are most concentrated, preferring the side that also has the "
                "fewest defenses (cannons, archer towers, mortars, wizard towers) near it.\n"
                'Respond with ONLY compact JSON: {"sides": ["TR"], "reason": "..."}. '
                "Use 1 side normally, or 2 sides only if loot is clearly split across two edges."
            )
            client = Groq(api_key=configs.GROQ_API_KEY, timeout=12, max_retries=0)
            resp = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ]}],
            )
            data = json.loads(resp.choices[0].message.content)
            sides = [s for s in data.get("sides", []) if s in self.SIDES]
            if not sides: return None
            if SMART_ATTACK: print(f"🤖 AI Attack: {sides} — {str(data.get('reason', ''))[:80]}")
            return sides[:2]
        except (KeyboardInterrupt, SystemExit): raise
        except Exception as e:
            type(self)._ai_backoff_time = time.time() + 600 # stop hammering a failing API for 10 min
            if configs.DEBUG: print("ai_choose_sides", e)
            return None

    def _smart_attack_analysis(self, red_area=None):
        """
        Full SmartFarm pipeline (assumes a troop card is currently selected so
        the redline is visible): detect redline → choose side(s) → build deploy
        points along the redline of each chosen side.

        Side selection uses the Groq vision model when AI Attack is enabled,
        otherwise (or on API failure) the color-blob loot heuristic.

        Returns:
            list of (x, y) deploy points, interleaved across chosen sides so
            each deployment wave rotates through all sides (like MyBot.run's
            per-side wave loop in LaunchTroopSmartFarm).
        """
        if red_area is None:
            red_area = self._get_red_area()
        resources = []

        # Prefer the AI's decision when enabled
        sides = None
        if not Task_Handler.ai_attack_excluded(use_cached=True):
            sides = self._ai_choose_sides()

        if sides is None:
            resources = self._detect_resources(red_area)
            if resources:
                attack_inside, sides, counts = self._choose_attack_sides(resources)
            else:
                # No resources detected: fall back to building-density heuristic
                best_side, scores = self._analyze_attack_side()
                sides = [best_side]

        points_per_side = [self._redline_deploy_points(s, red_area, DEPLOY_SPREAD_POINTS) for s in sides]
        deploy_points = []
        for group in zip(*points_per_side):
            deploy_points.extend(group)

        try: self._save_smart_attack_debug(red_area, resources, deploy_points)
        except (KeyboardInterrupt, SystemExit): raise
        except: pass

        return deploy_points

    _debug_attack_counter = 0

    def _save_smart_attack_debug(self, red_area, resources, deploy_points):
        import cv2, os, glob
        import numpy as np

        frame = Frame_Handler.get_frame(grayscale=False, use_cached=True).copy()
        h, w = frame.shape[:2]

        # Save the clean frame too — overlay drawings poison any later offline
        # analysis of the redline detection, so keep the raw pixels alongside
        Attacker._debug_attack_counter = (Attacker._debug_attack_counter % 5) + 1
        Frame_Handler.save_frame(frame.copy(), f"debug/smart_attack_{Attacker._debug_attack_counter}_raw.png")

        poly = getattr(self, "_last_redline_poly", None)
        if poly is not None and len(poly) > 4:
            cx, cy = self.VILLAGE_CENTER
            px_pts = np.stack([poly[:, 0] * w, poly[:, 1] * h], axis=1).astype(np.int32)
            # Semi-transparent red fill inside the boundary (no-deploy zone)
            overlay = frame.copy()
            cv2.fillPoly(overlay, [px_pts], (255, 40, 40))
            cv2.addWeighted(overlay, 0.20, frame, 0.80, 0, frame)
            # Thick red boundary following the isometric redline shape
            cv2.polylines(frame, [px_pts], isClosed=True, color=(255, 0, 0), thickness=3)
            cv2.putText(frame, "NO DEPLOY ZONE", (int(cx * w) - 100, int(cy * h) - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

        for r in resources:
            color = (255, 215, 0) if r["type"] == "gold" else (224, 64, 224)
            cv2.circle(frame, (int(r["x"] * w), int(r["y"] * h)), 10, color, 2)
            cv2.putText(frame, f"{r['side']}|{'In' if r['in'] else 'Out'}", (int(r["x"] * w) + 12, int(r["y"] * h)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        # Deploy points — green circles with white border for visibility
        for x, y in deploy_points:
            cv2.circle(frame, (int(x * w), int(y * h)), 7, (255, 255, 255), -1)
            cv2.circle(frame, (int(x * w), int(y * h)), 5, (0, 255, 0), -1)

        Frame_Handler.save_frame(frame, f"debug/smart_attack_{Attacker._debug_attack_counter}.png")

        # Remove old smart_attack.png (single-file legacy)
        legacy = os.path.join(os.path.dirname(os.path.dirname(__file__)), "debug", "smart_attack.png")
        if os.path.exists(legacy):
            os.remove(legacy)

    def _analyze_attack_side(self):
        """
        Analyze the battle screen to determine the best side to attack.
        Ported from MyBot.run SmartFarm.au3 → ChkSmartFarm() + Side().
        
        Divides the battlefield into 4 isometric quadrants (TL, TR, BL, BR),
        measures edge density (building concentration) in each, and returns
        the side with the highest density.
        
        Returns:
            str: Best side to attack ("TL", "TR", "BL", "BR")
            dict: Edge density scores for all 4 sides
        """
        import cv2, numpy as np
        
        # Capture the battle area (excluding troop bar at bottom)
        frame = Frame_Handler.get_frame_section(0.0, 0.0, 1.0, 0.82, grayscale=False)
        h, w = frame.shape[:2]
        
        # Convert to grayscale and detect edges (buildings appear as dense edges)
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        
        # Remove UI elements from edges to prevent them from skewing the density scores
        edges[:, :int(w * 0.12)] = 0         # Left margin (chat button, etc)
        edges[:, int(w * 0.85):] = 0         # Right margin (resources text, end battle)
        edges[:int(h * 0.15), :] = 0         # Top margin (name, stars)
        
        # CoC uses isometric perspective. The village center is roughly at (0.5, 0.45).
        # We split the screen into 4 triangles using the diagonals from the center.
        cx, cy = w // 2, int(h * 0.45)
        
        masks = {}
        for side in ["TL", "TR", "BL", "BR"]:
            mask = np.zeros((h, w), dtype=np.uint8)
            if side == "TL": # Left side
                pts = np.array([[cx, cy], [0, h], [0, 0]], np.int32)
            elif side == "TR": # Top side
                pts = np.array([[cx, cy], [0, 0], [w, 0]], np.int32)
            elif side == "BR": # Right side
                pts = np.array([[cx, cy], [w, 0], [w, h]], np.int32)
            elif side == "BL": # Bottom side
                pts = np.array([[cx, cy], [w, h], [0, h]], np.int32)
            cv2.fillPoly(mask, [pts], 255)
            masks[side] = mask
        
        # Calculate edge density for each quadrant
        scores = {}
        for side, mask in masks.items():
            masked_edges = cv2.bitwise_and(edges, edges, mask=mask)
            pixel_count = np.count_nonzero(mask)
            edge_count = np.count_nonzero(masked_edges)
            scores[side] = edge_count / max(pixel_count, 1)
        
        # Pick the side with highest building density
        best_side = max(scores, key=scores.get)
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Smart Attack Analysis - Scores: TL={scores['TL']:.4f}, TR={scores['TR']:.4f}, "
                    f"BL={scores['BL']:.4f}, BR={scores['BR']:.4f} → Best: {best_side}")
        if SMART_ATTACK: print(f"🎯 Smart Attack Analysis: Best side to attack is {best_side}!")
        
        return best_side, scores
    
    def _get_deploy_points(self, side, num_points=5):
        """
        Generate spread deploy coordinates along the chosen side edge.
        Ported from MyBot.run GetPixelDropTroop.au3 + GetVectorPixelOnEachSide.au3.
        
        In CoC's isometric view, the deployable edges are a diamond shape.
        Outer safe boundaries: Left(0.05, 0.45), Top(0.5, 0.15), Right(0.95, 0.45), Bottom(0.5, 0.75)
        
        Args:
            side: "TL", "TR", "BL", or "BR"
            num_points: Number of spread points to generate
            
        Returns:
            list of (x, y) tuples — normalized coordinates for troop deployment
        """
        import numpy as np
        
        # Define edge line endpoints for each side along the outer safe diamond.
        # We avoid the exact corners to prevent hitting UI buttons.
        edge_lines = {
            "TL": {"x": (0.14, 0.40), "y": (0.42, 0.22)},
            "TR": {"x": (0.60, 0.84), "y": (0.22, 0.42)},
            "BL": {"x": (0.14, 0.40), "y": (0.48, 0.68)},
            "BR": {"x": (0.60, 0.84), "y": (0.68, 0.48)},
        }
        
        edge = edge_lines[side]
        xs = np.linspace(edge["x"][0], edge["x"][1], num_points)
        ys = np.linspace(edge["y"][0], edge["y"][1], num_points)
        
        # Add slight random jitter to simulate human behavior (±0.01)
        xs += np.random.uniform(-0.01, 0.01, num_points)
        ys += np.random.uniform(-0.01, 0.01, num_points)
        
        xs = np.clip(xs, self.DEPLOY_SAFE_X[0], self.DEPLOY_SAFE_X[1])
        ys = np.clip(ys, self.DEPLOY_SAFE_Y[0], self.DEPLOY_SAFE_Y[1])
        
        return list(zip(xs.tolist(), ys.tolist()))
    
    # ============================================================
    # 🪖 Troop Deployment
    # ============================================================

    def _card_deployed(self, card_center):
        # A fully used card turns grayscale (R == G == B)
        import numpy as np
        section = Frame_Handler.get_frame_section(card_center-0.01, 0.89, card_center+0.01, 0.91, grayscale=False)
        return bool(np.all(section[:, :, 0] == section[:, :, 1]) and np.all(section[:, :, 1] == section[:, :, 2]))

    def deploy_troops(self, card_centers, available_slots=None, card_types=None, card_counts=None, deploy_points=None, slot_offset=0):
        """
        Deploy troops with wave-based multi-point spread.
        Ported from MyBot.run's LaunchTroopSmartFarm + DropOnPixel logic.
        
        When SMART_ATTACK is enabled and deploy_points are provided:
        - Troops are sorted into waves: tank → dps → hero/clan → spell
        - Each wave is spread across multiple deploy points
        - Spells are always dropped in the center of the village
        
        Args:
            card_centers: Array of card center x-positions on the troop bar
            available_slots: Which slots are available for deployment
            card_types: Type of each card ("troop", "hero", "clan", "spell")
            card_counts: Count for each card
            deploy_points: List of (x, y) tuples for spread deployment (from _get_deploy_points)
        """
        import time, numpy as np

        card_gray = self._card_deployed

        if available_slots is None: available_slots = [1] * len(card_centers)
        if card_types is None: card_types = [None] * len(card_centers)
        if card_counts is None: card_counts = [0] * len(card_centers)

        # If no smart deploy points provided, fall back to random edge point
        smart = deploy_points is not None
        if not smart:
            drop_x = float(np.random.choice([0.05, 0.95]))
            drop_y = float(np.random.uniform(0.3, 0.6))
            deploy_points = [(drop_x, drop_y)]
        
        # ======== Wave-based deployment (ported from MyBot.run) ========
        # Sort cards into deployment waves:
        #   Wave 1: Tanks (first troops in the list — usually tanky units)
        #   Wave 2: DPS troops (remaining troops)
        #   Wave 3: Heroes & Clan Castle
        #   Wave 4: Spells (always center of village)
        
        wave_tank = []    # Tank troop cards (front line)
        wave_dps = []     # Remaining troop cards
        wave_hero = []    # Heroes and Clan Castle troops
        wave_spell = []   # Spells
        wave_other = []   # Unknown types

        # Tanks lead: use the TANK_SLOTS config if set, otherwise assume the
        # troops with the smallest counts are tanks (expensive units come in
        # small numbers) and deploy troops in ascending-count order
        troop_idxs = [i for i in range(len(card_centers)) if available_slots[i] and card_types[i] == "troop"]
        if TANK_SLOTS:
            wave_tank = [i for i in troop_idxs if slot_offset + i in TANK_SLOTS]
            wave_dps = [i for i in troop_idxs if i not in wave_tank]
        else:
            order = sorted(troop_idxs, key=lambda i: card_counts[i] if (card_counts[i] or 0) > 0 else 999)
            wave_tank = order[:2] if len(order) > 2 else order[:1]
            wave_dps = [i for i in order if i not in wave_tank]

        for i in range(len(card_centers)):
            if not available_slots[i]: continue
            card_type = card_types[i]
            if card_type == "troop":
                continue
            elif card_type in ["hero", "clan"]:
                wave_hero.append(i)
            elif card_type == "spell":
                wave_spell.append(i)
            else:
                wave_other.append(i)
        
        # Use middle deploy point for heroes/CC (safest position)
        mid_point = deploy_points[len(deploy_points) // 2]
        
        def _dismiss_end_popup():
            """If we accidentally opened the End Battle/Surrender confirmation,
            dismiss it by tapping an empty area."""
            Frame_Handler.get_frame()
            for key in ("surrender", "end_battle"):
                sx, sy = Frame_Handler.locate(self.assets[key], thresh=0.85, use_cached=True)
                if sx is not None and sy is not None and sy < 0.7:
                    Input_Handler.click(0.5, 0.15)
                    time.sleep(0.5)
                    return True
            return False

        def _safe_xy(x, y):
            """Clamp deploy coordinates to the UI-safe zone."""
            return (
                float(np.clip(x, Attacker.DEPLOY_SAFE_X[0], Attacker.DEPLOY_SAFE_X[1])),
                float(np.clip(y, Attacker.DEPLOY_SAFE_Y[0], Attacker.DEPLOY_SAFE_Y[1])),
            )

        def _deploy_card(idx, x, y):
            """Deploy a single card at the given coordinates."""
            _dismiss_end_popup()
            x, y = _safe_xy(x, y)
            Input_Handler.click(card_centers[idx], 0.93)

            Input_Handler.down(x, y, pointer=1)

            if card_types[idx] in ["hero", "clan"]:
                Input_Handler.click(x, y)
            elif card_types[idx] == "troop":
                rx, ry = _safe_xy(
                    x + np.random.uniform(-0.02, 0.02),
                    y + np.random.uniform(-0.02, 0.02),
                )
                Input_Handler.down(rx, ry, pointer=0)
                end_time = time.monotonic() + TROOP_DEPLOY_TIME
                while time.monotonic() < end_time and not card_gray(card_centers[idx]): time.sleep(0.01)
                Input_Handler.up(pointer=0)
            elif card_types[idx] == "spell":
                n = card_counts[idx]
                rxs = np.random.uniform(0.35, 0.65, n)
                rys = np.random.uniform(0.40, 0.55, n)
                for coord in zip(rxs, rys):
                    Input_Handler.click(*coord)
            else:
                Input_Handler.click(x, y, n=max(0, card_counts[idx]))

            Input_Handler.up(pointer=1)
        
        # === Wave 1: Deploy tanks at 2-3 spread points (front line) ===
        if wave_tank:
            if smart: print("🌊 Wave 1: Deploying Tanks (Front Line)...")
            tank_points = deploy_points[:min(3, len(deploy_points))]
            for i, idx in enumerate(wave_tank):
                pt = tank_points[i % len(tank_points)]
                _deploy_card(idx, pt[0], pt[1])
            if smart: time.sleep(2.0)  # Delay so tanks can walk forward and draw fire
        
        # === Wave 2: Deploy DPS troops spread across all points ===
        if wave_dps:
            if smart: print("🌊 Wave 2: Deploying DPS Troops...")
            for i, idx in enumerate(wave_dps):
                pt = deploy_points[i % len(deploy_points)]
                _deploy_card(idx, pt[0], pt[1])
            if smart: time.sleep(1.5)  # Delay before other troops
        
        # === Wave 3: Deploy other/unknown types at spread points ===
        if wave_other:
            if smart: print("🌊 Wave 3: Deploying Other Troops...")
            for i, idx in enumerate(wave_other):
                pt = deploy_points[i % len(deploy_points)]
                _deploy_card(idx, pt[0], pt[1])
            if smart: time.sleep(1.0)
        
        # === Wave 4: Deploy heroes & clan castle at middle point ===
        if wave_hero:
            if smart: print("🌊 Wave 4: Deploying Heroes & Clan Castle...")
            for idx in wave_hero:
                _deploy_card(idx, mid_point[0], mid_point[1])
            if smart: time.sleep(1.0)
        
        # === Wave 5: Deploy spells in center of village ===
        if wave_spell:
            if smart: print("🌊 Wave 5: Deploying Spells...")
            for idx in wave_spell:
                _deploy_card(idx, 0.5, 0.5)  # center — spell deploy uses its own random spread internally
        
        # Unselect last card
        Input_Handler.click(0.5, 0.15)
    
    def complete_normal_attack(self, restart=True, exclude_clan_troops=False):
        import time, numpy as np

        # Skip poor bases before spending any troops
        self._find_worthy_target()

        Input_Handler.zoom(dir="out")

        # === Smart Attack: Analyze redline + resources and generate deploy points ===
        deploy_points = None
        smart_attack = not Task_Handler.smart_attack_excluded(use_cached=True)
        if smart_attack:
            try:
                # Select the first troop card so the game draws the red no-deploy
                # border. The redline only renders while a card is selected, so
                # verify it actually appeared and re-click if it didn't —
                # otherwise the analysis runs on garbage (random red decorations).
                frame = Frame_Handler.get_frame_section(0.0, 0.82, 1.0, 1.0, grayscale=False)
                card_centers = self.detect_troop_positions(frame)
                red_area = None
                for _ in range(3):
                    if len(card_centers) > 0:
                        Input_Handler.click(card_centers[0], 0.93)
                        time.sleep(0.8)
                    red_area = self._get_red_area()
                    if red_area is not None: break
                deploy_points = self._smart_attack_analysis(red_area=red_area)
                Input_Handler.click(0.5, 0.15) # unselect card
                time.sleep(0.5) # let the card deselect animation settle
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Smart attack analysis failed, using fallback: {e}")
                try:
                    best_side, scores = self._analyze_attack_side()
                    deploy_points = self._get_deploy_points(best_side, DEPLOY_SPREAD_POINTS)
                except (KeyboardInterrupt, SystemExit): raise
                except: deploy_points = None
        
        type_gaps_seen = 0
        total_slots_seen = 0
        last_card_left = 0.0
        
        while total_slots_seen < ATTACK_SLOT_RANGE[1] - ATTACK_SLOT_RANGE[0] + 1:
            frame = Frame_Handler.get_frame_section(0.0, 0.82, 1.0, 1.0, grayscale=False)
            # Find troops to deploy
            card_centers, card_boundaries, card_types, card_counts, type_gaps_seen = self.detect_troop_positions(frame, clip_left=last_card_left, type_gaps_seen=type_gaps_seen, return_boundaries=True, return_types=True, return_counts=True)
            
            if len(card_centers) == 0: break

            # Exclude clan troops if specified
            available_slots = np.ones_like(card_centers)
            if exclude_clan_troops:
                for i, card_type in enumerate(card_types):
                    if card_type == "clan": available_slots[i] = 0
            
            # Exclude troops outside of specified slot range
            available_slots[:max(0, ATTACK_SLOT_RANGE[0] - total_slots_seen)] = 0
            available_slots[max(0, ATTACK_SLOT_RANGE[1] + 1 - total_slots_seen):] = 0
            
            # Deploy troops up until the last one visible
            batch_offset = total_slots_seen
            total_slots_seen += len(card_centers) - 1
            self.deploy_troops(card_centers[:-1], available_slots[:-1], card_types[:-1], card_counts[:-1], deploy_points=deploy_points, slot_offset=batch_offset)
            # Scroll over and look for the new position of the last card
            last_card_frame = frame[:, int(card_boundaries[-2] * frame.shape[1]):int(card_boundaries[-1] * frame.shape[1])]
            Input_Handler.swipe_left(x1=min(card_centers[-1], 0.75), x2=0.15, y=0.93, hold_end_time=500)
            time.sleep(0.5)
            frame = Frame_Handler.get_frame_section(0.0, 0.82, 1.0, 1.0, grayscale=False)
            last_card_left = Frame_Handler.locate(last_card_frame, frame, thresh=0.9, grayscale=False, ref="lc")[0]
            # If the card didn't move then there are no more troops so it can be deployed
            if last_card_left is not None and abs(last_card_left - card_boundaries[-2]) < 0.01:
                self.deploy_troops(card_centers[-1:], available_slots[-1:], card_types[-1:], card_counts[-1:], deploy_points=deploy_points, slot_offset=total_slots_seen)
                break
            elif last_card_left is None:
                break

        # Dismiss end battle / surrender confirmation if it appeared
        Frame_Handler.get_frame()
        for key in ("surrender", "end_battle"):
            sx, sy = Frame_Handler.locate(self.assets[key], thresh=0.85, use_cached=True)
            if sx is not None and sy is not None and sy < 0.7:
                Input_Handler.click(0.5, 0.15)
                time.sleep(0.5)
                break

        try:
            time.sleep(0.5)
            frame = Frame_Handler.get_frame_section(0.0, 0.82, 1.0, 1.0, grayscale=False)
            card_centers, card_boundaries, card_types, card_counts, _ = self.detect_troop_positions(frame, return_boundaries=True, return_types=True, return_counts=True)
            leftover_slots = [0 if self._card_deployed(c) else 1 for c in card_centers]
            if exclude_clan_troops:
                for i, card_type in enumerate(card_types):
                    if card_type == "clan": leftover_slots[i] = 0
            if any(leftover_slots):
                if smart_attack: print(f"🧹 Deploying {int(sum(leftover_slots))} leftover card(s) at the outer edge...")
                self.deploy_troops(card_centers, leftover_slots, card_types, card_counts)
        except (KeyboardInterrupt, SystemExit): raise
        except Exception as e:
            if configs.DEBUG: print("leftover_deploy", e)

        # Wait for the battle to end naturally and return to the village
        # (fallback: restart CoC if the result screen never shows up)
        if not self.wait_battle_end():
            stop_coc()
            if restart: start_coc()

    def complete_builder_attack(self, restart=True):
        import numpy as np
        
        Input_Handler.zoom(dir="out")

        card_centers = np.linspace(0.1, 0.9, 11)
        self.deploy_troops(card_centers, card_counts=[4]*len(card_centers))

        # Wait for the versus battle to end naturally (opponent may still be
        # attacking) and return to the village; fallback: restart CoC
        if not self.wait_battle_end(timeout=360):
            stop_coc()
            if restart: start_coc()
    
    # ============================================================
    # 💰 Loot Filter (skip poor bases with Next)
    # ============================================================

    def _read_available_loot(self):
        """OCR the enemy's "Available Loot" panel (top-left of the battle
        screen). Returns {"gold": int, "elixir": int} or None on failure."""
        import re, cv2, numpy as np

        # One line per resource. The icon's white shine OCRs as a stray
        # leading "1", so blank the icon first — but its exact x varies, so
        # find it by color (gold=yellow, elixir=magenta) instead of position.
        icon_hues = {"gold": (20, 35, 150), "elixir": (140, 170, 100)}

        Frame_Handler.get_frame()
        loot = {}
        for name, y0, y1 in (("gold", 0.140, 0.185), ("elixir", 0.191, 0.236)):
            color = Frame_Handler.get_frame_section(0.02, y0, 0.20, y1, grayscale=False, use_cached=True)
            gray = Frame_Handler.grayscale(color)
            hc = ((gray >= 240) * 255).astype(np.uint8)

            h0, s0 = icon_hues[name][:2], icon_hues[name][2]
            hsv = cv2.cvtColor(color, cv2.COLOR_RGB2HSV)
            icon_mask = (hsv[..., 0] >= h0[0]) & (hsv[..., 0] <= h0[1]) & (hsv[..., 1] >= s0)
            cols = icon_mask.sum(axis=0)
            # The icon must sit in the left 30% of the strip
            search = cols[:int(len(cols) * 0.30)]
            icon_cols = np.nonzero(search > hc.shape[0] * 0.2)[0]
            if len(icon_cols) > 0:
                hc[:, :min(icon_cols.max() + 4, hc.shape[1])] = 0

            # Upscale + pad, otherwise the OCR drops narrow edge digits
            # (a leading "1" was consistently lost on 1M+ loot values)
            hc = cv2.resize(hc, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            hc = cv2.copyMakeBorder(hc, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=0)

            lines = OCR_Handler.get_text(hc)
            digits = re.sub(r"\D", "", fix_digits("".join(str(l) for l in lines).replace(" ", "")))
            if not digits: return None
            value = int(digits)
            # Sanity: implausible values mean a misread, not a real base
            if value < 100 or value > 3_000_000: return None
            loot[name] = value
        return loot

    def _find_worthy_target(self, max_nexts=10):
        """
        Keep clicking "Next" until the enemy's available loot meets the
        configured minimums (MIN_LOOT_GOLD / MIN_LOOT_ELIXIR). Attacks the
        current base if the loot can't be read or the search limit is hit.
        """
        import time, numpy as np

        min_gold = Task_Handler.setting("min_loot_gold", getattr(configs, "MIN_LOOT_GOLD", 0))
        min_elixir = Task_Handler.setting("min_loot_elixir", getattr(configs, "MIN_LOOT_ELIXIR", 0))
        if min_gold <= 0 and min_elixir <= 0: return

        for i in range(max_nexts):
            loot = None
            for _ in range(3):
                loot = self._read_available_loot()
                if loot is not None: break
                time.sleep(1.5)
            if loot is None:
                print("⚠️ Couldn't read available loot — attacking this base")
                return
            if loot["gold"] >= min_gold and loot["elixir"] >= min_elixir:
                print(f"💰 Target found: gold {loot['gold']:,} / elixir {loot['elixir']:,}")
                return
            print(f"⏭️ Loot too low (gold {loot['gold']:,} / elixir {loot['elixir']:,}) — Next ({i + 1}/{max_nexts})")
            Input_Handler.click(0.915, 0.72) # "Next" button (bottom-right)
            time.sleep(float(np.random.uniform(4.0, 6.5))) # cloud transition
        print("⚠️ Loot minimums never met — attacking the current base")

    # ============================================================
    # 💰 Storage Fullness Check
    # ============================================================

    def _storage_fill_levels(self):
        return get_storage_fill_levels()

    def _storages_full(self, thresh=0.90):
        """True when BOTH gold and elixir storages are (nearly) full —
        attacking would waste time since the loot can't be stored."""
        try:
            levels = self._storage_fill_levels()
            full = all(v >= thresh for v in levels.values())
            if full:
                print(f"💰 Storages full (gold {levels['gold']:.0%}, elixir {levels['elixir']:.0%}) — skipping attack")
            return full
        except (KeyboardInterrupt, SystemExit): raise
        except Exception as e:
            if configs.DEBUG: print("storages_full", e)
            return False

    # ============================================================
    # ⚔️ Attack Management
    # ============================================================

    @require_exit()
    def run_home_base(self, timeout=60, restart=True):
        import time
        
        try:
            # Make sure in home base
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    get_home_builders(1)
                    break
                except (KeyboardInterrupt, SystemExit): raise
                except: pass
            if time.time() - start_time >= timeout: return

            # No point farming when both storages are already full
            if self._storages_full(): return

            # Complete an attack
            if self.start_normal_attack(timeout):
                self.complete_normal_attack(restart=restart, exclude_clan_troops=EXCLUDE_CLAN_TROOPS)
        
        except Exception as e:
            if configs.DEBUG: print("attack_home_base", e)

    @require_exit()
    def run_builder_base(self, timeout=60, restart=True):
        import time
        
        try:
            # Make sure in builder base
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    get_builder_builders(1)
                    break
                except (KeyboardInterrupt, SystemExit): raise
                except: pass
            if time.time() - start_time >= timeout: return
            
            # Complete an attack
            if self.start_builder_attack(timeout):
                self.complete_builder_attack(restart=restart)
        
        except Exception as e:
            if configs.DEBUG: print("attack_builder_base", e)
