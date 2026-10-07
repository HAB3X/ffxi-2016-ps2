#!/usr/bin/env python3
"""make_logo.py: 'Seekers of Adoulin' strip (512x64) in the engraved-metal look of the installer's 'Wings of the Goddess' strip.
The new letters are drawn with a serif small-caps layout, then every pixel copies the colour of an original pixel at the same
row and the same distance from the letter edge (inside: bevel, cracks and shine; outside: the dark rim and glow)."""
import sys, numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
HERE = sys.path[0]
FONT = sys.argv[1] if len(sys.argv) > 1 else '/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf'
src = np.array(Image.open(HERE + '/../cdrom/wotg_strip.png').convert('RGBA')).astype(np.int32)
H, W = 64, 512
body_o = (src[:, :, 3] > 200) & (src[:, :, :3].max(axis=2) > 100)
din_o = ndimage.distance_transform_edt(body_o); dout_o = ndimage.distance_transform_edt(~body_o)
# new letters: big initials + small caps, baseline and heights matched to the original body (big ~y13-46, small ~y20-46)
big = ImageFont.truetype(FONT, 46); sm = ImageFont.truetype(FONT, 35)
words = [('S', 'EEKERS'), ('', 'OF'), ('A', 'DOULIN')]
m = Image.new('L', (W, H), 0); d = ImageDraw.Draw(m)
runs = []; x = 0; gap = 16; track = 1
for cap, rest in words:
    runs.append((x, cap, big)); x += d.textlength(cap, font=big) + track
    for ch in rest: runs.append((x, ch, sm)); x += d.textlength(ch, font=sm) + track
    x += gap
x -= gap; off = (W - x) / 2
for px, t, f in runs: d.text((off + px, 46), t, font=f, fill=255, anchor='ls')
ma = np.array(m); cols = np.where(ma.max(axis=0) > 0)[0]; x0, x1 = cols.min(), cols.max() + 1
target = 498; mw = Image.fromarray(ma[:, x0:x1]).resize((target, H), Image.LANCZOS)
m2 = Image.new('L', (W, H), 0); m2.paste(mw, ((W - target) // 2, 0))
body_n = ndimage.binary_dilation(np.array(m2) > 110, iterations=1)
din_n = ndimage.distance_transform_edt(body_n); dout_n = ndimage.distance_transform_edt(~body_n)
def pick(sel_mask, dist_o, y, dv, xn):
    for dy in (0, -1, 1, -2, 2, -3, 3):
        yy = y + dy
        if not 0 <= yy < H: continue
        for tol in (0.5, 1.0, 1.5):
            xs = np.where(sel_mask[yy] & (np.abs(dist_o[yy] - dv) <= tol))[0]
            if len(xs): return src[yy, xs[np.argmin(np.abs(xs - xn))]]
    return None
out = np.zeros((H, W, 4), np.int32)
rgb = src[:, :, :3].astype(np.float64)
blur = np.stack([ndimage.uniform_filter(rgb[:, :, k] * body_o, 5) / np.maximum(ndimage.uniform_filter(body_o.astype(float), 5), 1e-3) for k in range(3)], 2)
detail = (rgb - blur) * body_o[:, :, None]
maxin = int(din_o.max())
# mean body colour per (row, distance-from-edge)
mean = np.zeros((H, maxin + 2, 3)); cnt = np.zeros((H, maxin + 2))
for y in range(H):
    for x in range(W):
        if body_o[y, x]: k = int(round(din_o[y, x])); mean[y, k] += rgb[y, x]; cnt[y, k] += 1
for y in range(H):
    for k in range(maxin + 2):
        if cnt[y, k] == 0:   # borrow from neighbouring rows / distances
            for dy in (1, -1, 2, -2, 3, -3, 4, -4):
                yy = min(H - 1, max(0, y + dy))
                if cnt[yy, k]: mean[y, k] = mean[yy, k] / cnt[yy, k]; break
            else:
                mean[y, k] = mean[y, max(0, k - 1)]
        else: mean[y, k] /= cnt[y, k]
bodycols = [np.where(body_o[y])[0] for y in range(H)]
def detail_at(y, x):
    xs = bodycols[y]
    if not len(xs): return 0
    j = xs[np.argmin(np.abs(xs - x))]
    return detail[y, j]
for y in range(H):
    for xn in range(W):
        if body_n[y, xn]:
            k = min(int(round(din_n[y, xn])), maxin + 1)
            c = mean[y, k] + 0.9 * detail_at(y, xn)
            out[y, xn, :3] = c; out[y, xn, 3] = 255
        elif dout_n[y, xn] <= 4:
            c = pick(~body_o & (src[:, :, 3] > 0), dout_o, y, dout_n[y, xn], xn)
            if c is not None: out[y, xn] = c
img = Image.fromarray(out.clip(0, 255).astype(np.uint8), 'RGBA')
img.save(HERE + '/soa_strip.png')
bg = Image.new('RGBA', (W, 128), (30, 30, 50, 255)); o = Image.open(HERE + '/../cdrom/wotg_strip.png').convert('RGBA')
bg.alpha_composite(o, (0, 0)); bg.alpha_composite(img, (0, 64)); bg.resize((1024, 256), Image.LANCZOS).save(HERE + '/compare.png')
print('ok', off)
