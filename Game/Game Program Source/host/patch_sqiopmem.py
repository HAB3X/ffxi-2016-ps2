#!/usr/bin/env python3
"""patch_sqiopmem.py A_SIZE [B_SIZE] - write emb/SQIOPMEM.IRX from the original with smaller IOP memory pools.
Square's PlayOnline memory manager reserves two fixed blocks when it starts: pool A 0x84C00 bytes (a stack arena the Sony/Square ERX modules are
loaded into) and pool B 0x20000 bytes. Real PS2 hardware runs out of IOP memory, so the host loads this patched copy. Sizes in hex or decimal."""
import struct, sys, os
D = os.path.dirname(os.path.abspath(__file__)) + '/emb/'
a = int(sys.argv[1], 0); b = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x20000
d = bytearray(open(D + 'SQIOPMEM.IRX.orig', 'rb').read())
def put(off, word, expect):
    assert struct.unpack_from('<I', d, off)[0] == expect, (hex(off), hex(struct.unpack_from('<I', d, off)[0]))
    struct.pack_into('<I', d, off, word)
# pool A: lui a1,hi / ori a1,a1,lo  (size) and lui v0,hi / ori v0,v0,lo (size - 0x10, the arena's end)
put(0xf80, 0x3c050000 | (a >> 16), 0x3c050008); put(0xf84, 0x34a50000 | (a & 0xffff), 0x34a54c00)
e = a - 0x10
put(0xfa4, 0x3c020000 | (e >> 16), 0x3c020008); put(0xfa8, 0x34420000 | (e & 0xffff), 0x34424bf0)
# pool B: lui a1,2 (size) twice
assert b & 0xffff == 0, 'pool B size must be a multiple of 0x10000'
put(0xfd4, 0x3c050000 | (b >> 16), 0x3c050002); put(0xff4, 0x3c050000 | (b >> 16), 0x3c050002)
open(D + 'SQIOPMEM.IRX', 'wb').write(d)
print('SQIOPMEM.IRX written: pool A 0x%x (%d KB), pool B 0x%x (%d KB)' % (a, a // 1024, b, b // 1024))
