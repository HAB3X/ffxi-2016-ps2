"""PC item icon (0x91 + name[16] + BITMAPINFOHEADER + 256 x BGRA-ordered palette + 32x32 8-bit bottom-up pixels)
-> PS2 2012 item icon (name[16] + GS header + GIF packets; pixels at +0x90 in the PSMT8 block swizzle, CLUT at +0x4F0 in
CSM1 order). Built on a PS2 icon template: only name, pixels and palette are replaced."""
def swz_index(i): return (i & 0xE7) | ((i & 0x08) << 1) | ((i & 0x10) >> 1)
def swizzle8(src, w=32, h=32):
    dst = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            block = (y & ~0xF) * w + (x & ~0xF) * 2
            swap = (((y + 2) >> 2) & 1) * 4
            py = (((y & ~3) >> 1) + (y & 1)) & 7
            col = py * w * 2 + ((x + swap) & 7) * 4
            byte = ((y >> 1) & 1) + ((x >> 2) & 2)
            dst[block + col + byte] = src[y * w + x]
    return bytes(dst)
def pc_parts(B):
    name = B[1:17]; pal = B[57:57 + 1024]; px = B[57 + 1024:57 + 2048]
    return name, pal, px
def convert(pc_icon, template, alpha='keep', flip=True, swz=True, csm=True):
    name, pal, px = pc_parts(pc_icon)
    rows = b''.join(px[(31 - y) * 32:(32 - y) * 32] for y in range(32)) if flip else px
    pix = swizzle8(rows) if swz else rows
    clut = bytearray(1024)
    for k in range(256):
        e = bytearray(pal[4 * k:4 * k + 4])
        if alpha == 'half': e[3] = (e[3] + 1) // 2
        j = swz_index(k) if csm else k
        clut[4 * j:4 * j + 4] = e
    t = bytearray(template)
    t[0:16] = name; t[0x90:0x490] = pix; t[0x4F0:0x8F0] = bytes(clut)
    return bytes(t)
