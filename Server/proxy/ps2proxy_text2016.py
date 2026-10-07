#!/usr/bin/env python3
"""ps2proxy_text2016 - zone text ids and an event guard for the 2016 PS2 client.

Optional group "text-2016" (off unless --translate text-2016; use it together with npc-ids and enable it AFTER npc-ids,
so the event guard sees 2016 actor ids). Nothing here touches the 2012 build: the server keeps its 2012pc IDs.lua.

  text  The server's zone message numbers (scripts/zones/*/IDs.lua, profile 2012pc) index the 2012 dialog DATs; the
        2016 client reads its own (EN 6420+zone / 84271+zone-256). Map file: {zone: {server id: 2016 id}} for every id that differs.
        s2c 0x036 (MesNum @0x0A), 0x027 (@0x0A), 0x02A (@0x1A); the 0x8000 "no name" flag is kept. A map value of -1
        (a line the 2016 dialog lacks, i.e. post-2016 text) drops the message instead of showing a wrong line.
  guard An event (cutscene) the 2016 data does not have for that actor (post-Feb-2016 content, or an NPC the 2016
        list lacks) leaves the client waiting forever ("You cannot use that command"). s2c 0x032/0x033/0x034 whose
        event id is in neither the actor's block nor the zone's own block of the 2016 event DAT (5820+zone /
        83671+zone-256; maps/events_2016.json) is dropped, and an event end (c2s 0x05B, Mode End,
        option 0x40000000 = "cancelled") is sent to the server in the client's next frame, so the server
        finishes the event and releases the player (0x052). Nothing progresses for such events. (The client sends only
        empty frames while it waits, so the event end is added to its next frame: ZoneClient.run_hooks is wrapped.)
        If the 2016 file has the event under ANOTHER actor of the zone, the event is sent under that actor instead
        (PS2PROXY_EVREWRITE=0 switches this off).

Environment: PS2PROXY_TEXT2016_MAP, PS2PROXY_EVENTS2016 (file paths), PS2PROXY_EVGUARD=0 to switch the guard off.
Unit tests (no server): python3 ps2proxy_text2016.py
"""
import json
import os
import struct

MAPS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'maps')   # release: Server/proxy/maps
TEXT_FILE = os.environ.get('PS2PROXY_TEXT2016_MAP', os.path.join(MAPS, 'text_map_2016.json'))
EV_FILE = os.environ.get('PS2PROXY_EVENTS2016', os.path.join(MAPS, 'events_2016.json'))
GUARD = os.environ.get('PS2PROXY_EVGUARD', '1') != '0'
REWRITE = os.environ.get('PS2PROXY_EVREWRITE', '1') != '0'     # event under another actor: send it there
ZONE_BLOCK = 0x7FFFFFF0
CANCEL = 0x40000000

_TEXT = None
_EV = None
_PX = None
STATS = {}


def _load():
    global _TEXT, _EV
    if _TEXT is None:
        _TEXT = {}
        if os.path.exists(TEXT_FILE):
            for z, m in json.load(open(TEXT_FILE)).items():
                _TEXT[int(z)] = {int(k): v for k, v in m.items()}
    if _EV is None:
        _EV = {}
        if os.path.exists(EV_FILE):
            for z, m in json.load(open(EV_FILE)).items():
                _EV[int(z)] = {int(a): set(v) for a, v in m.items()}


def _u16(p, o):
    return struct.unpack_from('<H', p, o)[0]


def _u32(p, o):
    return struct.unpack_from('<I', p, o)[0]


def _count(ctx, key, what):
    n = STATS.get(key, 0) + 1
    STATS[key] = n
    if n == 1 and ctx is not None and hasattr(ctx, 'log'):
        ctx.log(ctx.tag, 't16   %s (first time; counted silently from now on)' % what)


# ---- zone ----------------------------------------------------------------------------------------------------
def s2c_login(ctx, pkt):
    if len(pkt) >= 0x34:
        ctx.t16_zone = _u16(pkt, 0x30)
    return None


# ---- text ----------------------------------------------------------------------------------------------------
def _text(ctx, pkt, off, pid):
    _load()
    m = _TEXT.get(getattr(ctx, 't16_zone', None))
    if not m or len(pkt) < off + 2:
        return None
    raw = _u16(pkt, off)
    new = m.get(raw & 0x7FFF)
    if new is None:
        return None
    if new < 0:                                    # a line the 2016 dialog does not have (post-2016 text): drop
        _count(ctx, 'textdrop %03X' % pid, 's2c 0x%03X text id %d has no 2016 line: message dropped' % (pid, raw & 0x7FFF))
        return b''
    p = bytearray(pkt)
    struct.pack_into('<H', p, off, (raw & 0x8000) | new)
    _count(ctx, 'text %03X' % pid, 's2c 0x%03X text id %d -> 2016 id %d' % (pid, raw & 0x7FFF, new))
    return bytes(p)


def s2c_036(ctx, pkt):
    return _text(ctx, pkt, 0x0A, 0x036)


def s2c_027(ctx, pkt):
    return _text(ctx, pkt, 0x0A, 0x027)


def s2c_02a(ctx, pkt):
    return _text(ctx, pkt, 0x1A, 0x02A)


# ---- event guard ---------------------------------------------------------------------------------------------
EV_LAYOUT = {0x032: (4, 8, 0x0A, 0x0C), 0x033: (4, 8, 0x0A, 0x0C), 0x034: (4, 0x28, 0x2A, 0x2C)}  # actor, index, file, event


def _lsb_ids(ctx, actor, index):
    """The packet already carries 2016 ids when npc-ids ran first: give LSB's back for the event end."""
    if _PX is None or 'npc-ids' not in getattr(_PX, 'ENABLED_TRANSLATIONS', ()):
        return actor, index
    try:
        import ps2proxy_npc as N
        z = N._zone(ctx)
    except Exception:                                                            # noqa: BLE001
        z = None
    if not z:
        return actor, index
    a = z[1].get(actor, actor)
    return a, (a & 0xFFF) if a != actor else index


def event_known(zone, actor, event):
    """True/False, or None when the 2016 event file is not on hand (then the event passes)."""
    _load()
    ev = _EV.get(zone)
    if ev is None or event == 0xFFFF:
        return None
    if event in ev.get(ZONE_BLOCK, ()):
        return True
    if actor >> 24 == 1:
        return event in ev.get(actor, ())
    return any(event in s for s in ev.values())      # player-targeted: anywhere in the zone file


def _guard(ctx, pkt, pid):
    if not GUARD:
        return None
    ao, io, fo, eo = EV_LAYOUT[pid]
    if len(pkt) < eo + 2:
        return None
    actor, index, efile, event = _u32(pkt, ao), _u16(pkt, io), _u16(pkt, fo), _u16(pkt, eo)
    if event_known(efile, actor, event) is not False:
        return None
    # prefer the smallest block holding the event (an event-holder entity next to the NPC, e.g. [S] doors)
    other = sorted((a for a, s in _EV.get(efile, {}).items() if event in s and a >> 24 == 1), key=lambda a: (len(_EV[efile][a]), a))
    if other and actor >> 24 == 1 and REWRITE:
        # the 2016 data keeps this cutscene under another actor of the zone (an NPC with several entities, or one the
        # event moved to after 2016): play it there; LSB only checks the event id of the event end
        p = bytearray(pkt)
        struct.pack_into('<I', p, ao, other[0])
        struct.pack_into('<H', p, io, other[0] & 0xFFF)
        ctx.log(ctx.tag, 't16   event %d (file %d): not under actor %d in the 2016 data, sent under actor %d' % (
            event, efile, actor, other[0]))
        STATS['event actor rewritten'] = STATS.get('event actor rewritten', 0) + 1
        return bytes(p)
    la, li = _lsb_ids(ctx, actor, index)
    end = struct.pack('<HHIIHHHH', 0x05B | ((0x14 // 4) << 9), 0, la, CANCEL, li, 0, efile, event)
    q = getattr(ctx, 't16_inject', None)
    if q is None:
        q = ctx.t16_inject = []
    q.append(end)
    ctx.log(ctx.tag, 't16   event %d (file %d) for actor %d not in the 2016 data: dropped, event end (cancel) queued '
                     'for the server' % (event, efile, actor))
    STATS['event dropped'] = STATS.get('event dropped', 0) + 1
    return b''


def s2c_032(ctx, pkt):
    return _guard(ctx, pkt, 0x032)


def s2c_033(ctx, pkt):
    return _guard(ctx, pkt, 0x033)


def s2c_034(ctx, pkt):
    return _guard(ctx, pkt, 0x034)


def _take_inject(ctx):
    """Queued event ends; each gets the current client frame's packet counter as its sync value (LSB skips a
    sub-packet whose sync is not newer than the last one it handled and not above the frame's counter)."""
    q = getattr(ctx, 't16_inject', None)
    if not q:
        return []
    ctx.t16_inject = []
    sync = getattr(ctx, 't16_frame_code', 0)
    ctx.log(ctx.tag, 't16   %d queued event end(s) sent to the server (sync %d)' % (len(q), sync))
    return [(0x05B, bytes(e[:2]) + struct.pack('<H', sync) + bytes(e[4:])) for e in q]


def _patch_run_hooks(px):
    """While waiting for an event the client sends EMPTY frames (no sub-packets), so the queued event end is added
    to the next client frame at frame level: ZoneClient.run_hooks is wrapped (c2s direction only)."""
    zc = getattr(px, 'ZoneClient', None)
    if zc is None or getattr(zc.run_hooks, '_t16', False):
        return
    orig = zc.run_hooks

    def run_hooks(self, subs, hooks):
        out, changed = orig(self, subs, hooks)
        if hooks is px.C2S_HOOKS and getattr(self, 't16_inject', None):
            out = list(out) + _take_inject(self)
            changed = True
        return out, changed
    run_hooks._t16 = True
    zc.run_hooks = run_hooks
    oc2s = zc.c2s

    def c2s(self, frame):
        if len(frame) >= 2:
            self.t16_frame_code = struct.unpack_from('<H', frame, 0)[0]
        return oc2s(self, frame)
    zc.c2s = c2s


def groups():
    items = [('s2c', 0x00A, s2c_login), ('s2c', 0x036, s2c_036), ('s2c', 0x027, s2c_027), ('s2c', 0x02A, s2c_02a),
             ('s2c', 0x032, s2c_032), ('s2c', 0x033, s2c_033), ('s2c', 0x034, s2c_034)]
    return {'text-2016': ('2016 client: zone text ids 2012pc -> 2016 dialog, and guard for events the 2016 data lacks '
                          '', items)}


def register(px):
    global _PX
    _PX = px
    _patch_run_hooks(px)
    for name, (desc, items) in groups().items():
        if name in px.OPTIONAL_HOOKS:
            continue
        for direction, pid, fn in items:
            (px.c2s_hook if direction == 'c2s' else px.s2c_hook)(pid, optional=name, desc=desc)(fn)


# ---- unit tests ----------------------------------------------------------------------------------------------
def unit_tests():
    global _TEXT, _EV
    class Ctx:
        tag = 'T'
        def log(self, *a):
            pass
    _TEXT = {230: {6403: 6428, 9000: -1}}
    _EV = {230: {ZONE_BLOCK: {500}, 17719503: {600, 601}}}
    c = Ctx(); ok = []
    login = bytearray(0x104); struct.pack_into('<H', login, 0x30, 230); s2c_login(c, bytes(login))
    ok.append(('zone', c.t16_zone == 230))
    m = struct.pack('<HHIHHBBH', 0x36 | (0x10 // 4) << 9, 0, 17719503, 207, 6403 | 0x8000, 0, 0, 0)
    r = s2c_036(c, m); ok.append(('0x036 text id + flag', _u16(r, 0x0A) == 6428 | 0x8000))
    ok.append(('unmapped text untouched', s2c_036(c, struct.pack('<HHIHHBBH', 0x36, 0, 1, 1, 7, 0, 0, 0)) is None))
    ok.append(('post-2016 text dropped', s2c_036(c, struct.pack('<HHIHHBBH', 0x36, 0, 1, 1, 9000, 0, 0, 0)) == b''))
    sp = bytearray(0x40); struct.pack_into('<H', sp, 0x1A, 6403); r = s2c_02a(c, bytes(sp))
    ok.append(('0x02A text id', _u16(r, 0x1A) == 6428))
    ev_ok = struct.pack('<HHIHHHH', 0x32 | (0x14 // 4) << 9, 0, 17719503, 207, 230, 600, 0) + bytes(4)
    ok.append(('known event passes', s2c_032(c, ev_ok) is None))
    ok.append(('zone-block event passes', s2c_032(c, struct.pack('<HHIHHHH', 0x32, 0, 17719503, 207, 230, 500, 0) + bytes(4)) is None))
    _EV[230][17719504] = {650}
    r = s2c_032(c, struct.pack('<HHIHHHH', 0x32 | (0x14 // 4) << 9, 0, 17719503, 207, 230, 650, 0) + bytes(4))
    ok.append(('event under other actor rewritten', _u32(r, 4) == 17719504 and _u16(r, 8) == 0x0D0))
    ev_bad = struct.pack('<HHIHHHH', 0x32 | (0x14 // 4) << 9, 0, 17719503, 207, 230, 999, 0) + bytes(4)
    ok.append(('missing event dropped', s2c_032(c, ev_bad) == b''))
    q = _take_inject(c)
    e = q[0][1] if q else b''
    ok.append(('event end queued', len(e) == 0x14 and _u16(e, 0) & 0x1FF == 0x5B and _u32(e, 4) == 17719503
               and _u32(e, 8) == CANCEL and _u16(e, 0x0E) == 0 and _u16(e, 0x10) == 230 and _u16(e, 0x12) == 999))
    ok.append(('queue emptied', _take_inject(c) == []))
    ok.append(('other zone file passes', event_known(5, 1, 1) is None))
    e34 = bytearray(0x30); struct.pack_into('<I', e34, 4, 17719503); struct.pack_into('<HHH', e34, 0x28, 207, 230, 777)
    ok.append(('0x034 missing dropped', s2c_034(c, bytes(e34)) == b''))
    for n, v in ok:
        print('  %-32s %s' % (n, 'PASS' if v else 'FAIL'))
    _TEXT = _EV = None
    return all(v for _, v in ok)


if __name__ == '__main__':
    import sys
    sys.exit(0 if unit_tests() else 1)
