#!/usr/bin/env python3
"""ps2proxy_npc - NPC-side translation between LandSandBoat and the 2007 PS2 FFXI client.

Loaded by ps2proxy.py (register(px) at import). On by default through the "npc" alias; switch off with
ps2proxy --no-translate npc-ids. (The shop list layout, s2c 0x03C, is ps2proxy_core's core-shop.)

  npc-ids    NPC server ids. Post-2007 NPCs were inserted into the zones' entity lists, so LSB's NPC ids (taken
             from the modern client) are shifted against the 2007 lists (Northern San d'Oria: Pontaudarme is
             17723598 in LSB, 17723586 in 2007). The 2007 client names an NPC and finds its event scripts (event
             DAT block per actor) by that id, so a shifted NPC shows another name and its events do not start
             ("the dialogue box closes at once"). The map, per zone, comes from lsb_textids_2007.py
             (npc_id_map.json: named, unambiguous pairs only; mobs are not translated). s2c packets naming an NPC
             get the 2007 id + index, c2s packets naming it get LSB's back; an LSB NPC whose id a moved NPC now
             uses is hidden (its 0x00E is dropped).
             s2c: 0x00E 0x02A 0x029 0x032 0x033 0x034 0x036 0x038 0x039 0x05B 0x065   (current zone from 0x00A)
             c2s: 0x016 0x017 0x01A 0x036 0x05B 0x05C

Unit tests (no server): python3 ps2proxy_npc.py
"""
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
MAP_FILE = os.environ.get('PS2PROXY_NPC_MAP', os.path.join(HERE, 'ps2proxy_npc_ids.json'))

_MAP = None                  # {zone: (fwd {lsb: 2007}, rev {2007: lsb}, hide set, fwd_idx, rev_idx)}
STATS = {}


def load_map(path=None):
    global _MAP
    _MAP = {}
    p = path or MAP_FILE
    if not os.path.exists(p):
        return _MAP
    for z, d in json.load(open(p)).items():
        fwd = {int(k): int(v) for k, v in d['map'].items()}
        rev = {v: k for k, v in fwd.items()}
        # an NPC that has a mapping of its own is never hidden: it moves to its own 2012 id, so it cannot clash
        # (1 Oct 2026: 4,282 mapped NPCs were still on old hide lists; Windurst Woods waited forever for one of them)
        _MAP[int(z)] = (fwd, rev, set(d.get('hide', ())) - set(fwd),
                        {k & 0xFFF: v & 0xFFF for k, v in fwd.items()}, {v & 0xFFF: k & 0xFFF for k, v in fwd.items()})
    return _MAP


def _zone(ctx):
    if _MAP is None:
        load_map()
    return _MAP.get(getattr(ctx, 'npc_zone', None))


def _u16(p, o):
    return struct.unpack_from('<H', p, o)[0]


def _u32(p, o):
    return struct.unpack_from('<I', p, o)[0]


def _count(ctx, key, what):
    n = STATS.get(key, 0) + 1
    STATS[key] = n
    if n == 1 and ctx is not None and hasattr(ctx, 'log'):
        ctx.log(ctx.tag, 'npc   %s (first time; counted silently from now on)' % what)


def _swap(ctx, pkt, pairs, direction, pid):
    """pairs: [(id offset, index offset or None)]; direction 'fwd' (LSB->2007) or 'rev'."""
    z = _zone(ctx)
    if not z:
        return None
    ids, idx = (z[0], z[3]) if direction == 'fwd' else (z[1], z[4])
    p = None
    for io, xo in pairs:
        if len(pkt) < io + 4:
            continue
        u = _u32(pkt, io)
        if u in ids:
            p = p or bytearray(pkt)
            struct.pack_into('<I', p, io, ids[u])
            if xo is not None and len(pkt) >= xo + 2 and _u16(pkt, xo) == (u & 0xFFF):
                struct.pack_into('<H', p, xo, ids[u] & 0xFFF)
    if p is not None:
        _count(ctx, '%s %03X' % (direction, pid), '%s 0x%03X NPC id translated (%s)' % (
            's2c' if direction == 'fwd' else 'c2s', pid, 'LSB -> 2007' if direction == 'fwd' else '2007 -> LSB'))
        return bytes(p)
    return None


# ---- s2c -----------------------------------------------------------------------------------------------------
def s2c_login(ctx, pkt):
    """0x00A: remember the zone (ZoneNo @0x30) for the id map."""
    if len(pkt) >= 0x34:
        ctx.npc_zone = _u16(pkt, 0x30)
    return None


def s2c_char_npc(ctx, pkt):
    z = _zone(ctx)
    if z and len(pkt) >= 0x0A and _u32(pkt, 4) in z[2]:
        _count(ctx, 'hide 00E', 's2c 0x00E of an LSB NPC whose id a moved NPC uses: hidden')
        return b''
    return _swap(ctx, pkt, [(4, 8)], 'fwd', 0x00E)


S2C_IDS = {0x02A: [(4, 0x18)], 0x029: [(4, 0x14), (8, 0x16)], 0x032: [(4, 8)], 0x033: [(4, 8)], 0x034: [(4, 0x28)],
           0x036: [(4, 8)], 0x038: [(4, 0x0C), (8, 0x0E)], 0x039: [(4, 0x10), (8, 0x12)], 0x05B: [(0x10, 0x14)],
           0x065: [(0x10, 0x14)]}
C2S_IDS = {0x017: [(8, 4)], 0x01A: [(4, 8)], 0x036: [(4, 0x3A)], 0x05B: [(4, 0x0C)], 0x05C: [(0x10, 0x1C)]}


def _make(pid, pairs, direction):
    def hook(ctx, pkt):
        return _swap(ctx, pkt, pairs, direction, pid)
    hook.__name__ = 'npc_%s_%03x' % (direction, pid)
    return hook


def c2s_charreq(ctx, pkt):
    """0x016 carries only the ActIndex."""
    z = _zone(ctx)
    if z and len(pkt) >= 6 and _u16(pkt, 4) in z[4]:
        p = bytearray(pkt)
        struct.pack_into('<H', p, 4, z[4][_u16(pkt, 4)])
        _count(ctx, 'rev 016', 'c2s 0x016 NPC index translated (2007 -> LSB)')
        return bytes(p)
    return None


def groups():
    ids = [('s2c', 0x00A, s2c_login), ('s2c', 0x00E, s2c_char_npc), ('c2s', 0x016, c2s_charreq)]
    ids += [('s2c', pid, _make(pid, pr, 'fwd')) for pid, pr in S2C_IDS.items()]
    ids += [('c2s', pid, _make(pid, pr, 'rev')) for pid, pr in C2S_IDS.items()]
    return {
        'npc-ids': ('NPC server ids LSB <-> 2007 entity lists (npc id map from lsb_textids_2007.py)', ids),
    }


ALIASES = {'npc': ['npc-ids']}


def register(px):
    for name, (desc, items) in groups().items():
        if name in px.OPTIONAL_HOOKS:
            continue
        for direction, pid, fn in items:
            (px.c2s_hook if direction == 'c2s' else px.s2c_hook)(pid, optional=name, desc=desc)(fn)
    for alias, names in ALIASES.items():
        px.TRANSLATION_ALIASES.setdefault(alias, list(names))


# ---- unit tests ----------------------------------------------------------------------------------------------
def unit_tests():
    class Ctx:
        tag = 'T'
        npc_zone = None
        def log(self, *a):
            pass
    global _MAP
    _MAP = {}
    fwd = {17723598: 17723586}
    _MAP[231] = (fwd, {v: k for k, v in fwd.items()}, {17723586},
                 {k & 0xFFF: v & 0xFFF for k, v in fwd.items()}, {v & 0xFFF: k & 0xFFF for k, v in fwd.items()})
    c = Ctx()
    ok = []
    login = bytearray(0x104); struct.pack_into('<H', login, 0x30, 231)
    s2c_login(c, bytes(login)); ok.append(('zone from 0x00A', c.npc_zone == 231))
    e = struct.pack('<HHIHHHHH', 0x32 | (0x14 // 4) << 9, 0, 17723598, 206, 231, 717, 0, 0)
    r = _swap(c, e, S2C_IDS[0x032], 'fwd', 0x032)
    ok.append(('0x032 id+index LSB->2007', _u32(r, 4) == 17723586 and _u16(r, 8) == 194 and _u16(r, 0x0C) == 717))
    a = struct.pack('<HHIHHI', 0x1A | (0x10 // 4) << 9, 0, 17723586, 194, 0, 0)
    r = _swap(c, a, C2S_IDS[0x01A], 'rev', 0x01A)
    ok.append(('0x01A talk 2007->LSB', _u32(r, 4) == 17723598 and _u16(r, 8) == 206))
    hidden = struct.pack('<HHIH', 0x0E, 0, 17723586, 194) + bytes(60)
    ok.append(('0x00E of a hidden LSB NPC dropped', s2c_char_npc(c, hidden) == b''))
    other = struct.pack('<HHIH', 0x0E, 0, 17723397, 5) + bytes(60)
    ok.append(('unmapped NPC untouched', s2c_char_npc(c, other) is None))
    q = struct.pack('<HH', 0x16, 0) + struct.pack('<HH', 194, 0)
    ok.append(('0x016 index 2007->LSB', _u16(c2s_charreq(c, q), 4) == 206))
    c.npc_zone = 230
    ok.append(('other zone untouched', _swap(c, e, S2C_IDS[0x032], 'fwd', 0x032) is None))
    for n, v in ok:
        print('  %-40s %s' % (n, 'PASS' if v else 'FAIL'))
    _MAP = None
    return all(v for _, v in ok)


if __name__ == '__main__':
    import sys
    sys.exit(0 if unit_tests() else 1)
