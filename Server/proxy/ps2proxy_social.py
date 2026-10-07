#!/usr/bin/env python3
"""ps2proxy_social - translations for the 2016 PS2 client in party / trade / check / linkshell / delivery box packets,
found by testing two 2016 clients against LandSandBoat (b49_social) and reading the 2016 receive handlers (ffxi_pol.pex 20160203_0).

Group "soc-2016" (off unless --translate soc-2016):
  s2c 0x017 chat: the 2016 client reads the text at 0x18, LSB writes it at 0x17 (received say/party/linkshell/tell lost the first letter)
            -> one zero byte is inserted before the text.
  s2c 0x05F music: beta tracks 901-953 -> 701-753 (the 2016 engine streams >= 900 from DAT files that do not exist; the drive has 7NN).
  s2c 0x0DD party member (RecvGroupList 0x3DA950): the 2016 client reads Name at 0x26; LSB (current retail) has two new job bytes at
            0x26/0x27 (masterjob_lv/flags) and Name at 0x28 -> drop the two bytes, so the member's name shows in the party list.
Group "soc-mute" (any client mode; FFXI Server app, 6 Oct 2026): c2s 0x0B5 (say/shout/party/linkshell/yell, incl. "!" lines) and
  0x0B6 (tell) from a character listed in the mute file are dropped, so nobody sees them. Mute file = PS2PROXY_MUTE_FILE or
  ~/Downloads/FFXI/Server/.tools/muted.txt (one character name per line; '#' comments), re-read when it changes - no restart.
Loaded by research/tools/ps2proxy.py itself (and by work/b49_social/soc_proxy.py)."""
import os
import struct
import time

def _hdr(p): return struct.unpack_from('<H', p, 0)[0]

def _resize(pkt, n):
    n = (n + 3) & ~3
    p = bytearray(pkt[:n].ljust(n, b'\0'))
    struct.pack_into('<H', p, 0, (_hdr(p) & 0x1FF) | ((n // 4) << 9))
    return bytes(p)

def s2c_group_list(ctx, pkt):
    if len(pkt) < 0x2C:
        return None
    body = pkt[:0x26] + pkt[0x28:]
    return _resize(body, len(pkt))          # same size, name moved down by 2

def _dump(ctx, pkt):
    try:
        ctx.log(ctx.tag, 'soc-debug %03X %d B: %s' % (_hdr(pkt) & 0x1FF, len(pkt), pkt.hex(' ')))
    except Exception:
        pass
    return None

def s2c_chat(ctx, pkt):
    """s2c 0x017 chat: LSB {Kind@4, Attr@5, Data@6, sName[15]@8, Mes@0x17}; the 2016 client reads the text from 0x18 (sName is 16 bytes there),
    so every received say/party/linkshell/tell line lost its first letter. Insert one zero byte before the text."""
    if len(pkt) < 0x17:
        return None
    body = pkt[:0x17] + b'\0' + pkt[0x17:]
    if body[-1:] != b'\0':
        body += b'\0'
    return _resize(body, len(body))

def s2c_music(ctx, pkt):
    """s2c 0x05F music {Slot u16@4, MusicNum u16@6}: the 2016 engine streams tracks >= 900 from DAT file 49875+n (only 900 exists;
    901+ hung the music task), so the beta tracks 901-953 (lan_legacy Beta Jukebox / !betamusic) are sent as 701-753, which the 2016
    drive carries as normal BGM/wave files (work/b43_host2016/stage_beta_music7)."""
    if len(pkt) < 8:
        return None
    n = struct.unpack_from('<H', pkt, 6)[0]
    if 901 <= n <= 953:
        p = bytearray(pkt); struct.pack_into('<H', p, 6, n - 200); return bytes(p)
    return None

MUTE_FILE = os.environ.get('PS2PROXY_MUTE_FILE') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'muted.txt')
_mute = {'mtime': None, 'names': frozenset(), 'checked': 0.0}

def muted_names():
    now = time.time()
    if now - _mute['checked'] >= 2.0:
        _mute['checked'] = now
        try:
            mt = os.path.getmtime(MUTE_FILE)
        except OSError:
            mt = None
        if mt != _mute['mtime']:
            names = set()
            if mt is not None:
                try:
                    for line in open(MUTE_FILE, errors='replace'):
                        line = line.split('#', 1)[0].strip()
                        if line:
                            names.add(line.lower())
                except OSError:
                    pass
            _mute['mtime'], _mute['names'] = mt, frozenset(names)
    return _mute['names']

def c2s_mute(ctx, pkt):
    """Drop chat from a muted character (b'' = the sub-packet is not forwarded)."""
    name = getattr(getattr(ctx, 'ticket', None), 'name', None)
    if name and name.lower() in muted_names():
        try:
            ctx.log(ctx.tag, 'soc-mute: dropped %03X chat from muted character %s' % (_hdr(pkt) & 0x1FF, name))
        except Exception:
            pass
        return b''
    return None

GROUPS = {
    'soc-mute': ('drop chat (say/shout/party/linkshell/yell/tell) from characters listed in .tools/muted.txt (FFXI Server app mute)', [
        ('c2s', 0x0B5, c2s_mute), ('c2s', 0x0B6, c2s_mute),
    ]),
    'soc-debug': ('log the raw bytes of chat packets (debug)', [
        ('s2c', 0x017, _dump), ('c2s', 0x0B5, _dump),
    ]),
    'soc-2016': ('2016 client: party member name (s2c 0x0DD name 0x28 -> 0x26), chat text offset (s2c 0x017 Mes 0x17 -> 0x18), beta music 901-953 -> 701-753 (s2c 0x05F)', [
        ('s2c', 0x0DD, s2c_group_list),
        ('s2c', 0x017, s2c_chat),
        ('s2c', 0x05F, s2c_music),
    ]),
}

def register(px):
    for name, (desc, items) in GROUPS.items():
        if name in px.OPTIONAL_HOOKS:
            continue
        for direction, pid, fn in items:
            (px.c2s_hook if direction == 'c2s' else px.s2c_hook)(pid, optional=name, desc=desc)(fn)
