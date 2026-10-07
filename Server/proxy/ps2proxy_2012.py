#!/usr/bin/env python3
"""ps2proxy_2012 - packet translation between LandSandBoat and the 2012 PS2 FFXI client (the Seekers of Adoulin disc's
INSTALL.ELF). Loaded by ps2proxy.py (register(px) at import); selected with `ps2proxy.py --client 2012`,
which replaces the 2007 default set (core, mp, s2c-00d) by the 2012 set below. `--client 2007` (default) is unchanged.

Every layout was read from the 2012 engine and compared with the 2007 engine and LSB's packet structs.

  c12-action   s2c 0x028: the 2012 reader (0x2D1C60) takes sub_kind 12, info 4, scale 5, value 17, message 10, bit 32
               per result, added effect 6/4/17/10, reaction 6/4/14/10. LSB: info 5 / bit 31. Re-packed (info keeps its
               low 4 bits, as for 2007).
  c12-items    s2c 0x01E/0x01F/0x020 outside the 2012 containers (7 bags x 81 slots: inventory, safe, storage,
               temporary, locker, satchel, sack) dropped; 0x050 equip from outside the inventory dropped;
               0x01C item max: 2012 = ItemNum[7] u8 @4, ItemNum2[7] u16 @0x14 (RecvItemMax 0x23AC60); LSB 18 @4 / 18 @0x24.
  c12-00d      s2c 0x00D other PCs: 2012 reads the look table @0x44 and the name @0x56 (RecvCharPc 0x18C140); LSB @0x48
               / @0x5A: LSB bytes 0x44..0x47 (post-2012 flags) removed.
  c12-index    entity indexes: 2012 = LSB for NPCs (< 0x400) and PCs (0x400-0x6FF); its actor table ends at 0x7FF
               (RecvCharNpc 0x18DF10 rejects >= 0x800), LSB hands out dynamic entities 0x700-0x8FF: those get a free
               slot 0x700-0x7FF per client (freed on despawn). c12-index-c2s maps them back.
  c12-chat     s2c 0x017: 2012 RecvStdChat (0x23EB00) = Kind@4, Attr@5, sName@8, Mes@0x18 (LSB Mes@0x17): one byte
               inserted; kinds >= 0x1B (not in its 0x1B-entry table) mapped like mp-chat. c2s 0x0B6 tell = 2007 layout
               (mp-chat's c2s_tell).
  c12-party    alliance kind 2 <-> 5 as in 2007 (the c2s senders are the 2007 code); s2c 0x0DD member: 2012 =
               LSB 0x04..0x21 (ZoneNo u16 @0x20) + Name @0x22 (RecvGroupList 0x253740; LSB has 6 job bytes first);
               s2c 0x0C8 table: 12-byte entries like LSB (RecvGroupTbl 0x253320), only Kind @4 converted.
  c12-text     OPTIONAL (not default): message ids in s2c 0x036/0x02A/0x027 from the ids installed in LSB for the 2007
               client to the 2012 ids. Only for an
               LSB running the 2007 text profile; with the 2012 profile it is not needed.
Unchanged from 2007 and reused: core-shop (RecvShopList identical), core-c2s (senders unchanged), core-newids (the
2012 handler tables are still 0x110 long), mp-linkshell, mp-check, npc-ids (with the 2012 map), and the search relay
with the 2012 area width (10 bits both ways; the name length is still 4 bits in the 2012 query builder 0x25F470).
Not needed for 2012 (and not in its default set): core-status, core-emote, core-index, s2c-00d, the 2007 core-items.

Unit tests (no server): python3 ps2proxy_2012.py
"""
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
MAPS = os.path.join(HERE, 'maps')   # release: Server/proxy/maps
NPC_MAP_2012 = os.path.join(MAPS, 'npc_id_map_2012.json')
TEXT_MAP_2012 = os.path.join(MAPS, 'textid_2007_to_2012.json')

try:
    import ps2proxy_core as core
    import ps2proxy_mp as mp
except ImportError:                                  # pragma: no cover
    import sys
    sys.path.insert(0, HERE)
    import ps2proxy_core as core
    import ps2proxy_mp as mp

resize = core.resize
STATS = {}

# ---------------------------------------------------------------------------------------------------- c12-action
A_RESULT_2012 = [('miss', 3), ('kind', 2), ('sub_kind', 12), ('info', 4), ('scale', 5), ('value', 17),
                 ('message', 10), ('bit', 32)]
A_PROC_2012 = [('kind', 6), ('info', 4), ('value', 17), ('message', 10)]


def s2c_action(ctx, pkt, pid=0x028):
    if len(pkt) < 5 + 14:
        return None
    a = core.action_unpack(pkt)
    # 1 Oct 2026: actor/target ids through the zone's id map (npc-ids: shifted NPCs and, since today, monsters), so
    # damage, animations and messages reach the entity the 2012 client knows under its own id.
    try:
        import ps2proxy_npc as npc
        z = npc._zone(ctx) if ctx is not None else None
    except Exception:
        z = None
    if z:
        fwd = z[0]
        a['actor'] = fwd.get(a['actor'], a['actor'])
        for t in a['targets']:
            t['id'] = fwd.get(t['id'], t['id'])
    return core.action_pack(a, pkt, A_RESULT_2012, A_PROC_2012)
s2c_action.wants_ctx = True


# ---------------------------------------------------------------------------------------------------- c12-items
CONTAINERS_2012 = 7
SLOTS_2012 = 81


def _item_ok(c, i):
    return c < CONTAINERS_2012 and i < SLOTS_2012


def s2c_item_num(pkt):
    if len(pkt) >= 0x0A and not _item_ok(pkt[8], pkt[9]):
        return b''
    return None


def s2c_item_list(pkt):
    if len(pkt) >= 0x0C and not _item_ok(pkt[0x0A], pkt[0x0B]):
        return b''
    return None


def s2c_item_attr(pkt):
    if len(pkt) >= 0x10 and not _item_ok(pkt[0x0E], pkt[0x0F]):
        return b''
    return None


def s2c_item_max(pkt):
    """0x01C: LSB ItemNum[18] u8 @4, ItemNum2[18] u16 @0x24 -> 2012 ItemNum[7] @4, ItemNum2[7] u16 @0x14."""
    if len(pkt) < 0x48:
        return None
    p = bytearray(pkt)
    usable = struct.unpack_from('<7H', pkt, 0x24)
    p[0x0B:0x14] = bytes(9)
    struct.pack_into('<7H', p, 0x14, *usable)
    p[0x22:0x24] = b'\0\0'
    return bytes(p)


s2c_equip = core.s2c_equip


# ---------------------------------------------------------------------------------------------------- c12-00d
def s2c_char_pc(pkt):
    if len(pkt) <= 0x48:
        return None
    body = pkt[:0x44] + pkt[0x48:]
    return resize(body, len(body))


# ---------------------------------------------------------------------------------------------------- c12-index
class IndexState2012:
    def __init__(self):
        self.zone = None
        self.dyn, self.dyn_rev = {}, {}

    def new_zone(self, zone):
        self.zone = zone
        self.dyn.clear()
        self.dyn_rev.clear()

    def fwd(self, i, alloc=True):
        if i < 0x700:
            return i
        if i < 0x900:
            s = self.dyn.get(i)
            if s is None and alloc:
                for s in range(0x700, 0x800):
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
        if 0x700 <= j < 0x800:
            return self.dyn_rev.get(j, j)
        return j


def _state(ctx):
    st = getattr(ctx, 'c12_index', None)
    if st is None:
        st = IndexState2012()
        try:
            ctx.c12_index = st
        except AttributeError:
            pass
    return st


def s2c_index(ctx, pkt, pid):
    st = _state(ctx)
    p = bytearray(pkt)
    if pid == 0x00A and len(p) >= 0x34:
        st.new_zone(struct.unpack_from('<H', p, 0x30)[0])
    despawn = None
    for off, kind in core._fields(core.S2C_INDEX, pid, p):
        v = core._get(p, off, kind)
        if v < 0x700:
            continue
        m = st.fwd(v)
        if m is None:
            optional = kind in ('face', 'pet') or pid == 0x0C8 or (pid == 0x05A and off >= 0x2C) or (pid == 0x00D and off == 0x3C)
            if not optional:
                STATS['drop %03X index' % pid] = STATS.get('drop %03X index' % pid, 0) + 1
                return b''
            m = 0
        if pid == 0x00E and off == 0x08 and p[0x0A] & 0x20:
            despawn = v
        core._put(p, off, kind, m)
    if despawn is not None:
        st.free(despawn)
    out = bytes(p)
    return None if out == pkt else out


def c2s_index(ctx, pkt, pid):
    st = _state(ctx)
    p = bytearray(pkt)
    for off, kind in core._fields(core.C2S_INDEX, pid, p):
        v = core._get(p, off, kind)
        if 0x700 <= v < 0x800:
            core._put(p, off, kind, st.rev(v))
    out = bytes(p)
    return None if out == pkt else out


s2c_index.wants_ctx = c2s_index.wants_ctx = True


# ---------------------------------------------------------------------------------------------------- c12-chat / party
def s2c_chat(pkt):
    """0x017 LSB {Kind@4, Attr@5, Data@6, sName@8[15], Mes@0x17} -> 2012 {..., sName@8, Mes@0x18}."""
    if len(pkt) < 0x17:
        return None
    p = bytearray(pkt[:0x17])
    k = p[4]
    if k >= 0x1B:
        k = mp.CHAT_KIND_MAP.get(k, k)
        if k >= 0x1B:
            k = 0
    p[4] = k
    msg = bytes(pkt[0x17:]).split(b'\0', 1)[0][:0x96]
    body = bytes(p) + b'\0' + msg + b'\0'
    return resize(body, len(body))


def s2c_group_list(pkt):
    """0x0DD LSB: ..., ZoneNo u16 @0x20, 6 job bytes @0x22, Name @0x28 -> 2012: ..., ZoneNo @0x20, Name @0x22."""
    if len(pkt) < 0x28:
        return None
    p = bytearray(pkt[:0x22])
    p[0x1C] = mp._kind_lsb_to_2007(p[0x1C])
    p += bytes(pkt[0x28:0x38]).split(b'\0', 1)[0][:16].ljust(16, b'\0')
    return resize(bytes(p), len(p))


def s2c_group_tbl(pkt):
    """0x0C8: 2012 = LSB's 12-byte entries; only the alliance Kind @4 (5 -> 2)."""
    if len(pkt) < 8 or pkt[4] != mp.ALLIANCE_LSB:
        return None
    p = bytearray(pkt)
    p[4] = mp.ALLIANCE_2007
    return bytes(p)


# ---------------------------------------------------------------------------------------------------- c12-text
_TEXT = None
MESNUM_OFF = {0x036: 0x0A, 0x027: 0x0A, 0x02A: 0x1A}


def _text_map():
    global _TEXT
    if _TEXT is None:
        try:
            raw = json.load(open(TEXT_MAP_2012))['map']
            _TEXT = {int(z): {int(k): v for k, v in m.items()} for z, m in raw.items()}
        except (OSError, ValueError, KeyError):
            _TEXT = {}
    return _TEXT


def s2c_text(ctx, pkt, pid):
    zone = getattr(getattr(ctx, 'c12_index', None), 'zone', None) or getattr(ctx, 'npc_zone', None)
    off = MESNUM_OFF[pid]
    if zone is None or len(pkt) < off + 2:
        return None
    raw = struct.unpack_from('<H', pkt, off)[0]
    new = _text_map().get(zone, {}).get(raw & 0x7FFF)
    if new is None:
        return None
    p = bytearray(pkt)
    struct.pack_into('<H', p, off, (raw & 0x8000) | (new & 0x7FFF))
    return bytes(p)


s2c_text.wants_ctx = True


# ---------------------------------------------------------------------------------------------------- search (2012)
def translate_query_block_2012(block):
    """2012 query block: name length 4 bits (-> 5 for LSB), area already 10 bits."""
    size = block[0]
    r = mp.BitReader(block[1:1 + size])
    w = mp.BitWriter()
    try:
        while r.left() >= 5:
            if r.only_padding_left():
                break
            t = r.get(5)
            w.put(t, 5)
            if t in mp._REQ_HEADERLESS:
                n = mp._REQ_RAW[t]
                if n:
                    w.put(r.get(n), n)
                continue
            sort, present = r.get(1), r.get(1)
            w.put(sort, 1)
            w.put(present, 1)
            if not present:
                continue
            if t == 0x00:
                n = r.get(4)
                w.put(n, 5)
                for _ in range(n):
                    w.put(r.get(7), 7)
            elif t == 0x01:
                w.put(r.get(10), 10)
            elif t in mp._REQ_FIXED:
                for n in mp._REQ_FIXED[t]:
                    w.put(r.get(n), n)
            else:
                raise ValueError('unknown query field type 0x%02X' % t)
    except (EOFError, ValueError):
        return bytes(block[:1 + size])
    body = w.bytes()
    return bytes([len(body)]) + body


# ---------------------------------------------------------------------------------------------------- c12-models
# OPTIONAL: the 2012 engine loads skeleton models
# only for ids < 3000 (XiSkeletonActor::SetUp 0x1ADC0C: id & 0xFFF; >= 3000 -> model 0). The PC-only models of
# conversion batch B with LSB ids >= 3000 sit in free PS2 slots 2850-2999 of the pc2ps2b drive; this group rewrites
# the standard-look model id of s2c 0x00E (SubKind u16 @0x30 & 7 in 0/5/6, model u16 @0x32, low 12 bits) from the LSB
# id to that slot. Only valid on a drive that carries batch B: switch it on with `server_tool.py proxy-2012 --models
# pc2ps2b` (= ps2proxy.py --client 2012 --translate c12-models). Map file: PS2PROXY_MODEL_MAP or the default below.
MODEL_MAP_2012 = os.path.join(MAPS, 'proxy_model_renumber_2012.json')
_MODELS = None
MODEL_SEEN = set()                  # (UniqueNo, old, new) logged once each


def model_map():
    global _MODELS
    if _MODELS is None:
        path = os.environ.get('PS2PROXY_MODEL_MAP') or MODEL_MAP_2012
        raw = json.load(open(path))['map']
        m = {}
        for k, v in raw.items():
            old, new = int(k), int(v['ps2'])
            if not (3000 <= old <= 0xFFF and 0 < new < 3000):
                raise ValueError('model map %s: %d -> %d outside the 2012 rule' % (path, old, new))
            m[old] = new
        if len(set(m.values())) != len(m) or set(m.values()) & set(m):
            raise ValueError('model map %s: slots not unique' % path)
        _MODELS = m
    return _MODELS


def s2c_models(ctx, pkt, pid):
    if len(pkt) < 0x34:
        return None
    sub = struct.unpack_from('<H', pkt, 0x30)[0] & 7
    model = struct.unpack_from('<H', pkt, 0x32)[0]
    if sub not in (0, 5, 6):
        return None
    new = model_map().get(model & 0xFFF)
    if new is None:
        return None
    p = bytearray(pkt)
    struct.pack_into('<H', p, 0x32, (model & 0xF000) | new)
    key = (struct.unpack_from('<I', p, 4)[0], model & 0xFFF, new)
    if key not in MODEL_SEEN:
        MODEL_SEEN.add(key)
        if ctx is not None and hasattr(ctx, 'log'):
            ctx.log(ctx.tag, 'c12   model %d of entity %d -> PS2 slot %d (batch B, c12-models)' % (key[1], key[0], new))
    return bytes(p)
s2c_models.wants_ctx = True


# ---------------------------------------------------------------------------------------------------- c12-badfx
# 1 Oct 2026: converted PC models with particle meshes turned into VU models (d3m->vum)
# can place a VU DMA packet at an 8-byte aligned address (model 2478, file 51853 = the "blank" effect NPCs of Bastok
# Markets/Mines, Lower Jeuno, Northern San d'Oria, Norg, Lower Delkfutt's Tower): the VIF1 chain then reads a garbage tag
# and the 2012 client freezes. Until the converter pads those packets, s2c 0x00E of an
# entity whose standard-look model (SubKind 0/5/6, model u16 @0x32) is in maps/bad_fx_models_2012.json is
# dropped, i.e. the NPC/mob is not shown. Runs before c12-models (it compares LSB model ids). PS2PROXY_BADFX=off disables it.
BADFX_FILE = os.path.join(MAPS, 'bad_fx_models_2012.json')
_BADFX = None
BADFX_SEEN = set()


def badfx_models():
    global _BADFX
    if _BADFX is None:
        try:
            _BADFX = {int(k) for k in json.load(open(os.environ.get('PS2PROXY_BADFX_FILE') or BADFX_FILE))['models']}
        except (OSError, ValueError, KeyError):
            _BADFX = set()
        if os.environ.get('PS2PROXY_BADFX', '').lower() == 'off':
            _BADFX = set()
    return _BADFX


def s2c_badfx(ctx, pkt, pid):
    if len(pkt) < 0x34:
        return None
    sub = struct.unpack_from('<H', pkt, 0x30)[0] & 7
    if sub not in (0, 5, 6):
        return None
    model = struct.unpack_from('<H', pkt, 0x32)[0] & 0xFFF
    if model not in badfx_models():
        return None
    ent = struct.unpack_from('<I', pkt, 4)[0]
    if (ent, model) not in BADFX_SEEN:
        BADFX_SEEN.add((ent, model))
        if ctx is not None and hasattr(ctx, 'log'):
            ctx.log(ctx.tag, 'c12   entity %d uses converted model %d with an unsafe effect (c12-badfx): not shown' % (ent, model))
    return b''
s2c_badfx.wants_ctx = True


# ---------------------------------------------------------------------------------------------------- registration
GROUPS = {
    'c12-badfx': ('s2c 0x00E of NPCs/mobs using converted models with unsafe VU effects dropped (freeze fix, 1 Oct 2026)',
                  [('s2c', 0x00E, s2c_badfx)]),
    'c12-action': ('s2c 0x028 actions re-packed to the 2012 widths (info 4, bit 32)', [('s2c', 0x028, s2c_action)]),
    'c12-items': ('s2c 0x01C item max 2012 layout (7 bags); 0x01E/0x01F/0x020/0x050 outside the 2012 containers dropped',
                  [('s2c', 0x01C, s2c_item_max), ('s2c', 0x01E, s2c_item_num), ('s2c', 0x01F, s2c_item_list),
                   ('s2c', 0x020, s2c_item_attr), ('s2c', 0x050, s2c_equip)]),
    'c12-00d': ('s2c 0x00D other PCs to the 2012 layout (look 0x48->0x44, name 0x5A->0x56)', [('s2c', 0x00D, s2c_char_pc)]),
    'c12-index': ('s2c dynamic entity indexes 0x700-0x8FF into the 2012 slots 0x700-0x7FF',
                  [('s2c', pid, s2c_index) for pid in sorted(core.S2C_INDEX)]),
    'c12-index-c2s': ('c2s dynamic entity indexes mapped back to LSB', [('c2s', pid, c2s_index) for pid in sorted(core.C2S_INDEX)]),
    'c12-chat': ('chat: s2c 0x017 to the 2012 layout (Mes @0x18); c2s 0x0B6 tell as 2007',
                 [('c2s', 0x0B6, mp.c2s_tell), ('s2c', 0x017, s2c_chat)]),
    'c12-party': ('party/alliance: kind 2<->5 (c2s as 2007), s2c 0x0DC as 2007, 0x0DD/0x0C8 2012 layouts',
                  [('c2s', 0x06E, mp.c2s_group_solicit), ('c2s', 0x06F, mp.c2s_group_leave),
                   ('c2s', 0x070, mp.c2s_group_breakup), ('c2s', 0x071, mp.c2s_group_strike),
                   ('c2s', 0x077, mp.c2s_group_change2), ('s2c', 0x0DC, mp.s2c_group_solicit),
                   ('s2c', 0x0DD, s2c_group_list), ('s2c', 0x0C8, s2c_group_tbl)]),
    'c12-models': ('OPTIONAL (pc2ps2b drive only): s2c 0x00E model ids >= 3000 -> converted PS2 slots 2850-2999',
                   [('s2c', 0x00E, s2c_models)]),
    'c12-text': ('OPTIONAL: message ids installed-2007 -> 2012 in s2c 0x036/0x02A/0x027',
                 [('s2c', pid, s2c_text) for pid in sorted(MESNUM_OFF)]),
}
ALIASES = {'c12': ['c12-badfx', 'c12-index', 'c12-action', 'c12-items', 'c12-00d', 'core-shop', 'core-c2s', 'core-newids'],
           'c12-mp': ['c12-chat', 'c12-party', 'mp-linkshell', 'mp-check']}
# the translation set of `ps2proxy.py --client 2012` (same order rules as the 2007 set: c2s index first, NPC ids before
# the index renumbering)
DEFAULT_2012 = ['c12-index-c2s', 'c12-mp', 'npc', 'c12']


def _adapt(fn, pid):
    def hook(ctx, pkt):
        r = fn(ctx, pkt, pid) if getattr(fn, 'wants_ctx', False) else fn(pkt)
        if r is not None:
            key = '%s %03X %s' % ('drop' if r == b'' else 'fix', pid, fn.__name__)
            n = STATS.get(key, 0) + 1
            STATS[key] = n
            if n == 1 and ctx is not None and hasattr(ctx, 'log'):
                ctx.log(ctx.tag, 'c12   %03X %s (%s; first time, counted silently from now on)'
                        % (pid, 'dropped' if r == b'' else 'translated to the 2012 layout', fn.__name__))
        return r
    hook.__name__ = fn.__name__
    return hook


def register(px):
    for name, (desc, items) in GROUPS.items():
        if name in px.OPTIONAL_HOOKS:
            continue
        for direction, pid, fn in items:
            (px.c2s_hook if direction == 'c2s' else px.s2c_hook)(pid, optional=name, desc=desc)(_adapt(fn, pid))
    for alias, names in ALIASES.items():
        px.TRANSLATION_ALIASES.setdefault(alias, list(names))


def apply_client(cfg, px, log=None):
    """Called by ps2proxy.main for --client 2012: 2012 NPC id map, 2012 search widths. Returns the default set."""
    import ps2proxy_npc as npc
    if not os.environ.get('PS2PROXY_NPC_MAP'):
        npc.MAP_FILE = NPC_MAP_2012
        npc._MAP = None
    mp.translate_query_block = translate_query_block_2012
    rep = dict(mp._REP_2007); rep[0x01] = [10]; mp._REP_2007 = rep   # 2012 reply decoder reads the area as 10 bits
    if log:
        log('proxy', 'client 2012 (Adoulin engine): NPC map %s; search area 10 bits' % npc.MAP_FILE)
    return list(DEFAULT_2012)


# ---------------------------------------------------------------------------------------------------- unit tests
def unit_tests():
    ok = []
    # action: an LSB action re-packed to 2012 widths reads back with the 2012 widths
    a = core._sample_action()
    lsb = core._lsb_action(a)
    out = s2c_action(None, lsb)
    back = core.action_unpack(out, A_RESULT_2012, A_PROC_2012)
    r1 = back['targets'][0]['results'][0]
    ok.append(('0x028 value 1234 / sub_kind 0x7FF kept (12/17 bits)', r1['value'] == 1234 and r1['sub_kind'] == 0x7FF))
    r3 = back['targets'][1]['results'][0]
    ok.append(('0x028 added-effect value 500 kept (17 bits)', r3['proc']['value'] == 500))
    ok.append(('0x028 bit field 0x12345678 kept', r1['bit'] == 0x12345678))
    # item max
    im = bytearray(0x48); im[0:2] = struct.pack('<H', 0x1C | (0x48 // 4) << 9)
    im[4:4 + 18] = bytes(range(80, 98)); struct.pack_into('<18H', im, 0x24, *range(30, 48))
    o = s2c_item_max(bytes(im))
    ok.append(('0x01C 7 sizes @4, 7 usable @0x14', list(o[4:11]) == list(range(80, 87)) and struct.unpack_from('<7H', o, 0x14) == tuple(range(30, 37))))
    ok.append(('0x01F satchel (5) kept, case (7) dropped',
               s2c_item_list(bytes([0x1F, 0, 0, 0] + [0] * 6 + [5, 3])) is None and s2c_item_list(bytes([0x1F, 0, 0, 0] + [0] * 6 + [7, 3])) == b''))
    # 0x00D
    pc = bytes(range(256))[:0x70]
    pc = struct.pack('<H', 0x0D | (0x70 // 4) << 9) + pc[2:]
    o = s2c_char_pc(pc)
    ok.append(('0x00D look @0x44 / name @0x56 = LSB 0x48 / 0x5A', o[0x44] == pc[0x48] and o[0x56] == pc[0x5A] and len(o) == 0x6C))
    # chat
    ch = struct.pack('<HHBBH', 0x17, 0, 26, 1, 0) + b'Habex'.ljust(15, b'\0') + b'hello\0'
    o = s2c_chat(ch)
    ok.append(('0x017 yell kept (26), name @8, text @0x18', o[4] == 26 and o[8:13] == b'Habex' and o[0x18:0x1D] == b'hello'))
    o = s2c_chat(struct.pack('<HHBBH', 0x17, 0, 27, 0, 0) + b'X'.ljust(15, b'\0') + b'y\0')
    ok.append(('0x017 LS2 (27) shown as linkshell (5)', o[4] == 5))
    # party list
    gl = bytearray(0x3C); gl[0x1C] = 5; struct.pack_into('<H', gl, 0x20, 231); gl[0x28:0x2D] = b'Nobu\0'
    o = s2c_group_list(bytes(gl))
    ok.append(('0x0DD zone u16 @0x20, name @0x22, alliance kind 2', struct.unpack_from('<H', o, 0x20)[0] == 231 and o[0x22:0x26] == b'Nobu' and o[0x1C] == 2))
    # index
    class Ctx:
        tag = 'T'
        def log(self, *a):
            pass
    c = Ctx()
    z = bytearray(0x104); struct.pack_into('<H', z, 0x30, 231); s2c_index(c, bytes(z), 0x00A)
    npc = bytearray(0x48); struct.pack_into('<H', npc, 0, 0x0E | (0x48 // 4) << 9); struct.pack_into('<H', npc, 8, 0x812)
    o = s2c_index(c, bytes(npc), 0x00E)
    slot = struct.unpack_from('<H', o, 8)[0]
    ok.append(('dynamic 0x812 -> slot 0x7xx', 0x700 <= slot < 0x800))
    ok.append(('PC 0x400 unchanged', s2c_index(c, bytes(z[:0x10]).ljust(0x40, b'\0'), 0x009) is None))
    t = bytearray(0x10); struct.pack_into('<H', t, 0, 0x1A | (0x10 // 4) << 9); struct.pack_into('<H', t, 8, slot)
    ok.append(('c2s slot mapped back to 0x812', struct.unpack_from('<H', c2s_index(c, bytes(t), 0x01A), 8)[0] == 0x812))
    # search
    w = mp.BitWriter(); w.put(1, 5); w.put(0, 1); w.put(1, 1); w.put(0x2A5, 10); body = w.bytes()
    q = translate_query_block_2012(bytes([len(body)]) + body)
    r = mp.BitReader(q[1:]); ok.append(('search area 10 bits kept', (r.get(5), r.get(1), r.get(1), r.get(10)) == (1, 0, 1, 0x2A5)))
    # c12-models (optional group; real map of batch B when present)
    try:
        mm = model_map()
    except (OSError, ValueError, KeyError) as e:
        mm = None
        ok.append(('model map loads (%s)' % e, False))
    if mm:
        old, new = sorted(mm.items())[0]
        def npc(sub, model):
            b = bytearray(0x48); struct.pack_into('<H', b, 0, 0x0E | (0x48 // 4) << 9); struct.pack_into('<I', b, 4, 17000001)
            struct.pack_into('<H', b, 0x30, sub); struct.pack_into('<H', b, 0x32, model); return bytes(b)
        o = s2c_models(None, npc(0, old), 0x00E)
        ok.append(('0x00E model %d -> slot %d (SubKind 0)' % (old, new), o is not None and struct.unpack_from('<H', o, 0x32)[0] == new))
        o = s2c_models(None, npc(0x0005, 0x1000 | old), 0x00E)
        ok.append(('0x00E high bits kept, SubKind 5', o is not None and struct.unpack_from('<H', o, 0x32)[0] == 0x1000 | new))
        ok.append(('0x00E SubKind 1 (equipment look) untouched', s2c_models(None, npc(1, old), 0x00E) is None))
        ok.append(('0x00E model < 3000 untouched', s2c_models(None, npc(0, 2406), 0x00E) is None))
        free = next(i for i in range(3000, 4096) if i not in mm)
        ok.append(('0x00E unmapped model %d untouched' % free, s2c_models(None, npc(0, free), 0x00E) is None))
        ok.append(('model map: %d entries, all slots < 3000 and unique' % len(mm), len(mm) > 0))
        ok.append(('c12-models not in the default 2012 set', 'c12-models' not in DEFAULT_2012 and
                   all('c12-models' not in v for v in ALIASES.values())))
    for n, v in ok:
        print('  %-58s %s' % (n, 'PASS' if v else 'FAIL'))
    return all(v for _, v in ok)


if __name__ == '__main__':
    import sys
    sys.exit(0 if unit_tests() else 1)
