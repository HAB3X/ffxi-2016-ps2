"""d_msg / XISTRING table read + write: rebuild a table as 2012 entries + appended PC entries."""
import struct
NOT = bytes((~x) & 0xFF for x in range(256))
def dmsg_read(d):
    enc = struct.unpack_from('<H', d, 0x0A)[0]; isz, rsz, dsz, n = struct.unpack_from('<4I', d, 0x1C)
    body = d[0x40:]
    if enc: body = body.translate(NOT)
    if isz == 0:
        return dict(kind='fix', enc=enc, rsz=rsz, ents=[body[k * rsz:(k + 1) * rsz] for k in range(n)])
    idx = body[:isz]; data = body[isz:]; ents = []; offs = []
    for k in range(n):
        o, l = struct.unpack_from('<II', idx, 8 * k); ents.append(data[o:o + l]); offs.append((o, l))
    return dict(kind='idx', enc=enc, ents=ents, offs=offs, datalen=len(data))
def dmsg_write(orig, ents):
    hdr = bytearray(orig[:0x40]); enc = struct.unpack_from('<H', orig, 0x0A)[0]; r = dmsg_read(orig)
    if r['kind'] == 'fix':
        body = b''.join(e.ljust(r['rsz'], b'\0') for e in ents); isz = 0; dsz = len(body)
    else:
        idx = b''; data = b''
        for e in ents:
            idx += struct.pack('<II', len(data), len(e)); data += e
        isz = len(idx); body = idx + data; dsz = len(data)
    if enc: body = body.translate(NOT)
    struct.pack_into('<I', hdr, 0x14, 0x40 + len(body)); struct.pack_into('<I', hdr, 0x1C, isz)
    struct.pack_into('<I', hdr, 0x24, dsz); struct.pack_into('<I', hdr, 0x28, len(ents))
    return bytes(hdr) + body
def xis_read(d):
    n, isz = struct.unpack_from('<II', d, 0x24)
    ents = []; flags = []
    for k in range(n):
        o, l, f = struct.unpack_from('<III', d, 0x38 + 12 * k); ents.append(d[0x38 + isz + o:0x38 + isz + o + l]); flags.append(f)
    return dict(kind='xis', ents=ents, flags=flags)
def xis_write(orig, ents, flags):
    hdr = bytearray(orig[:0x38]); idx = b''; data = b''
    for e, f in zip(ents, flags):
        idx += struct.pack('<III', len(data), len(e), f); data += e
    out = bytes(hdr) + idx + data
    b = bytearray(out); struct.pack_into('<I', b, 0x20, len(out)); struct.pack_into('<II', b, 0x24, len(ents), len(idx))
    struct.pack_into('<I', b, 0x2C, len(data))
    return bytes(b)
def read(d):
    return dmsg_read(d) if d[:5] == b'd_msg' else xis_read(d)
def append(old, new):
    """2012 table + only the entries the newer table appends (existing 2012 entries unchanged)."""
    a, b = read(old), read(new)
    if a['kind'] == 'xis':
        return xis_write(old, a['ents'] + b['ents'][len(a['ents']):], a['flags'] + b['flags'][len(a['ents']):])
    if a['kind'] == 'fix' and b['kind'] == 'fix' and a['rsz'] != b['rsz']: raise ValueError('record size differs')
    return dmsg_write(old, a['ents'] + b['ents'][len(a['ents']):])
def xis_append(old, new_ents, new_flags):
    """keep the original index + data (XISTRING shares identical strings), add new entries after them."""
    n, isz = struct.unpack_from('<II', old, 0x24); dsz = struct.unpack_from('<I', old, 0x2C)[0]
    idx = old[0x38:0x38 + isz]; data = old[0x38 + isz:0x38 + isz + dsz]; extra_i = b''; extra_d = b''
    for e, f in zip(new_ents, new_flags):
        extra_i += struct.pack('<III', len(data) + len(extra_d), len(e), f); extra_d += e
    out = bytearray(old[:0x38] + idx + extra_i + data + extra_d)
    struct.pack_into('<I', out, 0x20, len(out)); struct.pack_into('<II', out, 0x24, n + len(new_ents), isz + len(extra_i))
    struct.pack_into('<I', out, 0x2C, dsz + len(extra_d))
    return bytes(out)
def append(old, new):
    a, b = read(old), read(new); k = len(a['ents'])
    if a['kind'] == 'xis':
        return xis_append(old, b['ents'][k:], b['flags'][k:])
    if a['kind'] == 'fix' and b['kind'] == 'fix' and a['rsz'] != b['rsz']: raise ValueError('record size differs')
    return dmsg_write(old, a['ents'] + b['ents'][k:])
import re as _re
_PH = _re.compile(rb'^(\([^()]{0,24}\d+\)|\d+|\.|-|\?+|[Dd]ummy\d*|DUMMY\d*)$')
def placeholder(e):
    """True for an unused 2012 slot: no text at all, or only ASCII placeholders like '(magic 243)', '49', '.'."""
    if any(b >= 0x80 for b in e): return False
    t = [x.strip() for x in _re.split(rb'[^\x20-\x7e]+', e) if x.strip()]
    return all(_PH.match(x) for x in t)
def append_fill(old, new):
    """append() + fill the 2012 placeholder slots that the newer table fills (d_msg only). Returns (bytes, filled slots)."""
    a, b = read(old), read(new); k = len(a['ents'])
    if a['kind'] == 'xis': return append(old, new), []
    if a['kind'] == 'fix' and b['kind'] == 'fix' and a['rsz'] != b['rsz']: raise ValueError('record size differs')
    ents = list(a['ents']); filled = []
    for j in range(min(k, len(b['ents']))):
        if ents[j] != b['ents'][j] and placeholder(ents[j]) and not placeholder(b['ents'][j]):
            ents[j] = b['ents'][j]; filled.append(j)
    out = dmsg_write(old, ents + b['ents'][k:])
    return (out, filled) if (filled or len(b['ents']) > k) else (old, [])
