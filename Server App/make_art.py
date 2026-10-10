#!/usr/bin/env python3
"""make_art.py: draws the Server App's background strips and little icons (needs Pillow; the app itself only needs the PNG files in app/art).
The look follows the install disc: deep navy, fine scanlines, a soft blue glow, a purple band, and a crystal."""
import math, os, random
from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'art')
os.makedirs(OUT, exist_ok=True)
NAV_BOTTOM = (13, 11, 38)                               # the sidebar's flat bottom colour (#0d0b26)
S = 4                                                   # drawing scale for smooth edges


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def disc_background(w, h, glow=(0.5, 0.0), seed=1, band=False):
    """Navy gradient with scanlines, a soft glow and a vignette, like the install disc's screen."""
    random.seed(seed)
    top, mid, bot = (6, 9, 26), (10, 18, 48), (16, 14, 44)
    img = Image.new('RGB', (w, h))
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        c = lerp(top, mid, t * 2) if t < 0.5 else lerp(mid, bot, (t - 0.5) * 2)
        for x in range(w):
            px[x, y] = c
    glow_img = Image.new('RGB', (w, h), (0, 0, 0))
    gd = ImageDraw.Draw(glow_img)
    gx, gy = int(w * glow[0]), int(h * glow[1])
    for r, a in ((int(max(w, h) * 0.55), 22), (int(max(w, h) * 0.35), 26), (int(max(w, h) * 0.18), 30)):
        gd.ellipse((gx - r, gy - r, gx + r, gy + r), fill=(a // 3, a // 2 + 6, a + 24))
    glow_img = glow_img.filter(ImageFilter.GaussianBlur(max(w, h) // 8))
    img = Image.composite(Image.blend(img, glow_img, 0.0), img, Image.new('L', (w, h), 255))
    img = Image.eval(img, lambda v: v)
    gl = glow_img.load()
    px = img.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            gr, gg, gb = gl[x, y]
            px[x, y] = (min(255, r + gr), min(255, g + gg), min(255, b + gb))
    d = ImageDraw.Draw(img)
    lines = Image.new('L', (w, h), 0)                   # scanlines (soft)
    ld = ImageDraw.Draw(lines)
    for y in range(0, h, 3):
        ld.line((0, y, w, y), fill=70)
    img = Image.composite(Image.new('RGB', (w, h), (0, 0, 8)), img, lines)
    d = ImageDraw.Draw(img)
    if band:                                            # the purple band of the installer
        by = int(h * 0.80)
        for i in range(max(2, h // 18)):
            t = i / max(1, h // 18)
            c = lerp((52, 40, 120), (20, 18, 70), t)
            d.line((0, by + i, w, by + i), fill=c)
    for _ in range(max(10, w * h // 5200)):             # a few stars
        x, y = random.randrange(w), random.randrange(h)
        v = random.randrange(70, 170)
        d.point((x, y), fill=(v, v, min(255, v + 50)))
    vig = Image.new('L', (w, h), 0)
    vd = ImageDraw.Draw(vig)
    vd.rectangle((0, 0, w, h), fill=140)
    vd.ellipse((-w * 0.25, -h * 0.35, w * 1.25, h * 1.35), fill=0)
    vig = vig.filter(ImageFilter.GaussianBlur(max(w, h) // 10))
    img = Image.composite(Image.new('RGB', (w, h), (2, 3, 12)), img, vig)
    return img


def new_icon(size=256):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def shadow_pass(im, offset=(0, 10), blur=10, alpha=90):
    a = im.split()[3]
    sh = Image.new('RGBA', im.size, (0, 0, 20, 0))
    sh.putalpha(a.point(lambda v: min(255, v * alpha // 255)))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    base = Image.new('RGBA', im.size, (0, 0, 0, 0))
    base.alpha_composite(sh, offset)
    base.alpha_composite(im)
    return base


def grad_poly(im, pts, c1, c2, vertical=True):
    mask = Image.new('L', im.size, 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    g = Image.new('RGBA', im.size)
    gp = g.load()
    ys = [p[1] for p in pts]
    y0, y1 = min(ys), max(ys)
    for y in range(im.size[1]):
        t = min(1, max(0, (y - y0) / max(1, y1 - y0)))
        c = lerp(c1, c2, t) + (255,)
        for x in range(im.size[0]):
            gp[x, y] = c
    im.paste(g, (0, 0), mask)


def icon_crystal():
    im, d = new_icon()
    pts = [(128, 18), (190, 96), (190, 160), (128, 238), (66, 160), (66, 96)]
    grad_poly(im, pts, (200, 240, 255), (70, 130, 235))
    d.polygon([(128, 18), (190, 96), (128, 100)], fill=(235, 250, 255, 255))
    d.polygon([(128, 18), (66, 96), (128, 100)], fill=(190, 228, 255, 255))
    d.polygon([(66, 96), (66, 160), (128, 100)], fill=(120, 175, 245, 255))
    d.polygon([(190, 96), (190, 160), (128, 100)], fill=(150, 200, 250, 255))
    d.polygon([(66, 160), (128, 238), (128, 100)], fill=(70, 120, 225, 255))
    d.polygon([(190, 160), (128, 238), (128, 100)], fill=(95, 150, 240, 255))
    d.line([(128, 18), (190, 96), (190, 160), (128, 238), (66, 160), (66, 96), (128, 18)], fill=(20, 40, 120, 255), width=6, joint='curve')
    d.polygon([(100, 70), (118, 52), (122, 74)], fill=(255, 255, 255, 230))
    return shadow_pass(im)


def icon_moogle():
    im, d = new_icon()
    d.polygon([(40, 150), (6, 110), (24, 168), (14, 200), (52, 190)], fill=(150, 90, 190, 255), outline=(60, 30, 100, 255))
    d.polygon([(216, 150), (250, 110), (232, 168), (242, 200), (204, 190)], fill=(150, 90, 190, 255), outline=(60, 30, 100, 255))
    d.line([(128, 44), (128, 20)], fill=(70, 40, 40, 255), width=7)
    d.ellipse((108, -2, 148, 38), fill=(235, 70, 80, 255), outline=(120, 20, 40, 255), width=5)
    d.ellipse((118, 6, 130, 18), fill=(255, 190, 190, 255))
    d.ellipse((74, 34, 106, 70), fill=(255, 245, 240, 255), outline=(90, 60, 70, 255), width=5)
    d.ellipse((150, 34, 182, 70), fill=(255, 245, 240, 255), outline=(90, 60, 70, 255), width=5)
    d.ellipse((46, 44, 210, 208), fill=(255, 248, 242, 255), outline=(90, 60, 70, 255), width=7)
    d.ellipse((92, 108, 112, 140), fill=(40, 30, 50, 255))
    d.ellipse((146, 108, 166, 140), fill=(40, 30, 50, 255))
    d.ellipse((97, 112, 105, 122), fill=(255, 255, 255, 255))
    d.ellipse((151, 112, 159, 122), fill=(255, 255, 255, 255))
    d.ellipse((116, 142, 142, 168), fill=(240, 100, 110, 255), outline=(120, 30, 50, 255), width=4)
    d.ellipse((66, 144, 92, 164), fill=(255, 205, 210, 255))
    d.ellipse((166, 144, 192, 164), fill=(255, 205, 210, 255))
    d.arc((108, 150, 150, 186), 20, 160, fill=(90, 40, 60, 255), width=5)
    return shadow_pass(im)


def icon_chocobo():
    im, d = new_icon()
    for dx, ang in ((-34, -18), (0, 0), (34, 18)):       # head feathers
        d.polygon([(128 + dx, 44), (128 + dx - 16 + ang // 2, 8), (128 + dx + 16 + ang // 2, 44)], fill=(255, 214, 60, 255), outline=(150, 100, 10, 255))
    d.ellipse((40, 36, 216, 212), fill=(255, 222, 70, 255), outline=(150, 100, 10, 255), width=7)
    d.ellipse((70, 60, 150, 110), fill=(255, 236, 130, 255))
    d.ellipse((92, 96, 118, 136), fill=(40, 30, 20, 255))
    d.ellipse((150, 96, 176, 136), fill=(40, 30, 20, 255))
    d.ellipse((98, 102, 108, 114), fill=(255, 255, 255, 255))
    d.ellipse((156, 102, 166, 114), fill=(255, 255, 255, 255))
    d.polygon([(116, 140), (190, 148), (196, 164), (180, 188), (112, 180)], fill=(255, 150, 40, 255), outline=(150, 70, 10, 255))
    d.line([(116, 164), (188, 160)], fill=(150, 70, 10, 255), width=4)
    d.ellipse((58, 142, 88, 166), fill=(255, 176, 96, 255))
    return shadow_pass(im)


def icon_world():
    im, d = new_icon()
    d.ellipse((24, 24, 232, 232), fill=(60, 120, 230, 255), outline=(15, 40, 120, 255), width=8)
    d.polygon([(70, 70), (120, 56), (150, 84), (130, 118), (84, 124), (60, 100)], fill=(110, 200, 120, 255))
    d.polygon([(140, 140), (196, 124), (206, 170), (172, 206), (140, 186)], fill=(110, 200, 120, 255))
    d.ellipse((60, 40, 120, 80), fill=(130, 175, 245, 255))
    d.arc((8, 100, 248, 170), 190, 350, fill=(255, 215, 110, 255), width=9)
    return shadow_pass(im)


def icon_shield():
    im, d = new_icon()
    pts = [(128, 20), (214, 52), (206, 140), (128, 236), (50, 140), (42, 52)]
    grad_poly(im, pts, (255, 224, 120), (200, 120, 40))
    d.line(pts + [pts[0]], fill=(110, 60, 20, 255), width=8, joint='curve')
    d.polygon([(128, 52), (176, 70), (172, 130), (128, 190), (84, 130), (80, 70)], fill=(70, 100, 220, 255), outline=(20, 30, 100, 255))
    d.polygon([(128, 70), (140, 104), (176, 106), (148, 128), (158, 164), (128, 144), (98, 164), (108, 128), (80, 106), (116, 104)], fill=(255, 240, 160, 255))
    return shadow_pass(im)


def icon_chat():
    im, d = new_icon()
    d.rounded_rectangle((20, 36, 236, 176), radius=44, fill=(255, 250, 245, 255), outline=(70, 70, 120, 255), width=8)
    d.polygon([(72, 168), (66, 226), (126, 172)], fill=(255, 250, 245, 255), outline=(70, 70, 120, 255))
    d.line([(72, 172), (126, 172)], fill=(255, 250, 245, 255), width=8)
    for x in (88, 128, 168):
        d.ellipse((x - 14, 92, x + 14, 120), fill=(100, 130, 235, 255))
    d.polygon([(184, 40), (194, 14), (204, 40), (230, 50), (204, 60), (194, 86), (184, 60), (158, 50)], fill=(255, 220, 90, 255), outline=(150, 100, 10, 255))
    return shadow_pass(im)


def icon_potion():
    im, d = new_icon()
    d.polygon([(100, 20), (156, 20), (156, 84), (214, 176), (200, 226), (56, 226), (42, 176), (100, 84)], fill=(222, 240, 255, 255), outline=(60, 80, 140, 255))
    d.polygon([(60, 150), (196, 150), (214, 176), (200, 226), (56, 226), (42, 176)], fill=(240, 80, 150, 255))
    d.ellipse((96, 168, 120, 192), fill=(255, 190, 220, 255))
    d.ellipse((148, 190, 166, 208), fill=(255, 190, 220, 255))
    d.rounded_rectangle((90, 6, 166, 34), radius=10, fill=(190, 130, 70, 255), outline=(90, 50, 20, 255), width=6)
    d.line([(100, 60), (100, 120)], fill=(255, 255, 255, 255), width=8)
    d.line([(100, 20), (156, 20), (156, 84), (214, 176), (200, 226), (56, 226), (42, 176), (100, 84), (100, 20)], fill=(60, 80, 140, 255), width=7, joint='curve')
    return shadow_pass(im)


def icon_disc():
    im, d = new_icon()
    d.ellipse((16, 16, 240, 240), fill=(200, 215, 240, 255), outline=(60, 70, 130, 255), width=8)
    for i, c in enumerate(((255, 120, 160), (255, 220, 110), (120, 220, 160), (110, 170, 255))):
        d.pieslice((36, 36, 220, 220), 200 + i * 40, 230 + i * 40, fill=lerp(c, (200, 215, 240), 0.35) + (255,))
    d.ellipse((92, 92, 164, 164), fill=(20, 28, 70, 255), outline=(60, 70, 130, 255), width=6)
    d.polygon([(128, 100), (144, 128), (128, 156), (112, 128)], fill=(170, 225, 255, 255))
    return shadow_pass(im)


def icon_server():
    im, d = new_icon()
    for i, y in enumerate((30, 100, 170)):
        d.rounded_rectangle((28, y, 228, y + 56), radius=16, fill=(40, 60, 130, 255) if i != 1 else (50, 80, 160, 255), outline=(150, 190, 255, 255), width=5)
        d.ellipse((50, y + 18, 70, y + 38), fill=(110, 240, 160, 255) if i != 2 else (255, 210, 90, 255))
        d.line([(100, y + 28), (200, y + 28)], fill=(150, 190, 255, 160), width=6)
    return shadow_pass(im)


def icon_star():
    im, d = new_icon()
    d.polygon([(128, 8), (158, 96), (248, 128), (158, 160), (128, 248), (98, 160), (8, 128), (98, 96)], fill=(255, 226, 120, 255), outline=(170, 110, 20, 255))
    d.polygon([(128, 40), (146, 100), (128, 128), (110, 100)], fill=(255, 250, 200, 255))
    return shadow_pass(im)


def icon_heart():
    im, d = new_icon()
    d.polygon([(128, 232), (24, 120), (24, 70), (64, 36), (110, 48), (128, 84), (146, 48), (192, 36), (232, 70), (232, 120)], fill=(250, 90, 130, 255), outline=(140, 20, 60, 255))
    d.ellipse((58, 62, 90, 90), fill=(255, 190, 210, 255))
    return shadow_pass(im)


def icon_gil():
    im, d = new_icon()
    d.ellipse((20, 20, 236, 236), fill=(255, 205, 70, 255), outline=(150, 90, 10, 255), width=8)
    d.ellipse((50, 50, 206, 206), outline=(200, 140, 30, 255), width=6)
    d.polygon([(128, 70), (160, 128), (128, 186), (96, 128)], fill=(255, 245, 190, 255), outline=(170, 110, 20, 255))
    return shadow_pass(im)


ICONS = dict(crystal=icon_crystal, moogle=icon_moogle, chocobo=icon_chocobo, world=icon_world, shield=icon_shield, chat=icon_chat,
             potion=icon_potion, disc=icon_disc, server=icon_server, star=icon_star, heart=icon_heart, gil=icon_gil)

def hero(w=1400, h=300, cxf=0.76):
    """An original ink-and-watercolour style sky: soft clouds, a glowing crystal and drifting stars."""
    random.seed(11)
    img = Image.new('RGB', (w, h))
    px = img.load()
    for y in range(h):
        t = y / (h - 1)
        c = lerp((14, 24, 70), (70, 80, 160), t * 1.4) if t < 0.72 else lerp((70, 80, 160), (196, 176, 214), (t - 0.72) / 0.28)
        for x in range(w):
            px[x, y] = c
    layer = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for _ in range(46):                                  # watercolour clouds
        cx, cy = random.randrange(-100, w + 100), int(h * random.uniform(0.35, 1.0))
        rw, rh = random.randrange(80, 260), random.randrange(18, 56)
        col = random.choice(((235, 230, 250), (190, 200, 240), (255, 220, 215), (170, 185, 235)))
        ld.ellipse((cx - rw, cy - rh, cx + rw, cy + rh), fill=col + (random.randrange(40, 95),))
    layer = layer.filter(ImageFilter.GaussianBlur(14))
    img = Image.alpha_composite(img.convert('RGBA'), layer).convert('RGB')
    d = ImageDraw.Draw(img)
    for _ in range(90):                                  # stars
        x, y = random.randrange(w), random.randrange(int(h * 0.7))
        v = random.randrange(130, 255)
        r = random.choice((0, 0, 1, 1, 2))
        d.ellipse((x - r, y - r, x + r, y + r), fill=(v, v, 255))
    glow = Image.new('RGB', (w, h), (0, 0, 0))             # crystal glow behind the crystal
    gd = ImageDraw.Draw(glow)
    cx, cy = int(w * cxf), int(h * 0.5)
    for r, c in ((150, (14, 30, 60)), (95, (30, 60, 100)), (50, (70, 120, 170))):
        gd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=c)
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    gp, ip = glow.load(), img.load()
    for y in range(h):
        for x in range(w):
            a, b = ip[x, y], gp[x, y]
            ip[x, y] = (min(255, a[0] + b[0]), min(255, a[1] + b[1]), min(255, a[2] + b[2]))
    cr = icon_crystal().resize((int(h * 0.72), int(h * 0.72)), Image.LANCZOS)
    img = img.convert('RGBA')
    img.alpha_composite(cr, (cx - cr.size[0] // 2, cy - cr.size[1] // 2))
    for name, fx, fy, sz in (('star', 0.24, 0.18, 26), ('star', 0.76, 0.28, 22), ('star', 0.34, 0.66, 18)):
        st = Image.open(os.path.join(OUT, '%s_%d.png' % (name, 32 if sz < 32 else 64))).resize((sz, sz), Image.LANCZOS)
        img.alpha_composite(st, (int(w * fx), int(h * fy)))
    ink = Image.new('L', (w, h), 0)                       # faint pencil texture
    idr = ImageDraw.Draw(ink)
    for _ in range(260):
        x, y = random.randrange(w), random.randrange(h)
        idr.line((x, y, x + random.randrange(20, 90), y + random.randrange(-3, 4)), fill=random.randrange(8, 26))
    img = Image.composite(Image.new('RGBA', (w, h), (240, 240, 255, 255)), img, ink.filter(ImageFilter.GaussianBlur(0.6)))
    return img.convert('RGB')


if __name__ == '__main__':
    for name, fn in ICONS.items():
        big = fn()
        for px in (24, 32, 64):
            big.resize((px, px), Image.LANCZOS).save(os.path.join(OUT, '%s_%d.png' % (name, px)))
    nav = disc_background(340, 1500, glow=(0.5, 0.06), seed=3, band=False)
    fade = Image.new('L', nav.size, 0)                  # the bottom of the sidebar is one flat colour (the status pill sits on it)
    fd = ImageDraw.Draw(fade)
    for y in range(0, nav.size[1]):
        fd.line((0, y, nav.size[0], y), fill=int(255 * min(1, max(0, (y - 360) / 280.0))))
    nav = Image.composite(Image.new('RGB', nav.size, NAV_BOTTOM), nav, fade)
    nav.save(os.path.join(OUT, 'nav_bg.png'))
    disc_background(2600, 110, glow=(0.8, 0.5), seed=5, band=False).save(os.path.join(OUT, 'banner_bg.png'))
    mid = hero(620, 150, 0.5).convert('RGBA')                  # drawn at its real size and shape, not cropped and stretched
    a = Image.new('L', mid.size, 0)
    ap = a.load()
    for y in range(mid.size[1]):
        for x in range(mid.size[0]):
            fx = min(1, x / 190.0, (mid.size[0] - 1 - x) / 190.0)
            fy = min(1, y / 26.0, (mid.size[1] - 1 - y) / 26.0)
            ap[x, y] = int(255 * (fx * fx * (3 - 2 * fx)) * (fy * fy * (3 - 2 * fy)))
    mid.putalpha(a)
    mid.save(os.path.join(OUT, 'hero_mid.png'))
    print('art written to', OUT)
