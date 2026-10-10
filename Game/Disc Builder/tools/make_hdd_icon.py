#!/usr/bin/env python3
"""make_hdd_icon.py - the hard drive icon of the game: icon.sys + list.ico (a small spinning crystal).

usage:
  make_hdd_icon.py OUTDIR                  write OUTDIR/icon.sys and OUTDIR/list.ico
  make_hdd_icon.py --c-header FILE         write the data the host embeds (host/icon_data.h)
  make_hdd_icon.py --check DIR             parse DIR/icon.sys and DIR/list.ico and report anything out of spec

The PS2 browsers read the game's partition root: icon.sys names the icon file(s) and carries the two title lines; the icon file is
the PS2 3D icon format (".ico"/".icn" - the same format memory card save icons use):
  header   u32 magic 0x00010000, u32 number of animation shapes, u32 texture type (bit 2 = has a texture, bit 3 = RLE; 6 here:
           uncompressed texture, as the community HDD-OSD icons use), f32 1.0, u32 vertex count (a multiple of 3, triangle list)
  vertices per vertex: s16[4] position (1/4096 units), s16[4] normal, s16[2] texture coordinate (4096 = 1.0), u8[4] colour (0x80 = neutral)
           (with several shapes the position is repeated once per shape, here there is one)
  anim     9 words: id 1, frame length 1, speed 0, play offset 0, frame count 1, then one frame (shape 0, one key: time 0, value 1.0)
  texture  128 x 128 x u16, ABGR1555 (bit 15 = 1), top row first
icon.sys (964 bytes): 'PS2D', u16 0, u16 title line break (byte offset), u32 0, u32 background alpha, 4 x RGBA u32 corner colours,
  3 light directions and 3 light colours (4 floats each), ambient (4 floats), title[68] (Shift-JIS, both lines in one string),
  view/copy/delete icon names (64 bytes each), 512 reserved bytes.
The crystal is an original shape (a six-sided bipyramid with a middle band) with a generated blue gradient texture. No game artwork."""
import math, os, struct, sys

TITLE1 = 'FFXI 2016'
TITLE2 = 'Fan Project by Habex'
ICON_NAME = 'list.ico'
TEX = 128

# ---------- geometry -------------------------------------------------------------------------------------------------------
def crystal():
    """triangle list: [(pos, normal, uv, shade)] x 3 per triangle"""
    R, H1, H2 = 7000, 4500, 17000                       # ring radius, ring height, apex height (1/4096 units; the icon's y axis points down)
    n = 6
    top, bot = (0, -H2, 0), (0, H2, 0)
    ring_u = [(round(R * math.cos(2 * math.pi * i / n)), -H1, round(R * math.sin(2 * math.pi * i / n))) for i in range(n)]
    ring_l = [(x, H1, z) for (x, _, z) in ring_u]
    tris = []
    def face(a, b, c, uva, uvb, uvc, shade):
        # outward normal of the triangle (a,b,c), unit length scaled to 4096
        ux, uy, uz = (b[i] - a[i] for i in range(3)); vx, vy, vz = (c[i] - a[i] for i in range(3))
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        cx, cy, cz = (a[0] + b[0] + c[0]) / 3, (a[1] + b[1] + c[1]) / 3, (a[2] + b[2] + c[2]) / 3
        if nx * cx + ny * cy + nz * cz < 0:             # make the winding match the outward normal
            b, c, uvb, uvc = c, b, uvc, uvb
            nx, ny, nz = -nx, -ny, -nz
        l = math.sqrt(nx * nx + ny * ny + nz * nz) or 1
        nrm = tuple(round(4096 * q / l) for q in (nx, ny, nz))
        for p, uv in ((a, uva), (b, uvb), (c, uvc)):
            tris.append((p, nrm, uv, shade))
    for i in range(n):
        j = (i + 1) % n
        s = 0x80 + round(18 * math.cos(2 * math.pi * (i + 0.5) / n - 0.9))      # facets differ a little in brightness
        face(top, ring_u[i], ring_u[j], (2048, 0), (0, 1500), (4095, 1500), s + 8)
        face(ring_u[i], ring_l[i], ring_u[j], (0, 1500), (0, 2600), (4095, 1500), s)
        face(ring_u[j], ring_l[i], ring_l[j], (4095, 1500), (0, 2600), (4095, 2600), s - 6)
        face(bot, ring_l[j], ring_l[i], (2048, 4095), (4095, 2600), (0, 2600), s - 14)
    return tris

def icn_bytes(tex):
    tris = crystal()
    out = struct.pack('<IIIfI', 0x00010000, 1, 6, 1.0, len(tris))
    for p, nrm, uv, shade in tris:
        out += struct.pack('<4h4h2hBBBB', p[0], p[1], p[2], 1024, nrm[0], nrm[1], nrm[2], 1024, uv[0], uv[1], shade, shade, shade, 0x80)
    out += struct.pack('<IIIIIIIIf', 1, 1, 0, 0, 1, 0, 1, 0, 1.0)
    return out + tex

# ---------- texture --------------------------------------------------------------------------------------------------------
def px(r, g, b): return 0x8000 | ((b >> 3) << 10) | ((g >> 3) << 5) | (r >> 3)

def texture_runs():
    """128 x 128 pixels as (count, value) runs, top row first: a blue crystal gradient with a bright diagonal glint"""
    runs = []
    for y in range(TEX):
        v = y / (TEX - 1)
        t = 1 - abs(2 * v - 1)                                  # 0 at both apexes, 1 in the middle
        base = (round(20 + 60 * t), round(60 + 130 * t), round(140 + 100 * t))
        gl = ((y * 3) // 2) % TEX                               # glint position slides along the rows
        row = []
        for x in range(TEX):
            d = abs(x - gl)
            if d < 6: c = tuple(min(255, q + 90) for q in base)
            elif d < 9: c = tuple(min(255, q + 40) for q in base)
            else: c = base
            if x < 4 or x >= TEX - 4: c = tuple(q * 3 // 4 for q in c)       # darker edges
            row.append(px(*c))
        runs += row
    out = []
    for v in runs:
        if out and out[-1][1] == v and out[-1][0] < 0xFFFF: out[-1][0] += 1
        else: out.append([1, v])
    return [tuple(r) for r in out]

def texture_bytes():
    return b''.join(struct.pack('<H', v) * c for c, v in texture_runs())

# ---------- icon.sys -------------------------------------------------------------------------------------------------------
def icon_sys_bytes():
    title = (TITLE1 + TITLE2).encode('shift_jis')
    assert len(title) <= 68
    d = b'PS2D' + struct.pack('<HHII', 0, len(TITLE1.encode('shift_jis')), 0, 0x40)
    for c in ((0, 0, 40, 0), (0, 10, 70, 0), (0, 0, 20, 0), (0, 20, 90, 0)):         # corner colours, dark blue
        d += struct.pack('<4I', *c)
    for v in ((-0.5, -0.5, 0.5, 0), (0, 0.4, -0.1, 0), (0.5, -0.5, 0.5, 0)): d += struct.pack('<4f', *v)       # light directions
    for v in ((0.7, 0.7, 0.8, 0), (0.4, 0.4, 0.5, 0), (0.4, 0.5, 0.6, 0)): d += struct.pack('<4f', *v)        # light colours
    d += struct.pack('<4f', 0.25, 0.25, 0.3, 0)                                                        # ambient
    d += title.ljust(68, b'\0')
    for _ in range(3): d += ICON_NAME.encode().ljust(64, b'\0')                                       # view, copy, delete
    d += b'\0' * 512
    assert len(d) == 964
    return d

# ---------- checks ---------------------------------------------------------------------------------------------------------
def check(sysb, icn):
    msgs = []
    if len(sysb) != 964: msgs.append('icon.sys is %d bytes, expected 964' % len(sysb))
    if sysb[:4] != b'PS2D': msgs.append('icon.sys magic')
    off = struct.unpack_from('<H', sysb, 6)[0]
    title = sysb[0xC0:0xC0 + 68].split(b'\0')[0]
    if off > len(title): msgs.append('title break %d beyond title length %d' % (off, len(title)))
    name = sysb[0x104:0x104 + 64].split(b'\0')[0].decode()
    magic, shapes, ttype, one, nv = struct.unpack_from('<IIIfI', icn, 0)
    if magic != 0x00010000 or shapes != 1 or one != 1.0: msgs.append('icon header')
    if nv % 3: msgs.append('vertex count not a multiple of 3')
    want = 20 + nv * 24 + 36 + TEX * TEX * 2
    if len(icn) != want: msgs.append('icon is %d bytes, expected %d' % (len(icn), want))
    for i in range(nv):
        o = 20 + i * 24
        u, v = struct.unpack_from('<2h', icn, o + 16)
        if not (0 <= u <= 4096 and 0 <= v <= 4096): msgs.append('uv out of range at vertex %d' % i)
        nx, ny, nz = struct.unpack_from('<3h', icn, o + 8)
        if abs(math.sqrt(nx * nx + ny * ny + nz * nz) - 4096) > 8: msgs.append('normal %d not unit length' % i); break
    return name, title.decode('shift_jis', 'replace'), off, nv, msgs

def c_array(name, data):
    s = 'static const unsigned char %s[%d] = {\n' % (name, len(data))
    for i in range(0, len(data), 16): s += '  ' + ','.join('0x%02x' % b for b in data[i:i + 16]) + ',\n'
    return s + '};\n'

def main():
    a = sys.argv[1:]
    if len(a) == 2 and a[0] == '--c-header':
        icn_head = icn_bytes(b'')
        runs = texture_runs()
        tex = b''.join(struct.pack('<HH', c, v) for c, v in runs)
        with open(a[1], 'w') as f:
            f.write('/* generated by Game/Disc Builder/tools/make_hdd_icon.py --c-header; do not edit.\n'
                    '   The hard drive icon: icon.sys, the icon file without its texture, and the texture as (count, pixel) runs. */\n')
            f.write('#define ICON_NAME "%s"\n#define ICON_TEX_BYTES %d\n' % (ICON_NAME, TEX * TEX * 2))
            f.write(c_array('icon_sys_data', icon_sys_bytes())); f.write(c_array('icon_head_data', icn_head))
            f.write('#define ICON_RUNS %d\nstatic const unsigned short icon_tex_runs[%d] = {\n' % (len(runs), 2 * len(runs)))
            for i in range(0, len(runs), 8): f.write('  ' + ','.join('%d,%d' % r for r in runs[i:i + 8]) + ',\n')
            f.write('};\n')
        print('wrote %s (%d runs)' % (a[1], len(runs)))
    elif len(a) == 2 and a[0] == '--check':
        name, title, off, nv, msgs = check(open(a[1] + '/icon.sys', 'rb').read(), open(a[1] + '/' + ICON_NAME, 'rb').read())
        print('icon name %r, title %r (break at %d), %d vertices' % (name, title, off, nv))
        print('\n'.join(msgs) or 'ok'); sys.exit(1 if msgs else 0)
    elif len(a) == 1 and not a[0].startswith('-'):
        os.makedirs(a[0], exist_ok=True)
        open(a[0] + '/icon.sys', 'wb').write(icon_sys_bytes()); open(a[0] + '/' + ICON_NAME, 'wb').write(icn_bytes(texture_bytes()))
        print('wrote icon.sys and %s to %s' % (ICON_NAME, a[0]))
    else:
        print(__doc__); sys.exit(2)

if __name__ == '__main__': main()
