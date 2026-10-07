#!/usr/bin/env python3
"""build_art.py: new installer resources for the 2016 install disc.
  17.DAT (English installer graphics): the 'Wings of the Goddess' strip (textures ex4us1/ex4us2) replaced by soa_strip.png
  14.DAT / 15.DAT (English installer messages): 'Now installing.' and the 'complete' message get 'Fan Project by Habex'.
Writes out/0_14.DAT, out/0_15.DAT, out/0_17.DAT (same names as CDROM/0/*.DAT on the disc)."""
import os, struct, sys
import numpy as np
from PIL import Image
H = os.path.dirname(os.path.abspath(__file__)); W = os.path.join(H, '..', '..')
sys.path.insert(0, os.path.join(W, 'b36_pcimport')); sys.path.insert(0, os.path.join(W, 'b14_backport'))
from icon import swizzle8
from textfmt import dmsg_read, dmsg_write
SRC = os.path.join(H, '..', 'cdrom'); OUT = os.path.join(H, 'out'); os.makedirs(OUT, exist_ok=True)
def swz_index(i): return (i & 0xE7) | ((i & 0x08) << 1) | ((i & 0x10) >> 1)
def chunks(d):
    o = 0
    while o + 16 <= len(d):
        v = struct.unpack_from('<I', d, o + 4)[0]; sz = ((v >> 7) & 0x7ffff) * 16
        if sz == 0: break
        yield o, bytes(d[o:o + 4]), v & 0x7f, sz; o += sz
def encode_tile(img):
    """RGBA 128x128 -> (swizzled PSMT8 pixels, 1024-byte CLUT in CSM1 order, PS2 alpha 0..128)"""
    q = img.convert('RGBA').quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    pal = q.getpalette(rawmode='RGBA') or []
    pal = (pal + [0] * 1024)[:1024]
    idx = np.array(q, np.uint8)
    clut = bytearray(1024)
    for c in range(256):
        r, g, b, a = pal[4 * c:4 * c + 4]
        k = swz_index(c); clut[4 * k:4 * k + 4] = bytes([r, g, b, min(128, (a + 1) // 2)])
    return swizzle8(idx.tobytes(), 128, 128), bytes(clut)
# 1) graphics
d = bytearray(open(os.path.join(SRC, '0_17.DAT'), 'rb').read())
strip = Image.open(os.path.join(H, 'soa_strip.png')).convert('RGBA')
tiles = {}
for name, xa, xb in ((b'ex4u', 0, 128), (b'ex41', 256, 384)):
    t = Image.new('RGBA', (128, 128), (0, 0, 0, 0))
    t.paste(strip.crop((xa, 0, xa + 128, 64)), (0, 0)); t.paste(strip.crop((xb, 0, xb + 128, 64)), (0, 64))
    tiles[name] = t
done = 0
for o, nm, t, sz in chunks(d):
    if t == 8 and nm in tiles:
        body = o + 16; w, h = struct.unpack_from('<HH', d, body + 20); assert (w, h) == (128, 128) and d[body + 16] == 0x0a
        px, cl = encode_tile(tiles[nm])
        d[body + 0x90:body + 0x90 + w * h] = px
        d[body + 0x90 + w * h + 0x60:body + 0x90 + w * h + 0x60 + 1024] = cl
        done += 1
assert done == 2, done
open(os.path.join(OUT, '0_17.DAT'), 'wb').write(d)
# 2) messages
for fn in ('0_14.DAT', '0_15.DAT'):
    raw = open(os.path.join(SRC, fn), 'rb').read(); r = dmsg_read(raw); ents = list(r['ents'])
    for i, e in enumerate(ents):
        if b'Now installing.' in e and b'Habex' not in e:
            ents[i] = e.replace(b'Now installing.', b'Now installing.    Fan Project by Habex', 1)
        elif b'complete.' in e and b'Installation of FINAL FANTASY XI' in e and b'Habex' not in e:
            ents[i] = e.replace(b'complete.', b'complete.\nFan Project by Habex', 1)
    new = dmsg_write(raw, ents); chk = dmsg_read(new)['ents']
    assert sum(b'Habex' in e for e in chk) == 2, fn
    open(os.path.join(OUT, fn), 'wb').write(new); print(fn, len(raw), '->', len(new))
print('17.DAT tiles replaced:', done)
