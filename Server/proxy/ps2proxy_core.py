#!/usr/bin/env python3
"""ps2proxy_core - core-gameplay packet translation between LandSandBoat and the 2007 PS2 FFXI client.

Loaded by ps2proxy.py (register(px) at import). Every layout below was read from the 2007 engine (Vana'diel
Collection INSTALL.ELF; handler addresses from its gcZoneRecvCallBack registrations) and compared with LSB's packet code.


Groups (enable with ps2proxy --translate NAME; the "core" group is on by default, --no-translate NAME turns one off):

  core-action  s2c 0x028 (actions: melee, spells, abilities, weapon skills, items, mob skills).
               The 2007 reader (CXiSchStatus::Unpack 0x2CB7F0) uses 83-bit results, LSB writes 85-bit ones:
                   field        LSB  2007
                   sub_kind      12    11   (animation)
                   info           5     4
                   value         17    16   (damage / amount)
                   bit           31    32
                   proc value    17    14   (added-effect amount)
               Without this every result after the first 17 bits is misread (garbled damage, messages,
               animations). The packet is re-packed field by field; values that do not fit are clamped.
  core-status  s2c 0x037: the 2007 client (RecvServerStatus 0x18F7E0) takes status-icon bit 8 from 1 bit per icon at
               +0x4C; LSB sends 2 bits per icon there. Re-packed; icons >= 512 (not in 2007) are hidden (0xFF).
  core-items   s2c 0x01E/0x01F/0x020 (item count/list/attr): the 2007 client has 5 containers of 81 slots and
               writes container*0xDEC + index*0x2C with no bounds check (RecvItemNum 0x23A9F0, RecvItemList 0x23AA70,
               RecvItemAttr 0x23AB20). LSB also sends satchel/sack/case/wardrobes (5..17): those packets are dropped
               (they would overwrite client memory). s2c 0x01C item max: the 2007 layout is 5 x u8 sizes @4 and
               5 x u16 usable sizes @0xA (RecvItemMax 0x23A990); LSB has 18 x u8 @4 and 18 x u16 @0x24.
               s2c 0x050 equip: dropped when the item is not in the inventory (2007 has no wardrobes).
  core-c2s     c2s packets the 2007 client sends shorter or with a field missing, which LSB drops as "Bad packet size":
               0x061 status request 4 -> 8, 0x059 effect end 8 -> 16, 0x09B chocobo race 8 -> 12,
               0x01B world pass 0x1C -> 8, 0x102 extended job (BLU) 0xA0 -> 0xA4,
               0x0FA mog house layout 0x0C -> 0x10 (insert Category, FloorFlg at 7),
               0x0FE plant crop 8 -> 0x0C (insert Category at 7).
               (0x01A action is always fixed by ps2proxy.py itself; 0x0DD and 0x0E1/0x0E2/0x0E4 by ps2proxy_mp.)
  core-shop    s2c 0x03C shop list: 2007 entries are 8 bytes (LSB 12) and the 2007 table has 16 slots with no bounds
               check (RecvShopList 0x23D4D0 / RecvShopOpen 0x23D5C0); entries are shrunk, slots >= 16 dropped.
  core-index   entity indexes renumbered (see the core-index section) and models without a 2007 file replaced.
  core-emote   s2c 0x05A: Mode back from +0x16 (LSB) to +0x14 (RecvEmotionMes 0x194140).
  core-newids  s2c ids 0x110..0x1FF are dropped: the 2007 client has no handler and indexed an unbounded table with
               them (the zone-change crash to 0x190; pnach v30 also drops them client-side).

Run `python3 ps2proxy_core.py` for the unit tests (no server needed).
"""

import struct

# --------------------------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------------------------


def _hdr(pkt):
    return struct.unpack_from('<H', pkt, 0)[0]


def resize(pkt, new_len):
    """pkt cut or zero-padded to new_len (rounded up to 4) with the 7-bit size field updated."""
    new_len = (new_len + 3) & ~3
    p = bytearray(pkt[:new_len].ljust(new_len, b'\0'))
    struct.pack_into('<H', p, 0, (_hdr(p) & 0x1FF) | ((new_len // 4) << 9))
    return bytes(p)


def insert_at(pkt, off, data, want_len=None):
    p = bytes(pkt[:off]) + bytes(data) + bytes(pkt[off:])
    return resize(p, want_len or len(p))


class BitReader:
    """LSB-first bit reader (the FFXI action packet order: bit 0 of byte 0 first)."""

    def __init__(self, data, bitpos=0):
        self.v = int.from_bytes(bytes(data), 'little')
        self.n = len(data) * 8
        self.pos = bitpos

    def get(self, n):
        if self.pos + n > self.n:
            raise ValueError('0x028 bit stream too short (%d + %d > %d)' % (self.pos, n, self.n))
        x = (self.v >> self.pos) & ((1 << n) - 1)
        self.pos += n
        return x


class BitWriter:
    def __init__(self, prefix=b''):
        self.v = int.from_bytes(bytes(prefix), 'little')
        self.pos = len(prefix) * 8

    def put(self, x, n):
        self.v |= (x & ((1 << n) - 1)) << self.pos
        self.pos += n

    def bytes(self):
        return self.v.to_bytes((self.pos + 7) // 8, 'little')


# --------------------------------------------------------------------------------------------------------
# core-action: s2c 0x028
# --------------------------------------------------------------------------------------------------------

# (name, LSB bits, 2007 bits). Header and target fields are the same width in both.
A_HEAD = [('actor', 32), ('trg_sum', 6), ('res_sum', 4), ('cmd_no', 4), ('cmd_arg', 32), ('info', 32)]
A_TARGET = [('id', 32), ('result_sum', 4)]
A_RESULT_LSB = [('miss', 3), ('kind', 2), ('sub_kind', 12), ('info', 5), ('scale', 5), ('value', 17),
                ('message', 10), ('bit', 31)]
A_RESULT_2007 = [('miss', 3), ('kind', 2), ('sub_kind', 11), ('info', 4), ('scale', 5), ('value', 16),
                 ('message', 10), ('bit', 32)]
A_PROC_LSB = [('kind', 6), ('info', 4), ('value', 17), ('message', 10)]
A_PROC_2007 = [('kind', 6), ('info', 4), ('value', 14), ('message', 10)]
A_REACT = [('kind', 6), ('info', 4), ('value', 14), ('message', 10)]      # same in both


def _read_fields(r, spec):
    return {k: r.get(n) for k, n in spec}


def action_unpack(pkt, result_spec=A_RESULT_LSB, proc_spec=A_PROC_LSB):
    """Parse a 0x028 sub-packet (header + workSize byte, then the bit stream at byte 5)."""
    r = BitReader(pkt, 8 * 5)
    a = _read_fields(r, A_HEAD)
    a['targets'] = []
    for _ in range(a['trg_sum']):
        t = _read_fields(r, A_TARGET)
        t['results'] = []
        for _ in range(t['result_sum']):
            res = _read_fields(r, result_spec)
            res['proc'] = _read_fields(r, proc_spec) if r.get(1) else None
            res['react'] = _read_fields(r, A_REACT) if r.get(1) else None
            t['results'].append(res)
        a['targets'].append(t)
    return a


def _clamp(v, bits):
    return min(v, (1 << bits) - 1)


def action_pack(a, pid_hdr, result_spec=A_RESULT_2007, proc_spec=A_PROC_2007):
    """Build a 0x028 sub-packet from the parsed dict, with the given field widths (values clamped to fit)."""
    w = BitWriter(b'\0' * 5)
    for k, n in A_HEAD:
        w.put(a[k], n)
    for t in a['targets']:
        for k, n in A_TARGET:
            w.put(t[k], n)
        for res in t['results']:
            for k, n in result_spec:
                v = res[k]
                if k == 'sub_kind' and v >= (1 << n):
                    v = 0                          # animation id the 2007 client cannot have: no animation
                w.put(_clamp(v, n) if k in ('value',) else v, n)
            if res['proc']:
                w.put(1, 1)
                for k, n in proc_spec:
                    w.put(_clamp(res['proc'][k], n) if k == 'value' else res['proc'][k], n)
            else:
                w.put(0, 1)
            if res['react']:
                w.put(1, 1)
                for k, n in A_REACT:
                    w.put(res['react'][k], n)
            else:
                w.put(0, 1)
    body = bytearray(w.bytes())
    work = len(body)                               # workSize = bytes used from the packet start (LSB: same rule)
    body[4] = work & 0xFF
    body[0:4] = bytes(pid_hdr[0:4])                # id and sync number of the original (size set below)
    body = resize(bytes(body), work + 1)           # LSB: setSize(workSize + 1)
    return body


def s2c_action(pkt):
    if len(pkt) < 5 + 14:
        return None
    a = action_unpack(pkt)
    out = action_pack(a, pkt)
    return out


# --------------------------------------------------------------------------------------------------------
# core-status: s2c 0x037
# --------------------------------------------------------------------------------------------------------

def s2c_status(pkt):
    """LSB: BufStatus[32] @4 (low 8 bits, 0xFF = none) + 2 bits per icon @0x4C (bits 8-9).
    2007: same low bytes, 1 bit per icon @0x4C..0x4F (bit 8)."""
    if len(pkt) < 0x54:
        return None
    hi2 = int.from_bytes(pkt[0x4C:0x54], 'little')
    if hi2 == 0:
        return None                                  # nothing above 255: identical for the 2007 client
    p = bytearray(pkt)
    hi1 = 0
    for i in range(32):
        v = (hi2 >> (2 * i)) & 3
        if p[4 + i] == 0xFF:
            continue
        if v & 2:
            p[4 + i] = 0xFF                          # status id >= 512: no such icon in 2007, hide it
        elif v & 1:
            hi1 |= 1 << i
    p[0x4C:0x50] = hi1.to_bytes(4, 'little')
    p[0x50:0x54] = b'\0\0\0\0'
    return bytes(p)


# --------------------------------------------------------------------------------------------------------
# core-items
# --------------------------------------------------------------------------------------------------------

CONTAINERS_2007 = 5          # inventory, mog safe, storage, temporary, mog locker
SLOTS_2007 = 81              # 0xDEC / 0x2C


def _item_ok(container, index):
    return container < CONTAINERS_2007 and index < SLOTS_2007


def s2c_item_num(pkt):       # 0x01E: ItemNum u32 @4, Category @8, ItemIndex @9
    if len(pkt) >= 0x0A and not _item_ok(pkt[8], pkt[9]):
        return b''
    return None


def s2c_item_list(pkt):      # 0x01F: ItemNum @4, ItemNo @8, Category @0xA, ItemIndex @0xB
    if len(pkt) >= 0x0C and not _item_ok(pkt[0x0A], pkt[0x0B]):
        return b''
    return None


def s2c_item_attr(pkt):      # 0x020: ItemNum @4, Price @8, ItemNo @0xC, Category @0xE, ItemIndex @0xF
    if len(pkt) >= 0x10 and not _item_ok(pkt[0x0E], pkt[0x0F]):
        return b''
    return None


def s2c_item_max(pkt):
    """0x01C: 2007 = ItemNum[5] u8 @4, pad @9, ItemNum2[5] u16 @0xA. LSB = ItemNum[18] @4, ItemNum2[18] u16 @0x24."""
    if len(pkt) < 0x48:
        return None
    p = bytearray(pkt)
    usable = struct.unpack_from('<5H', pkt, 0x24)
    p[0x09] = 0
    struct.pack_into('<5H', p, 0x0A, *usable)
    return bytes(p)


def s2c_equip(pkt):          # 0x050: PropertyItemIndex @4, EquipKind @5, Category @6 (2007 reads @4/@5 only)
    if len(pkt) >= 7 and pkt[6] != 0 and pkt[4] != 0:
        return b''
    return None


SHOP_SLOTS_2007 = 16          # RecvShopOpen clears 0x34C bytes = 16 entries of 0x34 at zone+0x45FC; the party table follows


def s2c_shop_list(pkt):
    """0x03C. 2007 (RecvShopList 0x23D4D0): entries of 8 bytes from +8 {price u32, ItemNo u16, ShopIndex u8, pad}, count
    from the packet size, table slot = ShopIndex with no bounds check. LSB: 12-byte entries (adds Skill, GuildInfo).
    Entries are shrunk to 8 bytes; ShopIndex >= 16 would overwrite the party table and is dropped."""
    if len(pkt) < 8:
        return None
    n = (len(pkt) - 8) // 12
    out = bytearray(pkt[:8])
    kept = 0
    for i in range(n):
        price, item, idx = struct.unpack_from('<IHB', pkt, 8 + 12 * i)
        if item == 0 and price == 0:
            continue
        if idx >= SHOP_SLOTS_2007:
            continue
        out += struct.pack('<IHBB', price, item, idx, 0)
        kept += 1
    if kept == 0:
        return b''
    return resize(bytes(out), len(out))


def s2c_emote(pkt):
    """0x05A. 2007 (RecvEmotionMes 0x194140) reads Mode at +0x14; LSB inserted unknown14 there and moved Mode to +0x16."""
    if len(pkt) < 0x18:
        return None
    p = bytearray(pkt)
    p[0x14], p[0x15] = pkt[0x16], 0
    return bytes(p)


def s2c_drop_new_id(pkt):
    """s2c ids >= 0x110 (LSB sends 0x110, 0x119, ...) do not exist in 2007. The client indexes an unbounded
    handler table with them (the v29 crash, jump to 0x190); pnach v30 drops them client-side, this drops them
    before they are sent."""
    return b''


# --------------------------------------------------------------------------------------------------------
# core-c2s
# --------------------------------------------------------------------------------------------------------

def _pad_from(size_2007, size_lsb):
    def fix(pkt):
        if len(pkt) == size_2007:
            return resize(pkt, size_lsb)
        return None
    fix.__name__ = 'c2s_pad_%X_%X' % (size_2007, size_lsb)
    return fix


c2s_clistatus = _pad_from(0x04, 0x08)      # 0x061 ReqCliStatus 0x189C20: header only
c2s_effectend = _pad_from(0x08, 0x10)      # 0x059 effectpara @4; LSB adds 8 padding bytes
c2s_chocobo_race = _pad_from(0x08, 0x0C)   # 0x09B Param @4; LSB adds Kind @8 (0)
c2s_extended_job = _pad_from(0xA0, 0xA4)   # 0x102 BLU: SpellId..Spells[20] at the same offsets; unused tail


def c2s_friendpass(pkt):                   # 0x01B: 2007 sends 0x1C bytes with Para u16 @4; LSB wants 8
    if len(pkt) == 0x1C:
        return resize(pkt, 0x08)
    return None


MOG_SAFE = 1


def c2s_myroom_layout(pkt):
    """0x0FA (gcMyroomLayoutSet): ItemNo u16 @4, Index @6, x @7, y @8, z @9, v @0xA (0x0C).
    LSB: ItemNo @4, Index @6, Category @7, FloorFlg @8, x @9, y @0xA, z @0xB, v @0xC (0x10). Furniture was placed
    from the Mog Safe in 2007."""
    if len(pkt) == 0x0C:
        return insert_at(pkt, 7, bytes([MOG_SAFE, 0]), 0x10)
    return None


def c2s_plant_crop(pkt):
    """0x0FE (gcMyroomPlantCropSet): ItemNo @4, Index @6, CancellFlg @7 (8). LSB inserts Category @7 (0x0C)."""
    if len(pkt) == 0x08:
        return insert_at(pkt, 7, bytes([MOG_SAFE]), 0x0C)
    return None


# --------------------------------------------------------------------------------------------------------
# core-index: entity index (ActIndex / targid) renumbering, and model ids the 2007 client may not have
# --------------------------------------------------------------------------------------------------------
#
# The 2007 client has one actor table of 0x700 slots (0x59B870): NPCs/mobs < 0x300, PCs 0x300-0x5FF,
# pets/special 0x600-0x6FF (RecvCharNpc 0x18CAB0 rejects NPC indexes 0x300-0x5FF and >= 0x700).
# LSB: NPCs/mobs 0x000-0x3FF, PCs 0x400-0x6FF, dynamic entities (pets, trusts, fellows, spawned mobs)
# 0x700-0x8FF, handed out linearly (so they reach 0x8xx after enough spawns). Mapping LSB -> client:
#   < 0x300          unchanged
#   0x300 - 0x3FF    a free slot below 0x300 of that zone (static table ps2proxy_core_index.json, built by
#                    `ps2proxy_core.py --build-index-map`: slots LSB leaves empty, preferring ones the 2007
#                    entity list leaves empty too); none left -> unmapped
#   0x400 - 0x6FF    - 0x100 (PCs)
#   0x700 - 0x8FF    a free slot 0x600-0x6FF per client, given on first sight and freed on despawn
# Unmapped: the sub-packet is dropped (the client could not show that entity anyway). c2s is mapped back.
# UniqueNo (server ids) are not changed: PCs' is the character id, and LSB checks it against the index.

import json as _json
import os as _os

INDEX_MAP_FILE = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'ps2proxy_core_index.json')
_ZONE_SLOTS = None


def zone_slots():
    """{zone: {lsb_index: client_slot}} for LSB NPC/mob indexes 0x300-0x3FF."""
    global _ZONE_SLOTS
    if _ZONE_SLOTS is None:
        try:
            raw = _json.load(open(INDEX_MAP_FILE))['zones']
            _ZONE_SLOTS = {int(z): {int(k): v for k, v in m.items()} for z, m in raw.items()}
        except (OSError, ValueError, KeyError):
            _ZONE_SLOTS = {}
    return _ZONE_SLOTS


class IndexState:
    """Per zone client (ZoneClient) mapping state."""

    def __init__(self):
        self.zone = None
        self.dyn = {}           # LSB dynamic targid -> client slot 0x600-0x6FF
        self.dyn_rev = {}

    def new_zone(self, zone):
        self.zone = zone
        self.dyn.clear()
        self.dyn_rev.clear()

    def fwd(self, i, alloc=True):
        if i < 0x300:
            return i
        if i < 0x400:
            return zone_slots().get(self.zone, {}).get(i)
        if i < 0x700:
            return i - 0x100
        if i < 0x900:
            s = self.dyn.get(i)
            if s is None and alloc:
                for s in range(0x600, 0x700):
                    if s not in self.dyn_rev:
                        self.dyn[i] = s
                        self.dyn_rev[s] = i
                        break
                else:
                    return None
            return s
        return None

    def free(self, i):
        s = self.dyn.pop(i, None)
        if s is not None:
            self.dyn_rev.pop(s, None)

    def rev(self, j):
        if j < 0x300:
            inv = zone_slots().get(self.zone, {})
            for k, v in inv.items():
                if v == j:
                    return k
            return j
        if j < 0x600:
            return j + 0x100
        if j < 0x700:
            return self.dyn_rev.get(j, j + 0x100)
        return j


def _state(ctx):
    st = getattr(ctx, 'core_index', None)
    if st is None:
        st = IndexState()
        try:
            ctx.core_index = st
        except AttributeError:
            pass
    return st


# s2c index fields on LSB's layouts (offsets from LSB's own headers).
# kind: 'u16' plain, 'u32' plain, ('bits', off, shift, width) inside a u32, 'u16x5' array.
S2C_INDEX = {
    0x009: [(0x08, 'u16')], 0x00A: [(0x08, 'u16'), (0x18, 'face')], 0x00D: [(0x08, 'u16'), (0x18, 'face'), (0x3C, 'u16')],
    0x00E: [(0x08, 'u16'), (0x18, 'face')], 0x021: [(0x08, 'u16')], 0x022: [(0x0C, 'u16')], 0x027: [(0x08, 'u16')],
    0x029: [(0x14, 'u16'), (0x16, 'u16')], 0x02A: [(0x18, 'u16')], 0x02D: [(0x0C, 'u16'), (0x0E, 'u16')],
    0x02F: [(0x08, 'u16')], 0x030: [(0x08, 'u16')], 0x032: [(0x08, 'u16')], 0x033: [(0x08, 'u16')],
    0x034: [(0x28, 'u16')], 0x036: [(0x08, 'u16')], 0x037: [(0x34, 'pet')], 0x038: [(0x10, 'u16'), (0x12, 'u16')],
    0x039: [(0x10, 'u16'), (0x12, 'u16')], 0x03A: [(0x0C, 'u16'), (0x0E, 'u16')], 0x03B: [(0x08, 'u16')],
    0x043: [(0x08, 'u16')], 0x058: [(0x0C, 'u16')], 0x05A: [(0x0C, 'u16'), (0x0E, 'u16'), (0x2C, 'u16x5')],
    0x05B: [(0x14, 'u16')], 0x065: [(0x14, 'u16')], 0x067: [(0x06, 'u16'), (0x0C, 'u16')], 0x070: [(0x1C, 'u16')],
    0x078: [(0x0C, 'u16')], 0x0BF: [(0x0C, 'u32')], 0x0C8: [(0x08 + 12 * k + 4, 'u16') for k in range(20)],
    0x0C9: [(0x08, 'u16')], 0x0D2: [(0x12, 'u16'), (0x24, 'u16')], 0x0D3: [(0x0C, 'u16'), (0x10, 'u15')],
    0x0DC: [(0x08, 'u16')], 0x0DD: [(0x18, 'u16')], 0x0DF: [(0x14, 'u16')], 0x0E2: [(0x18, 'u16')],
    0x0F4: [(0x04, 'u16')], 0x0F5: [(0x12, 'u16')], 0x0F9: [(0x08, 'u16')], 0x108: [(0x0E, 'u16')],
    0x109: [(0x0C, 'u16'), (0x0E, 'u16')],
}
# c2s index fields (LSB layouts = the 2007 layouts at these offsets).
C2S_INDEX = {
    0x015: [(0x16, 'u16')], 0x016: [(0x04, 'u16')], 0x017: [(0x04, 'u16')], 0x01A: [(0x08, 'u16')],
    0x032: [(0x08, 'u16')], 0x036: [(0x3A, 'u16')], 0x037: [(0x0C, 'u16')], 0x05B: [(0x0C, 'u16')],
    0x05C: [(0x1C, 'u16')], 0x05D: [(0x08, 'u16')], 0x05E: [(0x14, 'u16')], 0x060: [(0x08, 'u16')],
    0x063: [(0x0C, 'u16')], 0x064: [(0x48, 'u16')], 0x06E: [(0x08, 'u16')], 0x071: [(0x08, 'u16')],
    0x0D8: [(0x04, 'u16')], 0x0DD: [(0x08, 'u32')], 0x0F5: [(0x04, 'u32')], 0x105: [(0x08, 'u16')],
}


def _get(p, off, kind):
    if kind in ('u16', 'u15'):
        v = struct.unpack_from('<H', p, off)[0]
        return v & 0x7FFF if kind == 'u15' else v
    if kind == 'u32':
        return struct.unpack_from('<I', p, off)[0]
    if kind == 'face':                                   # Flags0 bits 17..31 (facetarget)
        return struct.unpack_from('<I', p, off)[0] >> 17
    if kind == 'pet':                                    # 0x037 Flags2 bits 3..18 (PetIndex)
        return (struct.unpack_from('<I', p, off)[0] >> 3) & 0xFFFF
    raise ValueError(kind)


def _put(p, off, kind, v):
    if kind == 'u16':
        struct.pack_into('<H', p, off, v)
    elif kind == 'u15':
        struct.pack_into('<H', p, off, (struct.unpack_from('<H', p, off)[0] & 0x8000) | (v & 0x7FFF))
    elif kind == 'u32':
        struct.pack_into('<I', p, off, v)
    elif kind == 'face':
        w = struct.unpack_from('<I', p, off)[0]
        struct.pack_into('<I', p, off, (w & 0x1FFFF) | ((v & 0x7FFF) << 17))
    elif kind == 'pet':
        w = struct.unpack_from('<I', p, off)[0]
        struct.pack_into('<I', p, off, (w & ~(0xFFFF << 3) & 0xFFFFFFFF) | ((v & 0xFFFF) << 3))


def _fields(table, pid, p):
    if table is S2C_INDEX and pid == 0x0C8:
        stride = 8 if len(p) <= 8 + 8 * 20 else 12          # after mp-party (2007) or LSB's own layout
        for k in range(20):
            off = 8 + stride * k + 4
            if off + 2 <= len(p):
                yield off, 'u16'
        return
    for off, kind in table.get(pid, ()):
        if kind == 'u16x5':
            for k in range(5):
                if off + 2 * k + 2 <= len(p):
                    yield off + 2 * k, 'u16'
            continue
        size = 4 if kind in ('u32', 'face', 'pet') else 2
        if off + size <= len(p):
            yield off, kind


# Model ids (XiSkeletonActor::SetUp 0x1AB640 / 0x1ABAD0): the 2007 client uses id = model & 0xFFF;
# id < 1500 -> file 1300+id, 1500..2999 -> file 50875+(id-1500), >= 3000 -> model 0. Only the ids listed in
# the 2007 model id list (1153) have a file in the 2007 US data. A standard-look model not in that
# list is replaced: monsters by the Forest Hare model (268), NPCs by the Moogle model (82); both are in the list.
MODEL_LIST_2007 = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'pcsx2', 'npc_model_ids_2007_us.txt')
MODEL_MAX_2007 = 3031        # fallback rule only if the list file is missing
SAFE_MODEL_MOB = 268
SAFE_MODEL_NPC = 82
_MODELS_2007 = None


def models_2007():
    """Set of 2007 model ids with a file, or None when the list is not available (then the MAX rule is used)."""
    global _MODELS_2007
    if _MODELS_2007 is None:
        try:
            _MODELS_2007 = {int(l.split()[0]) for l in open(MODEL_LIST_2007, encoding='utf-8')
                            if l.strip() and not l.lstrip().startswith('#')}
        except (OSError, ValueError):
            _MODELS_2007 = set()
    return _MODELS_2007 or None


def model_ok_2007(model):
    ids = models_2007()
    if ids is None:
        return model <= MODEL_MAX_2007
    return (model & 0xFFF) in ids


MODEL_SUBS = {}              # (zone, UniqueNo, old model) -> new model (logged once each)


def _log(ctx, msg):
    if ctx is not None and hasattr(ctx, 'log'):
        ctx.log(ctx.tag, msg)


def s2c_index(ctx, pkt, pid=None):
    pid = pid if pid is not None else _hdr(pkt) & 0x1FF
    st = _state(ctx)
    p = bytearray(pkt)
    if pid == 0x00A and len(p) >= 0x34:
        st.new_zone(struct.unpack_from('<H', p, 0x30)[0])
    despawn_dyn = None
    for off, kind in _fields(S2C_INDEX, pid, p):
        v = _get(p, off, kind)
        if v == 0 and off != 0x08:
            continue                                       # empty optional fields (no pet, no target)
        if kind == 'face' and v == 0:
            continue
        m = st.fwd(v)
        if m is None:
            optional = (kind in ('face', 'pet') or pid == 0x0C8 or (pid == 0x05A and off >= 0x2C)
                        or (pid == 0x00D and off == 0x3C))
            if not optional:
                key = 'unmapped %03X %X' % (pid, v)
                if key not in STATS:
                    STATS[key] = 1
                    _log(ctx, 'core  index 0x%X (zone %s) has no 2007 slot: %03X dropped' % (v, st.zone, pid))
                return b''
            m = 0
        if pid == 0x00E and off == 0x08 and 0x700 <= v < 0x900 and p[0x0A] & 0x20:
            despawn_dyn = v
        _put(p, off, kind, m)
    if pid == 0x00E and len(p) >= 0x34:
        sub = struct.unpack_from('<H', p, 0x30)[0] & 7
        model = struct.unpack_from('<H', p, 0x32)[0]
        if sub in (0, 5, 6) and not model_ok_2007(model):
            mob = len(p) > 0x20 and (p[0x20] & 1)
            new = SAFE_MODEL_MOB if mob else SAFE_MODEL_NPC
            struct.pack_into('<H', p, 0x32, new)
            key = (st.zone, struct.unpack_from('<I', p, 4)[0], model)
            if key not in MODEL_SUBS:
                MODEL_SUBS[key] = new
                _log(ctx, 'core  model %d of %s %d (zone %s) has no 2007 model file: shown as model %d' % (
                    model, 'monster' if mob else 'NPC', key[1], st.zone, new))
    if despawn_dyn is not None:
        st.free(despawn_dyn)
    out = bytes(p)
    return None if out == pkt else out


s2c_index.wants_ctx = True


def c2s_index(ctx, pkt, pid=None):
    pid = pid if pid is not None else _hdr(pkt) & 0x1FF
    st = _state(ctx)
    p = bytearray(pkt)
    for off, kind in _fields(C2S_INDEX, pid, p):
        v = _get(p, off, kind)
        if v == 0:
            continue
        _put(p, off, kind, st.rev(v))
    out = bytes(p)
    return None if out == pkt else out


c2s_index.wants_ctx = True


def build_index_map(lsb_dir, dat_cache=None, out=INDEX_MAP_FILE, extra_ids=()):
    """Per zone: LSB NPC/mob indexes 0x300-0x3FF -> free slots below 0x300 (deterministic)."""
    import re as _re
    zdir = _os.path.join(lsb_dir, 'data', 'zones')
    per_zone = {}
    for z in sorted(_os.listdir(zdir)):
        for fn in ('npcs.yaml', 'mobs.yaml'):
            path = _os.path.join(zdir, z, fn)
            if _os.path.exists(path):
                for i in _re.findall(r'^  (\d{7,9}):', open(path, encoding='utf-8').read(), _re.M):
                    i = int(i)
                    per_zone.setdefault((i >> 12) & 0x1FF, set()).add(i & 0xFFF)
    for i in extra_ids:
        per_zone.setdefault((i >> 12) & 0x1FF, set()).add(i & 0xFFF)
    npc_targets = {}
    npc_map = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'ps2proxy_npc_ids.json')
    if _os.path.exists(npc_map):
        for z, d in _json.load(open(npc_map)).items():
            npc_targets[int(z)] = {int(v) & 0xFFF for v in d.get('map', {}).values()}
    zones, unmapped = {}, {}
    for zone, idx in sorted(per_zone.items()):
        high = sorted(i for i in idx if 0x300 <= i < 0x400)
        if not high:
            continue
        used07 = set()
        if dat_cache:
            p = _os.path.join(dat_cache, '%d.DAT' % (6720 + zone))
            if _os.path.exists(p):
                b = open(p, 'rb').read()
                for k in range(0, len(b) - 27, 28):
                    name = b[k:k + 24].split(b'\0')[0]
                    sid = struct.unpack_from('<I', b, k + 24)[0]
                    if name:
                        used07.add(sid & 0xFFF)
        taken = npc_targets.get(zone, set())                           # 2007 slots ps2proxy_npc moves NPCs into
        free = [s for s in range(1, 0x300) if s not in idx and s not in taken]   # slot 0 = "no entity" in many fields
        free = [s for s in free if s not in used07] + [s for s in free if s in used07]
        zones[str(zone)] = {str(i): s for i, s in zip(high, free)}
        if len(high) > len(free):
            unmapped[str(zone)] = high[len(free):]
    doc = {'about': 'LSB NPC/mob index 0x300-0x3FF -> client slot below 0x300, per zone (ps2proxy_core core-index). '
                    'Built from the server zone npc/mob lists and the 2007 entity lists.',
           'zones': zones, 'unmapped': unmapped}
    _json.dump(doc, open(out, 'w'), indent=0, sort_keys=True)
    return doc


# --------------------------------------------------------------------------------------------------------
# core-looks: humanoid look / gear model ids and static-model objects the 2007 client cannot load
# --------------------------------------------------------------------------------------------------------
#
# Humanoid looks (PCs in 0x00D and 0x051, "equipped"/"chocobo" NPCs in 0x00E SubKind 1/7): GrapIDTbl[9] =
# face | race << 8, then 8 gear values slot << 12 | id. XiSkeletonActor::SetUp (0x1AB914-0x1AB990) limits each id by
# slot: races 1-8 {face 32, head/body/hands/legs/feet 256, main/sub 512, range 256} (0x457700), races 29-31 64 for
# face..feet and 0 for weapons (0x457720); other races are treated as race 1. Every id below the limit has a file
# for every race, so an id at or above the limit becomes 0.
# Static-model objects (0x00E SubKind 4, LSB "ship"): XiModelActor::__ct (0x286750) loads file 0x7908 + id with no
# range check and crashes on a NULL resource. Valid ids: ps2proxy_core_objmodels.json (files that are real resource
# directories in the 2007 data); a packet with any other id is dropped.
# Runs FIRST among the s2c translations (before s2c-00d moves the 0x00D look), on LSB's layouts.

GEAR_CAPS = (32, 256, 256, 256, 256, 256, 512, 512, 256)
GEAR_CAPS_SPECIAL = (64, 64, 64, 64, 64, 64, 0, 0, 0)       # races 29-31
OBJ_MODEL_FILE = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'ps2proxy_core_objmodels.json')
_OBJ_VALID = None
LOOK_FIXES = {}


def obj_models_valid():
    global _OBJ_VALID
    if _OBJ_VALID is None:
        try:
            _OBJ_VALID = set(_json.load(open(OBJ_MODEL_FILE))['valid'])
        except (OSError, ValueError, KeyError):
            _OBJ_VALID = set()
    return _OBJ_VALID


def clamp_look(p, off):
    """GrapIDTbl[9] at p[off:off+18] clamped in place; returns a list of (slot, old, new) changes."""
    if off + 18 > len(p):
        return []
    tbl = list(struct.unpack_from('<9H', p, off))
    if tbl[8] == 0xFFFF:                     # costume / monstrosity marker: not a gear look
        return []
    race = tbl[0] >> 8
    caps = GEAR_CAPS_SPECIAL if 29 <= race <= 31 else GEAR_CAPS
    changes = []
    face = tbl[0] & 0xFF
    if face >= caps[0]:
        changes.append((0, tbl[0], tbl[0] & 0xFF00, caps[0]))
        tbl[0] &= 0xFF00
    for s in range(1, 9):
        v = tbl[s]
        if v & 0xFFF == 0:
            continue
        if (v & 0xFFF) >= caps[s]:
            nv = s << 12
            changes.append((s, v, nv, caps[s]))
            tbl[s] = nv
    if changes:
        struct.pack_into('<9H', p, off, *tbl)
    return changes


def s2c_looks(ctx, pkt, pid=None):
    pid = pid if pid is not None else _hdr(pkt) & 0x1FF
    p = bytearray(pkt)
    changes = []
    if pid == 0x00D and len(p) >= 0x5A:
        changes = clamp_look(p, 0x48)
    elif pid == 0x051:
        changes = clamp_look(p, 0x04)
    elif pid == 0x00E and len(p) >= 0x34:
        sub = struct.unpack_from('<H', p, 0x30)[0] & 7
        if sub in (1, 7):
            changes = clamp_look(p, 0x32)
        elif sub == 4 and len(p) >= 0x38:
            oid = struct.unpack_from('<I', p, 0x34)[0]
            if oid not in obj_models_valid():
                key = ('obj', struct.unpack_from('<I', p, 4)[0], oid)
                if key not in LOOK_FIXES:
                    LOOK_FIXES[key] = 1
                    _log(ctx, 'core  static-model object %d uses model %d (file %d), not a 2007 model resource: '
                              'not shown' % (key[1], oid, 0x7908 + oid))
                return b''
    if not changes:
        return None
    ent = struct.unpack_from('<I', p, 4)[0] if pid != 0x051 else 0
    for s, old, new, cap in changes:
        key = (pid, ent, s, old)
        if key not in LOOK_FIXES:
            LOOK_FIXES[key] = 1
            _log(ctx, 'core  %03X look of %d: %s value 0x%04X is beyond the 2007 limit %d -> 0x%04X' % (
                pid, ent, ('face', 'head', 'body', 'hands', 'legs', 'feet', 'main', 'sub', 'range')[s], old, cap, new))
    return bytes(p)


s2c_looks.wants_ctx = True


# --------------------------------------------------------------------------------------------------------
# Registration with ps2proxy
# --------------------------------------------------------------------------------------------------------

GROUPS = {
    'core-looks': ('humanoid gear/face ids beyond the 2007 per-slot limits -> 0; static-model objects without a 2007 '
                   'resource dropped (0x00D/0x00E/0x051, before s2c-00d)',
                   [('s2c', 0x00D, s2c_looks), ('s2c', 0x00E, s2c_looks), ('s2c', 0x051, s2c_looks)]),
    'core-index': ('s2c entity indexes renumbered into the 2007 actor table (NPC <0x300, PC 0x300-0x5FF, pets '
                   '0x600-0x6FF); models without a 2007 model file replaced',
                   [('s2c', pid, s2c_index) for pid in sorted(S2C_INDEX)]),
    'core-index-c2s': ('c2s entity indexes mapped back to LSB (runs first, before npc-ids)',
                       [('c2s', pid, c2s_index) for pid in sorted(C2S_INDEX)]),
    'core-action': ('s2c 0x028 actions re-packed to the 2007 bit widths (83-bit results)',
                    [('s2c', 0x028, s2c_action)]),
    'core-status': ('s2c 0x037 status-icon high bits 2 -> 1 per icon',
                    [('s2c', 0x037, s2c_status)]),
    'core-items': ('s2c 0x01C item max 2007 layout; 0x01E/0x01F/0x020/0x050 outside the 2007 containers dropped',
                   [('s2c', 0x01C, s2c_item_max), ('s2c', 0x01E, s2c_item_num), ('s2c', 0x01F, s2c_item_list),
                    ('s2c', 0x020, s2c_item_attr), ('s2c', 0x050, s2c_equip)]),
    'core-shop': ('s2c 0x03C shop list: 12 -> 8-byte entries, only the 16 slots the 2007 client has',
                  [('s2c', 0x03C, s2c_shop_list)]),
    'core-emote': ('s2c 0x05A emote: Mode moved back to +0x14', [('s2c', 0x05A, s2c_emote)]),
    'core-newids': ('s2c ids >= 0x110 (unknown to the 2007 client; crashed it before pnach v30) dropped',
                    [('s2c', pid, s2c_drop_new_id) for pid in range(0x110, 0x200)]),
    'core-c2s': ('c2s 0x061/0x059/0x09B/0x01B/0x102/0x0FA/0x0FE to the sizes and layouts LSB accepts',
                 [('c2s', 0x061, c2s_clistatus), ('c2s', 0x059, c2s_effectend), ('c2s', 0x09B, c2s_chocobo_race),
                  ('c2s', 0x01B, c2s_friendpass), ('c2s', 0x102, c2s_extended_job),
                  ('c2s', 0x0FA, c2s_myroom_layout), ('c2s', 0x0FE, c2s_plant_crop)]),
}
ALIASES = {'core': ['core-index-c2s', 'core-looks', 'core-index', 'core-action', 'core-status', 'core-items', 'core-c2s', 'core-shop', 'core-emote', 'core-newids']}

STATS = {}                   # hook name -> count of changed/dropped packets (for the log / tests)


def _adapt(fn, pid):
    def hook(ctx, pkt):
        if getattr(fn, 'wants_ctx', False):
            r = fn(ctx, pkt, pid)
            if r is not None:
                key = '%s %03X index' % ('drop' if r == b'' else 'fix', pid)
                STATS[key] = STATS.get(key, 0) + 1
            return r
        r = fn(pkt)
        if r is not None:
            key = '%s %03X' % ('drop' if r == b'' else 'fix', pid)
            n = STATS.get(key, 0) + 1
            STATS[key] = n
            if n == 1 and ctx is not None:
                what = ('translated to the 2007 layout' if r != b'' else
                        'dropped (id unknown to the 2007 client)' if pid >= 0x110 else
                        'dropped (outside the 2007 containers/slots)')
                ctx.log(ctx.tag, 'core  %03X %s (first time; counted silently from now on)' % (pid, what))
        return r
    hook.__name__ = fn.__name__
    return hook


def register(px):
    """Add the groups to ps2proxy's optional hooks and alias table (idempotent)."""
    for name, (desc, items) in GROUPS.items():
        if name in px.OPTIONAL_HOOKS:
            continue
        for direction, pid, fn in items:
            (px.c2s_hook if direction == 'c2s' else px.s2c_hook)(pid, optional=name, desc=desc)(_adapt(fn, pid))
    for alias, names in ALIASES.items():
        px.TRANSLATION_ALIASES.setdefault(alias, list(names))


# --------------------------------------------------------------------------------------------------------
# Unit tests (no server): python3 ps2proxy_core.py
# --------------------------------------------------------------------------------------------------------

def _lsb_action(a):
    """Pack like LSB's GP_SERV_COMMAND_BATTLE2::pack (85-bit results)."""
    return action_pack(a, b'\x28\x00\x00\x00', A_RESULT_LSB, A_PROC_LSB)


def _sample_action():
    res1 = dict(miss=0, kind=1, sub_kind=0x7FF, info=2, scale=3, value=1234, message=1, bit=0x12345678,
                proc=None, react=None)
    res2 = dict(miss=1, kind=0, sub_kind=5, info=0, scale=0, value=0, message=15, bit=0, proc=None,
                react=dict(kind=3, info=1, value=77, message=44))
    res3 = dict(miss=0, kind=2, sub_kind=300, info=1, scale=1, value=65535, message=2, bit=7,
                proc=dict(kind=2, info=3, value=500, message=163), react=None)
    t1 = dict(id=0x01000123, result_sum=2, results=[res1, res2])
    t2 = dict(id=0x01000456, result_sum=1, results=[res3])
    return dict(actor=0x0100ABCD, trg_sum=2, res_sum=0, cmd_no=1, cmd_arg=0x1B, info=0, targets=[t1, t2])


def unit_tests(verbose=True):
    results = []

    def check(name, cond):
        results.append((name, bool(cond)))
        if verbose:
            print('  %-60s %s' % (name, 'PASS' if cond else 'FAIL'))

    # 0x028: LSB -> 2007, then read back with the 2007 widths
    a = _sample_action()
    lsb = _lsb_action(a)
    check('0x028 LSB sample parses with LSB widths', action_unpack(lsb) == a)
    out = s2c_action(lsb)
    b = action_unpack(out, A_RESULT_2007, A_PROC_2007)
    check('0x028 2007 widths read back every field', b == a)
    check('0x028 size field matches the new length', ((_hdr(out) >> 9) * 4) == len(out))
    # misread without the fix: the 2007 reader on the LSB stream gets a wrong damage value
    try:
        wrong = action_unpack(lsb, A_RESULT_2007, A_PROC_2007)
        misread = wrong['targets'][0]['results'][0]['value'] != 1234
    except ValueError:
        misread = True
    check('0x028 unfixed LSB stream is misread by the 2007 widths', misread)
    big = _sample_action()
    big['targets'][0]['results'][0]['value'] = 200000
    big['targets'][0]['results'][0]['sub_kind'] = 0xABC
    big['targets'][1]['results'][0]['proc']['value'] = 99999
    o = action_unpack(s2c_action(_lsb_action(big)), A_RESULT_2007, A_PROC_2007)
    r0 = o['targets'][0]['results'][0]
    check('0x028 clamps value/proc value and drops a >11-bit animation',
          r0['value'] == 0xFFFF and r0['sub_kind'] == 0 and o['targets'][1]['results'][0]['proc']['value'] == 0x3FFF)

    # 0x037 icons
    p = bytearray(0x60)
    struct.pack_into('<H', p, 0, 0x037 | ((0x60 // 4) << 9))
    p[4:0x24] = b'\xff' * 32
    p[4] = 0x05                                   # id 0x105 in slot 0
    p[5] = 0x10                                   # id 0x010 in slot 1
    p[6] = 0x02                                   # id 0x202 in slot 2 (>= 512)
    p[7] = 0x03                                   # id 0x103 in slot 3
    hi = (1 << 0) | (2 << 4) | (1 << 6)           # 2-bit pairs: slot0=1, slot2=2, slot3=1
    p[0x4C:0x54] = hi.to_bytes(8, 'little')
    q = s2c_status(bytes(p))
    bits = int.from_bytes(q[0x4C:0x50], 'little')
    check('0x037 slot 0/3 keep bit 8, slot 1 plain, slot 2 (>=512) hidden',
          bits == 0b1001 and q[4] == 5 and q[5] == 0x10 and q[6] == 0xFF and q[7] == 3)
    check('0x037 unchanged when no id is above 255', s2c_status(bytes(p[:0x4C]) + bytes(8) + bytes(p[0x54:])) is None)

    # items
    def item_pkt(pid, size, cat_off, cat, idx):
        x = bytearray(size)
        struct.pack_into('<H', x, 0, pid | ((size // 4) << 9))
        x[cat_off], x[cat_off + 1] = cat, idx
        return bytes(x)
    check('0x020 inventory item passes', s2c_item_attr(item_pkt(0x020, 0x2C, 0x0E, 0, 5)) is None)
    check('0x020 satchel (5) item dropped', s2c_item_attr(item_pkt(0x020, 0x2C, 0x0E, 5, 5)) == b'')
    check('0x01F wardrobe (8) item dropped', s2c_item_list(item_pkt(0x01F, 0x10, 0x0A, 8, 1)) == b'')
    check('0x01E locker (4) slot 80 passes', s2c_item_num(item_pkt(0x01E, 0x0C, 0x08, 4, 80)) is None)
    m = bytearray(0x64)
    struct.pack_into('<H', m, 0, 0x01C | ((0x64 // 4) << 9))
    m[4:4 + 18] = bytes(range(31, 49))
    struct.pack_into('<18H', m, 0x24, *range(100, 118))
    mm = s2c_item_max(bytes(m))
    check('0x01C sizes stay, usable sizes moved to 0x0A',
          mm[4:9] == bytes(range(31, 36)) and struct.unpack_from('<5H', mm, 0x0A) == tuple(range(100, 105)))

    # c2s
    def c2s(pid, size, fill=b''):
        x = bytearray(size)
        struct.pack_into('<HH', x, 0, pid | ((size // 4) << 9), 0x1234)
        x[4:4 + len(fill)] = fill
        return bytes(x)
    r = c2s_myroom_layout(c2s(0x0FA, 0x0C, struct.pack('<HBBBBB', 0x0ABC, 7, 1, 2, 3, 4)))
    check('0x0FA 0x0C -> 0x10 with Category/FloorFlg inserted at 7',
          len(r) == 0x10 and struct.unpack_from('<HBBBBBBB', r, 4) == (0x0ABC, 7, 1, 0, 1, 2, 3, 4)
          and _hdr(r) >> 9 == 4 and struct.unpack_from('<H', r, 2)[0] == 0x1234)
    r = c2s_plant_crop(c2s(0x0FE, 0x08, struct.pack('<HBB', 0x0123, 9, 1)))
    check('0x0FE 8 -> 0x0C with Category inserted at 7',
          len(r) == 0x0C and struct.unpack_from('<HBBB', r, 4) == (0x0123, 9, 1, 1))
    check('0x061 4 -> 8', len(c2s_clistatus(c2s(0x061, 4))) == 8)
    check('0x059 8 -> 16', len(c2s_effectend(c2s(0x059, 8, b'\x01'))) == 16)
    check('0x01B 0x1C -> 8 keeps Para', c2s_friendpass(c2s(0x01B, 0x1C, b'\x01\x00'))[4:6] == b'\x01\x00')
    check('0x102 0xA0 -> 0xA4', len(c2s_extended_job(c2s(0x102, 0xA0))) == 0xA4)
    check('already-LSB-sized packets are left alone', c2s_clistatus(c2s(0x061, 8)) is None)
    check('s2c 0x110 dropped', s2c_drop_new_id(c2s(0x110, 0x14)) == b'')
    sh = bytearray(8 + 12 * 18)
    for i in range(18):
        struct.pack_into('<IHBBHH', sh, 8 + 12 * i, 100 + i, 4112 + i, i, 0, 7, 9)
    struct.pack_into('<H', sh, 0, 0x03C | ((len(sh) // 4) << 9))
    o = s2c_shop_list(bytes(sh))
    ents = [struct.unpack_from('<IHB', o, 8 + 8 * i) for i in range((len(o) - 8) // 8)]
    check('0x03C 18 LSB entries -> 16 x 8-byte entries, fields kept',
          len(ents) == 16 and ents[0] == (100, 4112, 0) and ents[15] == (115, 4127, 15) and _hdr(o) >> 9 == len(o) // 4)
    em = bytearray(0x28)
    em[0x14], em[0x16] = 5, 2
    check('0x05A Mode copied to +0x14', s2c_emote(bytes(em))[0x14] == 2)

    # ---- core-index
    class _Ctx:
        tag = 'T'
        def __init__(self):
            self.lines = []
        def log(self, tag, msg):
            self.lines.append(msg)
    cx = _Ctx()

    def s2c_pkt(pid, size, fields):
        x = bytearray(size)
        struct.pack_into('<HH', x, 0, pid | ((size // 4) << 9), 7)
        for off, fmt, val in fields:
            struct.pack_into(fmt, x, off, val)
        return bytes(x)
    zmap = zone_slots().get(116, {})
    login = s2c_pkt(0x00A, 0x104, [(4, '<I', 1234), (8, '<H', 0x400), (0x18, '<I', (0x401 << 17) | 5), (0x30, '<H', 116)])
    o = s2c_index(cx, login, 0x00A)
    check('index: 0x00A sets the zone, own index 0x400 -> 0x300, facetarget 0x401 -> 0x301',
          _state(cx).zone == 116 and struct.unpack_from('<H', o, 8)[0] == 0x300
          and struct.unpack_from('<I', o, 0x18)[0] == ((0x301 << 17) | 5))
    if zmap:
        lsb_i, slot = sorted(zmap.items())[0]
        npc = s2c_pkt(0x00E, 0x48, [(4, '<I', 0x1000000 | (116 << 12) | lsb_i), (8, '<H', lsb_i), (0x0A, '<B', 0x0F)])
        o = s2c_index(cx, npc, 0x00E)
        check('index: zone 116 NPC 0x%X -> free slot 0x%X, UniqueNo unchanged' % (lsb_i, slot),
              struct.unpack_from('<H', o, 8)[0] == slot and struct.unpack_from('<I', o, 4)[0] == struct.unpack_from('<I', npc, 4)[0])
        act = c2s(0x01A, 0x10, struct.pack('<IHHI', 1, slot, 0, 0))
        check('index: c2s 0x01A slot 0x%X -> LSB 0x%X' % (slot, lsb_i),
              struct.unpack_from('<H', c2s_index(cx, act, 0x01A), 8)[0] == lsb_i)
    un = s2c_pkt(0x00E, 0x48, [(4, '<I', 0x1000000 | (116 << 12) | 0x305), (8, '<H', 0x305), (0x0A, '<B', 0x0F)])
    check('index: NPC without a 2007 slot -> 0x00E dropped', s2c_index(cx, un, 0x00E) == b'')
    pet = s2c_pkt(0x00E, 0x48, [(4, '<I', 0x1070123), (8, '<H', 0x7F3), (0x0A, '<B', 0x0F)])
    o = s2c_index(cx, pet, 0x00E)
    pet_slot = struct.unpack_from('<H', o, 8)[0]
    pet2 = s2c_pkt(0x00E, 0x48, [(4, '<I', 0x1070124), (8, '<H', 0x850), (0x0A, '<B', 0x0F)])
    slot2 = struct.unpack_from('<H', s2c_index(cx, pet2, 0x00E), 8)[0]
    check('index: dynamic 0x7F3 / 0x850 -> 0x600 / 0x601', pet_slot == 0x600 and slot2 == 0x601)
    msg = s2c_pkt(0x029, 0x1C, [(0x14, '<H', 0x850), (0x16, '<H', 0x401)])
    o = s2c_index(cx, msg, 0x029)
    check('index: 0x029 caster 0x850 -> 0x601, target 0x401 -> 0x301',
          struct.unpack_from('<HH', o, 0x14) == (0x601, 0x301))
    st37 = s2c_pkt(0x037, 0x60, [(0x34, '<I', (0x7F3 << 3) | 5)])
    o = s2c_index(cx, st37, 0x037)
    check('index: 0x037 PetIndex 0x7F3 -> 0x600, other flag bits kept',
          struct.unpack_from('<I', o, 0x34)[0] == ((0x600 << 3) | 5))
    act = c2s(0x01A, 0x10, struct.pack('<IHHI', 1, 0x601, 2, 0))
    check('index: c2s target 0x601 -> LSB 0x850, 0x301 -> 0x401',
          struct.unpack_from('<H', c2s_index(cx, act, 0x01A), 8)[0] == 0x850
          and struct.unpack_from('<H', c2s_index(cx, c2s(0x01A, 0x10, struct.pack('<IHHI', 1, 0x301, 2, 0)), 0x01A), 8)[0] == 0x401)
    gone = s2c_pkt(0x00E, 0x48, [(4, '<I', 0x1070123), (8, '<H', 0x7F3), (0x0A, '<B', 0x20)])
    s2c_index(cx, gone, 0x00E)
    again = s2c_pkt(0x00E, 0x48, [(4, '<I', 0x1070125), (8, '<H', 0x8FE), (0x0A, '<B', 0x0F)])
    check('index: despawn frees slot 0x600, next pet reuses it',
          struct.unpack_from('<H', s2c_index(cx, again, 0x00E), 8)[0] == 0x600)
    mob = s2c_pkt(0x00E, 0x48, [(4, '<I', 0x1074010), (8, '<H', 0x010), (0x0A, '<B', 0x1F), (0x20, '<I', 1),
                                (0x30, '<H', 0), (0x32, '<H', 3585)])
    o = s2c_index(cx, mob, 0x00E)
    npc2 = s2c_pkt(0x00E, 0x48, [(4, '<I', 0x1074011), (8, '<H', 0x011), (0x0A, '<B', 0x1F), (0x32, '<H', 3174)])
    o2 = s2c_index(cx, npc2, 0x00E)
    ok_m = s2c_pkt(0x00E, 0x48, [(4, '<I', 0x1074012), (8, '<H', 0x012), (0x0A, '<B', 0x1F), (0x32, '<H', 268)])
    check('model: monster 3585 -> 268, NPC 3174 -> 82, model 268 untouched, substitutions logged',
          struct.unpack_from('<H', o, 0x32)[0] == SAFE_MODEL_MOB and struct.unpack_from('<H', o2, 0x32)[0] == SAFE_MODEL_NPC
          and s2c_index(cx, ok_m, 0x00E) is None and sum('no 2007 model file' in l for l in cx.lines) == 2)
    ids07 = models_2007() or set()
    below = s2c_pkt(0x00E, 0x48, [(4, '<I', 0x1074013), (8, '<H', 0x013), (0x0A, '<B', 0x1F), (0x20, '<I', 1),
                                  (0x32, '<H', 2920)])
    ob = s2c_index(cx, below, 0x00E)
    check('model: the 2007 list is loaded (%d ids, Hare 268 and Moogle 82 in it); 2920 (<3000, no file) -> 268'
          % len(ids07), len(ids07) > 1000 and 268 in ids07 and 82 in ids07
          and ob is not None and struct.unpack_from('<H', ob, 0x32)[0] == SAFE_MODEL_MOB)
    listed = sorted(i for i in ids07 if 1500 <= i < 3000)[:1]
    if listed:
        lp = s2c_pkt(0x00E, 0x48, [(4, '<I', 0x1074014), (8, '<H', 0x014), (0x0A, '<B', 0x1F), (0x32, '<H', listed[0])])
        check('model: listed id %d (1500-2999 range) kept' % listed[0], s2c_index(cx, lp, 0x00E) is None)
    tbl = bytearray(8 + 12 * 20)
    struct.pack_into('<HH', tbl, 0, 0x0C8 | ((len(tbl) // 4) << 9), 0)
    struct.pack_into('<IH', tbl, 8, 1234, 0x400)
    struct.pack_into('<IH', tbl, 20, 99, 0x402)
    o = s2c_index(cx, bytes(tbl), 0x0C8)
    check('index: 0x0C8 party table entries 0x400/0x402 -> 0x300/0x302 (LSB layout, before mp-party)',
          struct.unpack_from('<H', o, 12)[0] == 0x300 and struct.unpack_from('<H', o, 24)[0] == 0x302)
    tbl8 = bytearray(8 + 8 * 20)
    struct.pack_into('<HH', tbl8, 0, 0x0C8 | ((len(tbl8) // 4) << 9), 0)
    struct.pack_into('<IH', tbl8, 8, 1234, 0x400)
    struct.pack_into('<IH', tbl8, 16, 99, 0x402)
    o = s2c_index(cx, bytes(tbl8), 0x0C8)
    check('index: 0x0C8 after mp-party (8-byte entries) mapped too',
          struct.unpack_from('<H', o, 12)[0] == 0x300 and struct.unpack_from('<H', o, 20)[0] == 0x302)
    cx2 = _Ctx()
    s2c_index(cx2, login, 0x00A)
    check('index: dynamic slots are per client and reset on zone-in', _state(cx2).dyn == {})

    # ---- core-looks
    cl = _Ctx()
    pc = bytearray(0x64)
    struct.pack_into('<HH', pc, 0, 0x00D | ((0x64 // 4) << 9), 1)
    struct.pack_into('<I', pc, 4, 99)
    struct.pack_into('<9H', pc, 0x48, (1 << 8) | 5, 0x1000 | 300, 0x2000 | 12, 0x3000 | 255, 0x4000 | 256, 0x5000,
                     0x6000 | 511, 0x7000 | 600, 0x8000 | 300)
    o = s2c_looks(cl, bytes(pc), 0x00D)
    check('looks: 0x00D head 300 / legs 256 / sub 600 / range 300 -> 0; body 12, hands 255, main 511 kept',
          struct.unpack_from('<9H', o, 0x48) == ((1 << 8) | 5, 0x1000, 0x2000 | 12, 0x3000 | 255, 0x4000, 0x5000,
                                                  0x6000 | 511, 0x7000, 0x8000))
    gl = bytearray(0x18)
    struct.pack_into('<HH', gl, 0, 0x051 | ((0x18 // 4) << 9), 1)
    struct.pack_into('<9H', gl, 4, (2 << 8) | 40, 0x1001, 0x2002, 0x3003, 0x4004, 0x5005, 0x6006, 0x7000, 0x8000)
    o = s2c_looks(cl, bytes(gl), 0x051)
    check('looks: 0x051 face 40 (>= 32) -> 0, gear kept', struct.unpack_from('<H', o, 4)[0] == (2 << 8)
          and struct.unpack_from('<H', o, 6)[0] == 0x1001)
    costume = bytearray(gl)
    struct.pack_into('<9H', costume, 4, 0x1234, 0, 0, 0, 0, 0, 0, 0, 0xFFFF)
    check('looks: costume marker (0xFFFF) left alone', s2c_looks(cl, bytes(costume), 0x051) is None)
    npc_eq = bytearray(0x48)
    struct.pack_into('<HH', npc_eq, 0, 0x00E | ((0x48 // 4) << 9), 1)
    struct.pack_into('<IH', npc_eq, 4, 17735742, 0x3E)
    struct.pack_into('<H', npc_eq, 0x30, 1)
    struct.pack_into('<9H', npc_eq, 0x32, (3 << 8) | 1, 0x1000 | 388, 0x2001, 0x3000, 0x4005, 0x5005, 0x6000 | 140,
                     0x7000, 0x8000)
    o = s2c_looks(cl, bytes(npc_eq), 0x00E)
    check('looks: 0x00E equipped NPC head 388 -> 0, main 140 kept',
          struct.unpack_from('<H', o, 0x34)[0] == 0x1000 and struct.unpack_from('<H', o, 0x3E)[0] == 0x6000 | 140)
    sp = bytearray(npc_eq)
    struct.pack_into('<9H', sp, 0x32, (31 << 8) | 0x14, 0x1000 | 70, 0x2014, 0x3000, 0x4014, 0x5014, 0x6000 | 5, 0, 0)
    o = s2c_looks(cl, bytes(sp), 0x00E)
    check('looks: special race 31 uses its own limits (head 70 >= 64 -> 0, main cap 0 -> 0)',
          struct.unpack_from('<H', o, 0x34)[0] == 0x1000 and struct.unpack_from('<H', o, 0x3E)[0] == 0x6000)
    ship = bytearray(0x48)
    struct.pack_into('<HH', ship, 0, 0x00E | ((0x48 // 4) << 9), 1)
    struct.pack_into('<IH', ship, 4, 17735961, 0x119)
    struct.pack_into('<HHI', ship, 0x30, 4, 0, 379)
    ok_ship = bytearray(ship)
    struct.pack_into('<I', ok_ship, 0x34, 21)
    check('looks: static-model object 379 (no 2007 resource) dropped, 21 kept; logged once',
          s2c_looks(cl, bytes(ship), 0x00E) == b'' and s2c_looks(cl, bytes(ok_ship), 0x00E) is None
          and len(obj_models_valid()) > 2000 and sum('static-model object' in l for l in cl.lines) == 1)
    return results




if __name__ == '__main__' and '--build-index-map' in __import__('sys').argv:
    import sys as _sys
    _root = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..'))   # release: not used
    _extra = []
    try:
        _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
        import lsb_db as _db
        _extra = [int(r[0]) for r in _db.query('SELECT mobid FROM mob_spawn_points')]
    except Exception as _e:                                                      # noqa: BLE001
        print('(DB mob_spawn_points not read: %s)' % _e)
    _doc = build_index_map(_os.path.join(_root, 'work', 'lsb'),
                           _os.path.join(_root, 'work', 'lsb_textids', 'out', 'dat_cache'), extra_ids=_extra)
    print('zones with LSB indexes 0x300-0x3FF: %d; unmapped (no free slot): %s' % (
        len(_doc['zones']), {z: len(v) for z, v in _doc['unmapped'].items()}))
    raise SystemExit(0)

if __name__ == '__main__':
    print('ps2proxy_core unit tests')
    res = unit_tests()
    bad = [n for n, ok in res if not ok]
    print('OVERALL: %s' % ('PASS' if not bad else 'FAIL (%d)' % len(bad)))
    raise SystemExit(1 if bad else 0)
