#!/usr/bin/env python3
"""ps2proxy_mp - person-to-person (multiplayer) translation between the 2007 PS2 FFXI client and LandSandBoat.

Loaded by ps2proxy.py (register(px) at import). Everything here comes from reading the 2007 engine
(INSTALL.ELF, Vana'diel Collection build; function names from research/engine_atlas/functions/i_vc2007.tsv),
the JP 2002 engine's DWARF struct layouts (work/b13_mp/gp_structs_jp2002.txt) and LSB's packet structs.
Details and evidence: research/reports/26_multiplayer.md.

Zone packets (hooks, enabled by name with ps2proxy --translate NAME; the "mp" group is on by default):

  mp-chat       c2s 0x0B6 tell: 2007 {Dammy@4, sName@5[15], Mes@0x14} -> LSB {3@4, 0@5, sName@6[15], Mes@0x15}
                s2c 0x017 chat: LSB {Kind@4, Attr@5, Data@6, sName@8, Mes@0x17} -> 2007 {Attr@4, sName@5, Kind@0x14,
                Mes@0x15}; chat kinds the 2007 client does not know (yell, LS2, system 3, unity/assist) are mapped
                to the nearest old kind.
  mp-party      alliance Kind is 2 on the 2007 client and 5 on LSB (c2s 0x06E/0x06F/0x070/0x071/0x077, s2c 0x0DC/0x0C8);
                c2s 0x071 kick: LSB requires UniqueNo = ActIndex = 0 (kick by name), the 2007 client fills them;
                s2c 0x0DD party member: LSB ZoneNo u16@0x20 + jobs + Name@0x28 -> 2007 ZoneNo u8@0x1F, Name@0x20;
                s2c 0x0C8 party table: LSB 20 x 12-byte entries -> 2007 20 x 8-byte entries (zone as u8).
  mp-linkshell  c2s 0x0C3 make pearl: add LinkshellId=1; c2s 0x0C4 equip: 0x18 -> 0x1C (Category, padding, LinkshellId);
                c2s 0x0E1/0x0E2/0x0E4 LS message: insert Category/ItemIndex/padding at 6 (0x8C -> 0x90);
                s2c 0x0E0: LSB {LinkshellNum@4, ItemIndex@5} -> 2007 {ItemIndex@4} (LS2 updates dropped).
  mp-check      c2s 0x0DD /check: 0x0C -> 0x10 (Kind 0 = check); s2c 0x0C9 answer: LSB's general block (flag 1)
                moved to the 2007 offsets, LSB's 8-item equipment block (flag 3) split into one 2007 packet per item.

Search server (TCP, --search-port, default 54242): the proxy rewrites the search address in lobby 0x0B to itself
and relays to xi_search. Requests and replies are MD5-sealed and Blowfish-encrypted with a key the proxy can
derive (a fixed 16-byte key + a 4-byte value sent in clear + a 4-byte nonce), so it can translate:
  request   query block: name length 4 -> 5 bits, area code 8 -> 10 bits (the 2007 builder at 0x25EF80);
  reply     entries: area 10 -> 8 bits; field types the 2007 decoder (0x260270) does not know (0x16 flags2,
            0x17 language) are dropped, because it would misread every bit after them.
"""

import hashlib
import socket
import struct
import threading
import time
import traceback

# --------------------------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------------------------

ALLIANCE_2007 = 2
ALLIANCE_LSB = 5


def _hdr(pkt):
    return struct.unpack_from('<H', pkt, 0)[0]


def resize(pkt, new_len):
    """pkt cut or zero-padded to new_len (rounded up to 4) with the 7-bit size field updated."""
    new_len = (new_len + 3) & ~3
    p = bytearray(pkt[:new_len].ljust(new_len, b'\0'))
    struct.pack_into('<H', p, 0, (_hdr(p) & 0x1FF) | ((new_len // 4) << 9))
    return bytes(p)


def _kind_2007_to_lsb(k):
    return ALLIANCE_LSB if k == ALLIANCE_2007 else k


def _kind_lsb_to_2007(k):
    return ALLIANCE_2007 if k == ALLIANCE_LSB else k


# --------------------------------------------------------------------------------------------------------
# mp-chat
# --------------------------------------------------------------------------------------------------------

def c2s_tell(pkt):
    """0x0B6 (gcChatNameSend 0x23E600): name at 5 (<= 15 chars), message at 0x14, size 0x15 + len."""
    if len(pkt) < 0x15:
        return None
    if pkt[4] == 3 and pkt[5] == 0 and len(pkt) >= 0x16:
        return None                                   # already in LSB layout (a PC-style client)
    name = bytes(pkt[5:0x14])
    msg = bytes(pkt[0x14:]).split(b'\0', 1)[0][:0x96]
    body = bytes([3, 0]) + name + msg + b'\0'
    return resize(pkt[:4] + body, 4 + len(body))


# LSB CHAT_MESSAGE_TYPE -> a kind the 2007 RecvStdChat (0x23E820, jump table of 0x1A kinds) prints
CHAT_KIND_MAP = {26: 1,        # yell -> shout
                 27: 5, 28: 16,  # linkshell 2 -> linkshell
                 29: 6,        # system 3 -> system 1
                 30: 5, 31: 16, 32: 16,
                 33: 0, 34: 0, 35: 0}


def s2c_chat(pkt):
    """0x017 (RecvStdChat 0x23E820 reads Attr@4 bit0, sName@5[15], Kind@0x14, Mes@0x15; DWARF GP_SERV_CHAT_STD)."""
    if len(pkt) < 0x17:
        return None
    kind, attr = pkt[4], pkt[5]
    kind = CHAT_KIND_MAP.get(kind, kind)
    if kind >= 0x1A:
        kind = 0
    name = bytes(pkt[8:0x17])
    msg = bytes(pkt[0x17:]).split(b'\0', 1)[0][:0x96]
    body = bytes([attr]) + name + bytes([kind]) + msg + b'\0'
    return resize(pkt[:4] + body, 4 + len(body))


# --------------------------------------------------------------------------------------------------------
# mp-party
# --------------------------------------------------------------------------------------------------------

def _c2s_kind_at(off):
    def fix(pkt):
        if len(pkt) <= off or pkt[off] != ALLIANCE_2007:
            return None
        p = bytearray(pkt)
        p[off] = ALLIANCE_LSB
        return bytes(p)
    return fix


c2s_group_solicit = _c2s_kind_at(0x0A)        # 0x06E gcGroupSolicitReqSet: UniqueNo@4, ActIndex@8, Kind@0xA
c2s_group_leave = _c2s_kind_at(0x04)          # 0x06F gcGroupLeaveSet: Kind@4
c2s_group_breakup = _c2s_kind_at(0x04)        # 0x070 gcGroupBreakupSet: Kind@4
c2s_group_change2 = _c2s_kind_at(0x14)        # 0x077 GP_CLI_GROUP_CHANGE2: sName@4, Kind@0x14, ChangeKind@0x15


def c2s_group_strike(pkt):
    """0x071 kick. gcGroupStrikeSet (0x252140) fills UniqueNo/ActIndex of the member; LSB's validator requires
    both 0 and kicks by the name at 0xC (gcGroupStrike2Set, the by-name variant, already sends zeros)."""
    if len(pkt) < 0x1C:
        return None
    p = bytearray(pkt)
    changed = False
    if any(p[4:0x0A]):
        p[4:0x0A] = b'\0' * 6
        changed = True
    if p[0x0A] == ALLIANCE_2007:
        p[0x0A] = ALLIANCE_LSB
        changed = True
    return bytes(p) if changed else None


def s2c_group_solicit(pkt):
    """0x0DC invite: 2007 (0x252B00 and YkWndPartyList 0x37AFB0) = LSB layout except Kind@0xB (2 = alliance)."""
    if len(pkt) <= 0x0B or pkt[0x0B] != ALLIANCE_LSB:
        return None
    p = bytearray(pkt)
    p[0x0B] = ALLIANCE_2007
    return bytes(p)


def s2c_group_list(pkt):
    """0x0DD member (RecvGroupList 0x253360): 2007 keeps LSB's 0x04..0x1E, then ZoneNo u8@0x1F, Name@0x20[16]."""
    if len(pkt) < 0x28:
        return None
    p = bytearray(pkt[:0x1F])
    p[0x1C] = _kind_lsb_to_2007(p[0x1C])
    zone = struct.unpack_from('<H', pkt, 0x20)[0]
    p.append(zone & 0xFF)
    name = bytes(pkt[0x28:0x38]).split(b'\0', 1)[0][:16]
    p += name.ljust(16, b'\0')
    return resize(p, len(p))


def s2c_group_tbl(pkt):
    """0x0C8 party table (RecvGroupTbl 0x252F40): Kind@4; 20 entries of 8 bytes at 8:
    UniqueNo u32, ActIndex u16, flags u8 (same bit order as LSB), ZoneNo u8. LSB entries are 12 bytes."""
    if len(pkt) < 0x08 + 12:
        return None
    n = min(20, (len(pkt) - 8) // 12)
    p = bytearray(0xA8)
    p[0:4] = pkt[0:4]
    p[4] = _kind_lsb_to_2007(pkt[4])
    for i in range(n):
        o = 8 + 12 * i
        uniq, act, flags = struct.unpack_from('<IHB', pkt, o)
        zone = struct.unpack_from('<H', pkt, o + 8)[0]
        struct.pack_into('<IHBB', p, 8 + 8 * i, uniq, act, flags, zone & 0xFF)
    return resize(p, 0xA8)


# --------------------------------------------------------------------------------------------------------
# mp-linkshell
# --------------------------------------------------------------------------------------------------------

def c2s_comlink_make(pkt):
    """0x0C3 (gcGroupComlinkMakeSet 0x2528B0): State@4 only; LSB also wants LinkshellId@5 in {1, 2}."""
    if len(pkt) < 6 or pkt[5] in (1, 2):
        return None
    p = bytearray(resize(pkt, 8))
    p[5] = 1
    return bytes(p)


def c2s_comlink_active(pkt):
    """0x0C4 equip/create (gcGroupComlinkActiveSet 0x2526E0): rgba@4, ItemIndex@6, ActiveFlg@7, name@8[15], 0x18 B.
    LSB: rgba@4, ItemIndex@6, Category@7, ActiveFlg@8, pad, sComLinkName@0xC[15], LinkshellId@0x1B, 0x1C B."""
    if len(pkt) != 0x18:
        return None
    p = bytearray(0x1C)
    p[0:4] = pkt[0:4]
    p[4:7] = pkt[4:7]
    p[7] = 0                                          # container: inventory
    p[8] = pkt[7]
    p[0x0C:0x1B] = pkt[8:0x17]
    p[0x1B] = 1                                       # linkshell 1 (the 2007 client has one slot)
    return resize(p, 0x1C)


def c2s_lsmsg(pkt):
    """0x0E1/0x0E2/0x0E4 (0x253ED0/0x253F90/0x254000/0x254090): bits@4, bits@5, seqId@6, uniqNo@8, sMessage@0xC,
    0x8C B. LSB inserts Category@6, ItemIndex@7, padding@8 (0x90 B); LinkshellId stays in byte 5 bits 6-7 (0 = LS1)."""
    if len(pkt) != 0x8C:
        return None
    p = bytearray(pkt[:6]) + b'\0\0\0\0' + bytearray(pkt[6:])
    return resize(p, 0x90)


def s2c_comlink(pkt):
    """0x0E0 (0x2537C0 reads ItemIndex@4 only). LSB: LinkshellNum@4, ItemIndex@5, Category@6."""
    if len(pkt) < 7:
        return None
    if pkt[4] == 2:
        return b''                                    # second linkshell: the 2007 client has no such slot
    p = bytearray(pkt)
    p[4] = pkt[5]
    p[5] = p[6] = 0
    return bytes(p)


# --------------------------------------------------------------------------------------------------------
# mp-check
# --------------------------------------------------------------------------------------------------------

def c2s_equip_inspect(pkt):
    """0x0DD (gcEquipStartInspect 0x23DA60): UniqueNo@4, ActIndex@8, 0x0C B; LSB adds Kind@0xC (0 = check)."""
    if len(pkt) != 0x0C:
        return None
    return resize(pkt, 0x10)


def s2c_equip_inspect(pkt):
    """0x0C9 /check result. RecvEquipInspect (0x23DFE0): OptionFlag@0xA = 0: one item per packet (ItemNo@0xC,
    EquipKind@0xE, 0..15); 1: general (linkshell item@0xE, colour@0x10, jobs@0x12, linkshell name@0x14[15],
    levels@0x23). LSB sends flag 1 {ItemNo@0xE, name@0x10[16], colour@0x20, job@0x22, lvl@0x24, ...} and flag 3
    {EquipCount@0xB, 8 x {ItemNo u16, EquipKind u8, pad, Data[24]} at 0xC}; flag 3 becomes one flag-0 packet per item."""
    if len(pkt) < 0x0C:
        return None
    flag = pkt[0x0A]
    if flag == 1 and len(pkt) >= 0x26:
        p = bytearray(0x30)
        p[0:0x0B] = pkt[0:0x0B]
        p[0x0E:0x10] = pkt[0x0E:0x10]
        p[0x10:0x12] = pkt[0x20:0x22]
        p[0x12:0x14] = pkt[0x22:0x24]
        p[0x14:0x23] = pkt[0x10:0x1F]
        p[0x23:0x25] = pkt[0x24:0x26]
        return resize(p, 0x30)
    if flag == 3:
        n = min(pkt[0x0B], 8, (len(pkt) - 0x0C) // 28)
        out = b''
        for i in range(n):
            o = 0x0C + 28 * i
            item, kind = struct.unpack_from('<HB', pkt, o)
            if kind >= 16:
                continue
            p = bytearray(0x10)
            p[0:0x0A] = pkt[0:0x0A]
            struct.pack_into('<HB', p, 0x0C, item, kind)
            out += resize(p, 0x10)
        return out
    return None


def s2c_servmes_empty(pkt):
    """6 Oct 2026 (2016 host build): s2c 0x04D server-message fragment with an EMPTY message (size_total @0x0C == 0;
    value1 @6 == 1 = server message). The 2016 client prints "<<< Welcome to <world>! >>>" for any reply, so an empty
    one is dropped (Habex does not want the banner; LSB SERVER_MESSAGE is '')."""
    if len(pkt) >= 0x10 and pkt[6] == 1 and struct.unpack_from('<i', pkt, 0x0C)[0] == 0:
        return b''
    return None


# --------------------------------------------------------------------------------------------------------
# Registration with ps2proxy
# --------------------------------------------------------------------------------------------------------

GROUPS = {
    'mp-tell-out': ('tells only, outgoing (c2s 0x0B6) in the 2007 layout; the 2016 host client reads received chat in the server layout',
                    [('c2s', 0x0B6, c2s_tell)]),
    'mp-chat': ('chat: tells (c2s 0x0B6) and received chat (s2c 0x017) in the 2007 layouts',
                [('c2s', 0x0B6, c2s_tell), ('s2c', 0x017, s2c_chat)]),
    'mp-party': ('party/alliance: kind 2<->5, kick by name, s2c 0x0DD/0x0C8 layouts',
                 [('c2s', 0x06E, c2s_group_solicit), ('c2s', 0x06F, c2s_group_leave),
                  ('c2s', 0x070, c2s_group_breakup), ('c2s', 0x071, c2s_group_strike),
                  ('c2s', 0x077, c2s_group_change2), ('s2c', 0x0DC, s2c_group_solicit),
                  ('s2c', 0x0DD, s2c_group_list), ('s2c', 0x0C8, s2c_group_tbl)]),
    'mp-linkshell': ('linkshell: c2s 0x0C3/0x0C4/0x0E1/0x0E2/0x0E4 and s2c 0x0E0 layouts',
                     [('c2s', 0x0C3, c2s_comlink_make), ('c2s', 0x0C4, c2s_comlink_active),
                      ('c2s', 0x0E1, c2s_lsmsg), ('c2s', 0x0E2, c2s_lsmsg), ('c2s', 0x0E4, c2s_lsmsg),
                      ('s2c', 0x0E0, s2c_comlink)]),
    'servmes-empty': ('drop the empty server-message reply (s2c 0x04D) so the 2016 client shows no "Welcome to" banner',
                      [('s2c', 0x04D, s2c_servmes_empty)]),
    'mp-check': ('/check: c2s 0x0DD 0x0C -> 0x10 bytes; s2c 0x0C9 general info and equipment in the 2007 layouts',
                 [('c2s', 0x0DD, c2s_equip_inspect), ('s2c', 0x0C9, s2c_equip_inspect)]),
}
ALIASES = {'mp': ['mp-chat', 'mp-party', 'mp-linkshell', 'mp-check']}


def _adapt(fn):
    def hook(ctx, pkt):
        return fn(pkt)
    hook.__name__ = fn.__name__
    return hook


def register(px):
    """Add the groups to ps2proxy's optional hooks and alias table (idempotent)."""
    for name, (desc, items) in GROUPS.items():
        if name in px.OPTIONAL_HOOKS:
            continue
        for direction, pid, fn in items:
            (px.c2s_hook if direction == 'c2s' else px.s2c_hook)(pid, optional=name, desc=desc)(_adapt(fn))
    for alias, names in ALIASES.items():
        px.TRANSLATION_ALIASES.setdefault(alias, list(names))


# --------------------------------------------------------------------------------------------------------
# Search server: MSB-first bit streams (the wca query/reply blocks; LSB unpackBitsLE reads them MSB-first too)
# --------------------------------------------------------------------------------------------------------

class BitReader:
    def __init__(self, data):
        self.data = bytes(data)
        self.pos = 0
        self.nbits = len(self.data) * 8

    def left(self):
        return self.nbits - self.pos

    def only_padding_left(self):
        """True when every remaining bit is 0 (the builders pad the last byte with zero bits)."""
        for i in range(self.pos, self.nbits):
            if (self.data[i >> 3] >> (7 - (i & 7))) & 1:
                return False
        return True

    def get(self, n):
        if self.pos + n > self.nbits:
            raise EOFError
        v = 0
        for _ in range(n):
            v = (v << 1) | ((self.data[self.pos >> 3] >> (7 - (self.pos & 7))) & 1)
            self.pos += 1
        return v


class BitWriter:
    def __init__(self):
        self.bits = []

    def put(self, v, n):
        for i in range(n - 1, -1, -1):
            self.bits.append((v >> i) & 1)

    def bytes(self):
        out = bytearray((len(self.bits) + 7) // 8)
        for i, b in enumerate(self.bits):
            if b:
                out[i >> 3] |= 0x80 >> (i & 7)
        return bytes(out)


# Request field types (LSB search/enums/search_type.h). Widths: (2007 client, LSB). None = raw payload listed.
_REQ_HEADERLESS = {0x0B, 0x0C, 0x11, 0x13, 0x16}           # no sort/present bits (LSB _HandleSearchRequest)
_REQ_FIXED = {0x02: [2], 0x03: [5], 0x04: [8, 8], 0x05: [4], 0x06: [16], 0x10: [8, 8]}
_REQ_RAW = {0x0B: 32, 0x0C: 0, 0x11: 32, 0x13: 32, 0x16: 32}


def translate_query_block(block):
    """2007 query block (size byte + MSB-first bits, _wcaBuilfQueryBlock 0x25EF80) -> LSB (name length 5 bits,
    area 10 bits). Returns the new block (size byte first). Unknown types end the translation (rest copied as is)."""
    size = block[0]
    r = BitReader(block[1:1 + size])
    w = BitWriter()
    try:
        while r.left() >= 5:
            if r.only_padding_left():
                break                                 # zero padding at the end
            t = r.get(5)
            w.put(t, 5)
            if t in _REQ_HEADERLESS:
                n = _REQ_RAW[t]
                if n:
                    w.put(r.get(n), n)
                continue
            sort, present = r.get(1), r.get(1)
            w.put(sort, 1)
            w.put(present, 1)
            if not present:
                continue
            if t == 0x00:                             # name: 4-bit length (2007) -> 5-bit (LSB), 7-bit chars
                n = r.get(4)
                w.put(n, 5)
                for _ in range(n):
                    w.put(r.get(7), 7)
            elif t == 0x01:                           # area: 8 bits (2007) -> 10 bits (LSB)
                w.put(r.get(8), 10)
            elif t in _REQ_FIXED:
                for n in _REQ_FIXED[t]:
                    w.put(r.get(n), n)
            else:
                raise ValueError('unknown query field type 0x%02X' % t)
    except (EOFError, ValueError):
        return bytes(block[:1 + size])                # leave it alone rather than send something half-translated
    body = w.bytes()
    return bytes([len(body)]) + body


# Reply entry fields: type -> list of widths as LSB writes them (search/packets/search_list.cpp, party_list.cpp)
_REP_LSB = {0x00: None, 0x01: [10], 0x02: [2], 0x03: [5, 5], 0x04: [8, 8], 0x05: [4], 0x06: [16], 0x08: [20],
            0x0D: [8], 0x0E: [32], 0x10: [8], 0x11: [32], 0x14: [32], 0x15: [16], 0x16: [32], 0x17: [16]}
# ... and what the 2007 decoder (_wcaDecodeReplyBlock 0x260270) reads; types it does not know are dropped
_REP_2007 = {0x00: None, 0x01: [8], 0x02: [2], 0x03: [5, 5], 0x04: [8, 8], 0x05: [4], 0x06: [16], 0x08: [20],
             0x0D: [8], 0x0E: [32], 0x10: [8], 0x11: [32], 0x14: [32], 0x15: [16]}


def translate_reply_entry(entry):
    """One reply entry's bits (without its size byte), LSB -> 2007."""
    r = BitReader(entry)
    w = BitWriter()
    while r.left() >= 5:
        if r.only_padding_left():
            break
        t = r.get(5)
        if t not in _REP_LSB:
            break                                     # unknown to us too: stop (the rest is padding in practice)
        if t == 0x00:
            n = r.get(4)
            chars = [r.get(7) for _ in range(n)]
            w.put(0, 5)
            w.put(n, 4)
            for c in chars:
                w.put(c, 7)
            continue
        vals = [r.get(n) for n in _REP_LSB[t]]
        if t not in _REP_2007:
            continue                                  # 0x16 flags2, 0x17 language: the 2007 client cannot skip them
        w.put(t, 5)
        for v, n in zip(vals, _REP_2007[t]):
            w.put(v & ((1 << n) - 1), n)
    return w.bytes()


LIST_REPLY_TYPES = (0x80, 0x82, 0x83, 0x84)          # search list, party list, linkshell list (entry-based)


def translate_reply_payload(plain):
    """plain = decrypted reply up to (not including) its MD5 + key trailer; returns the new plain payload."""
    if len(plain) < 0x18 or plain[0x0B] not in LIST_REPLY_TYPES:
        return None
    datasize = struct.unpack_from('<H', plain, 0x08)[0]
    end = min(datasize, len(plain))
    out = bytearray(plain[:0x18])
    o = 0x18
    while o < end:
        n = plain[o]
        if n == 0 or o + 1 + n > end:
            break
        new = translate_reply_entry(plain[o + 1:o + 1 + n])
        out.append(len(new))
        out += new
        o += 1 + n
    struct.pack_into('<H', out, 0x08, len(out))
    return bytes(out)


# --------------------------------------------------------------------------------------------------------
# Search crypto (search_handler.cpp encrypt/decrypt; PS2 0x25A150 / 0x25A2B0)
# --------------------------------------------------------------------------------------------------------

SEARCH_KEY16 = bytes([0x30, 0x73, 0x3D, 0x6D, 0x3C, 0x31, 0x49, 0x5A, 0x32, 0x7A, 0x42, 0x43, 0x63, 0x38, 0x7B, 0x7E])


def _crypt(px, buf, key, nbytes, decrypt):
    bf = px.FFXIBlowfish(hashlib.md5(key).digest())
    region = bytearray(buf[8:8 + nbytes])
    bf.crypt_blocks(region, decrypt=decrypt)
    buf[8:8 + nbytes] = region


def lsb_reply_crypt_len(length):
    """How many bytes LSB's SearchHandler::encrypt covers (its loop counter is a uint8)."""
    tmp = ((length - 12) // 4) & 0xFF
    tmp -= tmp % 2
    return tmp * 4


def open_request(px, pkt):
    """PS2 -> plain request. Returns (plain bytearray, trailer4, nonce4) or raises ValueError."""
    L = len(pkt)
    if L < 0x1C or pkt[4:8] != b'IXFF':
        raise ValueError('not a search packet')
    trailer = bytes(pkt[L - 4:])
    buf = bytearray(pkt)
    _crypt(px, buf, SEARCH_KEY16 + trailer, ((L - 12) // 8) * 8, True)
    if hashlib.md5(bytes(buf[8:L - 0x14])).digest() != bytes(buf[L - 0x14:L - 4]):
        raise ValueError('search request MD5 mismatch (unexpected key scheme)')
    return buf, trailer, bytes(buf[L - 0x18:L - 0x14])


def seal_request(px, plain, trailer):
    L = len(plain)
    buf = bytearray(plain)
    struct.pack_into('<I', buf, 0, L)
    buf[4:8] = b'IXFF'
    buf[L - 0x14:L - 4] = hashlib.md5(bytes(buf[8:L - 0x14])).digest()
    buf[L - 4:] = trailer
    _crypt(px, buf, SEARCH_KEY16 + trailer, ((L - 12) // 8) * 8, False)
    return bytes(buf)


def translate_request(px, pkt):
    """Returns (new packet bytes, trailer, nonce, description)."""
    plain, trailer, nonce = open_request(px, pkt)
    L = len(pkt)
    kind = plain[0x0B]
    desc = 'type 0x%02X' % kind
    if kind not in (0x00, 0x03) or L < 0x18 + 0x11:
        return bytes(pkt), trailer, nonce, desc
    qlen = struct.unpack_from('<H', plain, 0x08)[0]
    payload_end = L - 0x18                            # the nonce sits right after the (padded) payload
    old_block = bytes(plain[0x10:0x11 + plain[0x10]])
    new_block = translate_query_block(old_block)
    if new_block == old_block:
        return bytes(pkt), trailer, nonce, desc + ' (query unchanged)'
    rest = bytes(plain[0x10 + len(old_block):max(qlen, 0x10 + len(old_block))])   # friend id list, if any
    payload = bytes(plain[:0x10]) + new_block + rest
    new_qlen = len(payload)
    need = new_qlen + 0x18
    newL = L if need <= L else ((need - 12 + 63) // 64) * 64 + 12
    buf = bytearray(newL)
    buf[:len(payload)] = payload
    struct.pack_into('<H', buf, 0x08, new_qlen)
    buf[newL - 0x18:newL - 0x14] = nonce
    return seal_request(px, bytes(buf), trailer), trailer, nonce, desc + ' (query translated, %d -> %d B)' % (
        len(old_block), len(new_block))


def open_reply(px, pkt, trailer_req, nonce):
    L = len(pkt)
    buf = bytearray(pkt)
    trailer = bytes(pkt[L - 4:])
    _crypt(px, buf, SEARCH_KEY16 + trailer + nonce, lsb_reply_crypt_len(L), True)
    ok = hashlib.md5(bytes(buf[8:L - 0x14])).digest() == bytes(buf[L - 0x14:L - 4])
    return buf, trailer, ok


def seal_reply(px, payload, trailer, nonce):
    L = len(payload) + 0x14
    buf = bytearray(payload) + bytearray(0x14)
    struct.pack_into('<H', buf, 0, L)
    buf[2:4] = b'\0\0'
    buf[4:8] = b'IXFF'
    buf[L - 0x14:L - 4] = hashlib.md5(bytes(buf[8:L - 0x14])).digest()
    _crypt(px, buf, SEARCH_KEY16 + trailer + nonce, ((L - 12) // 8) * 8, False)
    buf[L - 4:] = trailer
    return bytes(buf)


def translate_reply(px, pkt, trailer_req, nonce):
    buf, trailer, ok = open_reply(px, pkt, trailer_req, nonce)
    if not ok:
        return bytes(pkt), 'MD5 mismatch, passed through'
    L = len(pkt)
    kind = buf[0x0B]
    new = translate_reply_payload(bytes(buf[:L - 0x14]))
    if new is None:
        # Re-seal anyway: LSB's uint8 loop counter leaves big replies partly unencrypted, the PS2 decrypts all.
        if lsb_reply_crypt_len(L) != ((L - 12) // 8) * 8:
            return seal_reply(px, bytes(buf[:L - 0x14]), trailer, nonce), 'type 0x%02X re-encrypted' % kind
        return bytes(pkt), 'type 0x%02X' % kind
    return seal_reply(px, new, trailer, nonce), 'type 0x%02X translated (%d -> %d B)' % (kind, L, len(new) + 0x14)


# --------------------------------------------------------------------------------------------------------
# Search relay (TCP)
# --------------------------------------------------------------------------------------------------------

def _read_frame(sock, pending, size_bytes):
    """One search packet: its size is the u16 (LSB) / u32 (PS2) at offset 0."""
    while True:
        if len(pending) >= 8:
            n = struct.unpack_from('<H', pending, 0)[0]
            if pending[4:8] != b'IXFF' or n < 0x1C:
                out = bytes(pending)
                del pending[:]
                return out, False
            if len(pending) >= n:
                out = bytes(pending[:n])
                del pending[:n]
                return out, True
        chunk = sock.recv(65536)
        if not chunk:
            if pending:
                out = bytes(pending)
                del pending[:]
                return out, False
            return None, False
        pending += chunk


class SearchRelay(threading.Thread):
    """Listens where lobby 0x0B now points the PS2 (cfg.search_port) and relays to xi_search, translating."""
    counter = 0

    def __init__(self, px, cfg, log):
        super().__init__(daemon=True, name='search-relay')
        self.px, self.cfg, self.log = px, cfg, log
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((cfg.listen_host, cfg.search_port))
        self.sock.listen(16)
        self.port = self.sock.getsockname()[1]

    def run(self):
        while True:
            try:
                c, a = self.sock.accept()
            except OSError as e:
                self.log('search', 'accept failed: %s' % e)
                time.sleep(0.5)
                continue
            threading.Thread(target=self.session, args=(c, a), daemon=True).start()

    def session(self, c, a):
        SearchRelay.counter += 1
        tag = 'S%d' % SearchRelay.counter
        up = None
        try:
            up = socket.create_connection((self.cfg.lsb_host, self.cfg.lsb_search_port), 10,
                                          (self.cfg.source_ip, 0) if self.cfg.source_ip else None)
            c.settimeout(30)
            up.settimeout(15)
            cp, upend = bytearray(), bytearray()
            while True:
                req, framed = _read_frame(c, cp, 4)
                if req is None:
                    break
                trailer = nonce = None
                note = 'passed through'
                out = req
                if framed:
                    try:
                        out, trailer, nonce, note = translate_request(self.px, req)
                    except Exception as e:                                        # noqa: BLE001
                        note = 'not translated (%s)' % e
                        out = req
                self.log(tag, 'search PS2 %s:%d -> LSB  %d B, %s' % (a[0], a[1], len(req), note))
                up.sendall(out)
                # LSB answers with one or more packets, then waits for the next request (or times out).
                while True:
                    try:
                        rep, framed = _read_frame(up, upend, 2)
                    except socket.timeout:
                        break
                    if rep is None:
                        raise EOFError
                    note = 'passed through'
                    fwd = rep
                    if framed and trailer is not None and self.cfg.search_translate:
                        try:
                            fwd, note = translate_reply(self.px, rep, trailer, nonce)
                        except Exception as e:                                    # noqa: BLE001
                            note = 'not translated (%s)' % e
                    self.log(tag, 'search LSB -> PS2  %d B, %s' % (len(rep), note))
                    c.sendall(fwd)
                    last = len(rep) >= 0x0B and rep[0x0A] & 0x80
                    if not framed:
                        break
                    up.settimeout(0.5 if not last else 0.3)
        except EOFError:
            pass
        except (OSError, ValueError) as e:
            self.log(tag, 'search session ended: %s' % e)
        except Exception as e:                                                    # noqa: BLE001
            self.log(tag, 'search session error: %s\n%s' % (e, traceback.format_exc()))
        finally:
            for s in (c, up):
                if s:
                    try:
                        s.close()
                    except OSError:
                        pass


# --------------------------------------------------------------------------------------------------------
# Unit tests (python3 ps2proxy_mp.py): pure layout checks, no network
# --------------------------------------------------------------------------------------------------------

def _mk(pid, body):
    size = (4 + len(body) + 3) & ~3
    p = bytearray(size)
    struct.pack_into('<HH', p, 0, pid | ((size // 4) << 9), 7)
    p[4:4 + len(body)] = body
    return bytes(p)


def _unittest():
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ps2proxy as px
    fails = []

    def check(name, cond):
        print('  %-66s %s' % (name, 'PASS' if cond else 'FAIL'))
        if not cond:
            fails.append(name)

    # tell: 2007 layout -> LSB layout
    pk = _mk(0x0B6, bytes([0]) + b'Kyle'.ljust(15, b'\0') + b'hi!\0')
    t = c2s_tell(pk)
    check('c2s 0x0B6: 3/0 marker, name@6, message@0x15',
          t[4] == 3 and t[5] == 0 and t[6:10] == b'Kyle' and t[0x15:0x18] == b'hi!' and (_hdr(t) >> 9) * 4 == len(t))
    lsb_len_ok = min((_hdr(t) >> 9) * 4 - 0x15, 128) >= 3
    check('c2s 0x0B6: LSB message length covers the text', lsb_len_ok)
    # chat: LSB -> 2007
    body = bytes([3, 1]) + struct.pack('<H', 231) + b'Mar'.ljust(15, b'\0') + b'hello there'
    c = s2c_chat(_mk(0x017, body))
    check('s2c 0x017: Attr@4, name@5, Kind@0x14, text@0x15',
          c[4] == 1 and c[5:8] == b'Mar' and c[0x14] == 3 and c[0x15:0x20] == b'hello there')
    c = s2c_chat(_mk(0x017, bytes([26, 0, 0, 0]) + b'X'.ljust(15, b'\0') + b'y'))
    check('s2c 0x017: yell (26) shown as shout (1)', c[0x14] == 1)
    # party
    p = s2c_group_solicit(_mk(0x0DC, struct.pack('<IHBB', 1234, 0x401, 0, 5) + b'Mar'.ljust(16, b'\0') + b'\x01\0\0\0'))
    check('s2c 0x0DC: alliance kind 5 -> 2 at 0xB, name stays at 0xC', p[0x0B] == 2 and p[0x0C:0x0F] == b'Mar')
    lst = bytearray(0x3C - 4)                        # body offsets = packet offsets - 4
    struct.pack_into('<IIII', lst, 0, 77, 100, 50, 0)
    struct.pack_into('<IH', lst, 0x14 - 4, 0x05, 0x402)
    lst[0x1D - 4] = 90
    lst[0x1E - 4] = 80
    struct.pack_into('<H', lst, 0x20 - 4, 231)
    lst[0x28 - 4:0x28 - 4 + 4] = b'Kyle'
    g = s2c_group_list(_mk(0x0DD, bytes(lst)))
    check('s2c 0x0DD: ZoneNo u8@0x1F, name@0x20, HP%%@0x1D', g[0x1F] == 231 and g[0x20:0x24] == b'Kyle'
          and g[0x1D] == 90 and px.u32(g, 4) == 77 and len(g) == 0x30)
    tb = bytearray(0xF8 - 4)
    tb[0] = 5
    for i, (u, a, f, z) in enumerate([(11, 0x400, 0x04, 231), (22, 0x401, 0x00, 230)]):
        struct.pack_into('<IHBBH', tb, 4 + 12 * i, u, a, f, 0, z)
    g = s2c_group_tbl(_mk(0x0C8, bytes(tb)))
    check('s2c 0x0C8: 8-byte entries, kind 5 -> 2, zone u8', len(g) == 0xA8 and g[4] == 2 and px.u32(g, 8) == 11
          and struct.unpack_from('<HBB', g, 12) == (0x400, 4, 231) and px.u32(g, 16) == 22 and g[23] == 230)
    k = c2s_group_strike(_mk(0x071, struct.pack('<IHBB', 99, 0x402, 0, 0) + b'Kyle'.ljust(15, b'\0') + b'\0'))
    check('c2s 0x071: UniqueNo/ActIndex zeroed, name kept', px.u32(k, 4) == 0 and k[8:10] == b'\0\0' and k[0x0C:0x10] == b'Kyle')
    k = c2s_group_solicit(_mk(0x06E, struct.pack('<IHBB', 99, 0x402, 2, 0)))
    check('c2s 0x06E: alliance kind 2 -> 5', k[0x0A] == 5)
    # linkshell
    a = c2s_comlink_active(_mk(0x0C4, struct.pack('<HBB', 0xF123, 7, 1) + b'MyShell'.ljust(15, b'\0') + b'\0'))
    check('c2s 0x0C4: 0x1C bytes, ItemIndex@6, ActiveFlg@8, name@0xC, LS id 1',
          len(a) == 0x1C and a[6] == 7 and a[8] == 1 and a[0x0C:0x13] == b'MyShell' and a[0x1B] == 1)
    m = c2s_lsmsg(_mk(0x0E2, bytes([0x40, 0]) + struct.pack('<HI', 5, 0) + b'msg'.ljust(128, b'\0')))
    check('c2s 0x0E2: 0x90 bytes, seqId@0xA, text@0x10', len(m) == 0x90 and struct.unpack_from('<H', m, 0x0A)[0] == 5
          and m[0x10:0x13] == b'msg' and m[4] == 0x40)
    e = s2c_comlink(_mk(0x0E0, bytes([1, 9, 0, 0])))
    check('s2c 0x0E0: ItemIndex moves to 4', e[4] == 9)
    check('s2c 0x0E0: LS2 update dropped', s2c_comlink(_mk(0x0E0, bytes([2, 9, 0, 0]))) == b'')
    check('c2s 0x0DD: padded to 0x10 (Kind 0)', len(c2s_equip_inspect(_mk(0x0DD, struct.pack('<II', 5, 0x401)))) == 0x10)
    gen = bytearray(0x54 - 4)
    struct.pack_into('<IHB', gen, 0, 46, 0x400, 1)
    struct.pack_into('<H', gen, 0x0E - 4, 513)
    gen[0x10 - 4:0x10 - 4 + 8] = b'Botshell'
    struct.pack_into('<HBBBB', gen, 0x20 - 4, 0xF39, 1, 5, 75, 37)
    g = s2c_equip_inspect(_mk(0x0C9, bytes(gen)))
    check('s2c 0x0C9 general: colour@0x10, jobs@0x12, LS name@0x14, levels@0x23',
          g[0x0A] == 1 and g[0x12:0x14] == bytes([1, 5]) and g[0x14:0x1C] == b'Botshell' and g[0x23:0x25] == bytes([75, 37])
          and struct.unpack_from('<H', g, 0x10)[0] == 0xF39)
    eq = bytearray(0x0C - 4 + 28 * 2)
    struct.pack_into('<IHBB', eq, 0, 46, 0x400, 3, 2)
    struct.pack_into('<HB', eq, 0x0C - 4, 18282, 0)
    struct.pack_into('<HB', eq, 0x0C - 4 + 28, 15270, 4)
    e2 = s2c_equip_inspect(_mk(0x0C9, bytes(eq)))
    subs = [e2[i:i + 16] for i in range(0, len(e2), 16)]
    check('s2c 0x0C9 equipment: split into flag-0 packets (item@0xC, slot@0xE)', len(subs) == 2 and
          all((_hdr(x) >> 9) * 4 == 16 and x[0x0A] == 0 for x in subs) and struct.unpack_from('<HB', subs[1], 0x0C) == (15270, 4))
    # search query: name "Mar" + area 231, 2007 widths
    w = BitWriter()
    w.put(0, 5); w.put(0, 1); w.put(1, 1); w.put(3, 4)
    for ch in b'Mar':
        w.put(ch, 7)
    w.put(1, 5); w.put(0, 1); w.put(1, 1); w.put(231, 8)
    blk = w.bytes()
    nb = translate_query_block(bytes([len(blk)]) + blk)
    r = BitReader(nb[1:])
    ok = (r.get(5), r.get(1), r.get(1), r.get(5)) == (0, 0, 1, 3) and bytes(r.get(7) for _ in range(3)) == b'Mar' \
        and (r.get(5), r.get(1), r.get(1), r.get(10)) == (1, 0, 1, 231)
    check('search query: name length 4 -> 5 bits, area 8 -> 10 bits', ok)
    # an 8-letter name: 67 bits, the last byte padded with zero bits (the case that must not be misread)
    w = BitWriter()
    w.put(0, 5); w.put(0, 1); w.put(1, 1); w.put(8, 4)
    for ch in b'Botbuddy':
        w.put(ch, 7)
    blk8 = w.bytes()
    nb8 = translate_query_block(bytes([len(blk8)]) + blk8)
    r = BitReader(nb8[1:])
    ok = (r.get(5), r.get(1), r.get(1), r.get(5)) == (0, 0, 1, 8) and bytes(r.get(7) for _ in range(8)) == b'Botbuddy'
    check('search query: 8-letter name followed by padding bits', ok and r.only_padding_left())
    # search reply entry: LSB -> 2007
    w = BitWriter()
    w.put(0, 5); w.put(3, 4)
    for ch in b'Mar':
        w.put(ch, 7)
    w.put(1, 5); w.put(231, 10); w.put(3, 5); w.put(1, 5); w.put(0, 5); w.put(4, 5); w.put(1, 8); w.put(0, 8)
    w.put(8, 5); w.put(2, 20); w.put(0x16, 5); w.put(0xFFFFFFFF, 32); w.put(0x17, 5); w.put(1, 16)
    ent = w.bytes()
    ne = translate_reply_entry(ent)
    r = BitReader(ne)
    ok = (r.get(5), r.get(4)) == (0, 3) and bytes(r.get(7) for _ in range(3)) == b'Mar' and \
        (r.get(5), r.get(8)) == (1, 231) and (r.get(5), r.get(5), r.get(5)) == (3, 1, 0) and \
        (r.get(5), r.get(8), r.get(8)) == (4, 1, 0) and (r.get(5), r.get(20)) == (8, 2)
    rest = r.data[(r.pos + 7) // 8:]
    check('search reply: area 10 -> 8 bits, flags2/language dropped', ok and not any(rest) and r.left() < 13)
    # search crypto round trip against our own sealer
    plain = bytearray(64 + 12)
    plain[0x0B] = 3
    struct.pack_into('<H', plain, 8, 0x10 + 1 + len(blk))
    plain[0x10] = len(blk)
    plain[0x11:0x11 + len(blk)] = blk
    plain[len(plain) - 0x18:len(plain) - 0x14] = b'NONC'
    sealed = seal_request(px, bytes(plain), b'TRLR')
    out, tr, nonce, note = translate_request(px, sealed)
    op, tr2, n2 = open_request(px, out)
    r = BitReader(op[0x11:0x11 + op[0x10]])
    check('search request: decrypt, translate, re-seal (%s)' % note,
          tr2 == b'TRLR' and n2 == b'NONC' and (r.get(5), r.get(1), r.get(1), r.get(5)) == (0, 0, 1, 3))
    print('ps2proxy_mp unit tests: %s' % ('PASS' if not fails else 'FAIL (%d)' % len(fails)))
    return not fails


if __name__ == '__main__':
    import sys
    sys.exit(0 if _unittest() else 1)
