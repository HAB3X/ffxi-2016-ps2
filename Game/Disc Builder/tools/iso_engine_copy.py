#!/usr/bin/env python3
"""build_patched_iso.py - the engine behind the server app's "Patcher" tab and the "Join a Server" tools.
Pure Python 3 standard library; works on Mac, Windows and Linux. Never prints a password.

Inputs: ONE source disc image (Final Fantasy XI - Adoulin no Makyou (Japan), SLPM-55298) + ONE patch file
("FFXI Definitive Edition 2012.ffxipatch") + server address / account / password.
Outputs: the patched ISO (--out) and the pre-installed PS2 hard drive image for PCSX2 (--hdd-out).

  build_patched_iso.py --list-requirements [--patch PACK]
        JSON on stdout: the source disc image needed (name, title, serial, size, md5) and what the pack holds.
  build_patched_iso.py --source adoulin2012jp=PATH --patch PACK --server IP --account NAME [--password PW]
                       --out OUT.iso [--hdd-out FFXI-HDD.raw] [--variant full|safe] [--port 54001] [--progress] [--skip-md5]
        Builds the patched ISO and (with --hdd-out) unpacks the hard drive image. The source is only read.
  build_patched_iso.py --patch PACK --hdd-out FFXI-HDD.raw [--progress]
        Only unpacks the hard drive image (a 40 GB sparse file that really uses about 9 GB).
  build_patched_iso.py --source adoulin2012jp=PATH --ps2-disc-out OUT.iso [--ps2-data FILE.ffxips2] --server IP --account NAME
                       [--variant full|safe]
        Real PS2: builds the install + play DVD image (3.7 GB). Needs the extra data file in Game/Real PS2/.
  build_patched_iso.py --verify ISO
        JSON on stdout: {"patched": true, "server": ..., "port": ..., "account": ..., "password_set": true}
  build_patched_iso.py --retarget ISO --server IP --account NAME [--password PW] [--port N]
        Changes server/account/password inside an already patched ISO (or a Real PS2 .ELF) in place. No rebuild.

  Password: --password PW, or the environment variable FFXI_PASSWORD (preferred by the GUI: not visible in "ps").
  --progress prints lines "PROGRESS <0-100> <text>".  Exit code 0 = done; otherwise one line "ERROR: reason" on stderr.
  PACK = the .ffxipatch file (a plain zip) or an unpacked patch folder. Default: the *.ffxipatch next to the tools folder.

Limits (the game's own command-line parser): server = dotted IPv4; account and password = printable ASCII without
spaces or '-'; password at most 15 characters; the whole line "-net 3 -ip .. -port .. -accunt .. -pass .." at most
79 characters.
"""
import argparse, glob, hashlib, io, json, os, re, shutil, struct, subprocess, sys, zipfile, zlib

S = 2048
HERE = os.path.dirname(os.path.abspath(__file__))
def default_pack():
    for d in (os.path.join(HERE, '..'), os.path.join(HERE, '..', '..'), HERE):
        c = sorted(glob.glob(os.path.join(d, '*.ffxipatch')))
        if c:
            return c[0]
    return os.path.join(HERE, '..', 'patch-pack')
PROGRESS = False


class Fail(Exception):
    pass


def progress(pct, text):
    if PROGRESS:
        print('PROGRESS %d %s' % (max(0, min(100, int(pct))), text), flush=True)


# ---------------------------------------------------------------- patch pack
class Pack:
    def __init__(self, path):
        self.path = os.path.abspath(path)
        if os.path.isdir(self.path):
            self.zip = None
        elif zipfile.is_zipfile(self.path):
            self.zip = zipfile.ZipFile(self.path)
            names = self.zip.namelist()
            self.prefix = '' if 'manifest.json' in names else next((n[:-len('manifest.json')] for n in names
                                                                   if n.endswith('/manifest.json')), None)
            if self.prefix is None:
                raise Fail('the patch pack has no manifest.json')
        else:
            raise Fail('patch pack not found (a folder or .zip with manifest.json): %s' % path)
        try:
            self.m = json.loads(self.read('manifest.json').decode('utf-8'))
        except (OSError, KeyError, ValueError) as e:
            raise Fail('the patch pack manifest cannot be read: %s' % e)

    def has(self, name):
        if self.zip:
            return (self.prefix + name) in self.zip.namelist()
        return os.path.exists(os.path.join(self.path, name))

    def open(self, name):
        if self.zip:
            return self.zip.open(self.prefix + name)
        return open(os.path.join(self.path, name), 'rb')

    def read(self, name):
        if self.zip:
            return self.zip.read(self.prefix + name)
        with open(os.path.join(self.path, name), 'rb') as f:
            return f.read()


# ---------------------------------------------------------------- ISO9660 helpers
def both32(v):
    return struct.pack('<I', v) + struct.pack('>I', v)


class Iso:
    def __init__(self, f):
        self.f = f
        f.seek(16 * S); pvd = f.read(S)
        if pvd[0:6] != b'\x01CD001':
            raise Fail('not a disc image (no ISO9660 header)')
        self.blocks = struct.unpack('<I', pvd[80:84])[0]
        root = pvd[156:190]
        self.root = (struct.unpack('<I', root[2:6])[0], struct.unpack('<I', root[10:14])[0])

    def listdir(self, ext, size):
        self.f.seek(ext * S); d = self.f.read(size); i = 0; out = {}
        while i < len(d):
            ln = d[i]
            if ln == 0:
                i = (i // S + 1) * S; continue
            r = d[i:i + ln]
            name = bytes(r[33:33 + r[32]]).decode('latin1')
            out[name] = dict(lba=struct.unpack('<I', r[2:6])[0], size=struct.unpack('<I', r[10:14])[0],
                             isdir=bool(r[25] & 2), rec_off=ext * S + i, rec_len=ln)
            i += ln
        return out

    def find(self, path):
        """path like /MODULES/TCP000.ERX (no ;1). Returns the record dict or None."""
        parts = [p for p in path.upper().split('/') if p]
        cur = self.root
        for k, p in enumerate(parts):
            d = self.listdir(*cur)
            e = d.get(p) if k < len(parts) - 1 else (d.get(p + ';1') or d.get(p))
            if not e:
                return None
            cur = (e['lba'], e['size'])
        return e

    def read(self, e):
        self.f.seek(e['lba'] * S)
        return self.f.read(e['size'])


def elf_cmd_offset(h, va, room):
    """file offset of virtual address va inside the ELF whose first bytes are h, or None."""
    if h[:4] != b'\x7fELF':
        return None
    phoff = struct.unpack_from('<I', h, 0x1C)[0]; phes, phn = struct.unpack_from('<HH', h, 0x2A)
    for k in range(phn):
        typ, off, v, pa, fsz, msz, flg, al = struct.unpack_from('<8I', h, phoff + k * phes)
        if typ == 1 and v <= va and va + room <= v + fsz:
            return off + va - v
    return None


CMD_VA, CMD_ROOM = 0x0050F8E0, 80          # the 2012 engine's static command line (patch P3)


def locate_cmdline(f):
    """Absolute file position of the 80-byte command line in a patched ISO or a bare patched ELF."""
    f.seek(0)
    if f.read(4) == b'\x7fELF':
        cands = [0]
    else:
        iso = Iso(f); cands = []
        for p in ('/POL/SCUSBOOT.ELF', '/SLUS_217.04'):          # install+play disc first, then the PCSX2 disc
            e = iso.find(p)
            if e:
                cands.append(e['lba'] * S)
    for base in cands:
        f.seek(base); h = f.read(0x1000)
        off = elf_cmd_offset(h, CMD_VA, CMD_ROOM)
        if off is None:
            continue
        f.seek(base + off); cur = f.read(CMD_ROOM)
        if cur.startswith(b'-net 3 -ip '):
            return base + off, cur
    raise Fail('this is not a patched FFXI Definitive Edition disc (no built-in command line found)')


def parse_cmdline(cur):
    t = cur.split(b'\0')[0].decode('ascii', 'replace')
    m = dict(re.findall(r'-(\w+) (\S+)', t))
    return dict(server=m.get('ip', ''), port=m.get('port', ''), account=m.get('accunt', ''), password=m.get('pass', ''))


def make_cmdline(server, port, account, password):
    p = server.split('.')
    if len(p) != 4 or not all(x.isdigit() and 0 <= int(x) <= 255 for x in p):
        raise Fail('server must be an address like 192.168.1.50')
    if not str(port).isdigit() or not 0 < int(port) < 65536:
        raise Fail('port must be a number')
    for label, v, mx in (('account', account, 40), ('password', password, 15)):
        if not v:
            raise Fail('%s is empty' % label)
        if len(v) > mx:
            raise Fail('%s is too long (at most %d characters)' % (label, mx))
        if not all(33 <= ord(c) <= 126 for c in v) or '-' in v:
            raise Fail('%s may only use plain letters, numbers and symbols without spaces or "-"' % label)
    cmd = ('-net 3 -ip %s -port %s -accunt %s -pass %s' % (server, port, account, password)).encode('ascii')
    if len(cmd) > CMD_ROOM - 1:
        raise Fail('server + account + password are too long together (%d characters, at most %d)' % (len(cmd), CMD_ROOM - 1))
    return cmd.ljust(CMD_ROOM, b'\0')


def retarget(path, server, port, account, password):
    with open(path, 'rb') as f:
        pos, cur = locate_cmdline(f)
    old = parse_cmdline(cur)
    new = make_cmdline(server or old['server'], port or old['port'] or '54001', account or old['account'],
                       password or old['password'])
    try:
        with open(path, 'r+b') as f:
            f.seek(pos); f.write(new); f.flush(); os.fsync(f.fileno())
    except OSError as e:
        raise Fail('cannot write to the disc image (read-only, or open in PCSX2?): %s' % e.strerror)
    with open(path, 'rb') as f:
        f.seek(pos)
        if f.read(CMD_ROOM) != new:
            raise Fail('writing failed (the file did not change)')
    return parse_cmdline(new)


def verify(path):
    with open(path, 'rb') as f:
        try:
            pos, cur = locate_cmdline(f)
        except Fail:
            return dict(patched=False)
    c = parse_cmdline(cur)
    return dict(patched=True, server=c['server'], port=c['port'], account=c['account'], password_set=bool(c['password']))


# ---------------------------------------------------------------- build
def md5_file(path, lo, hi, text):
    h = hashlib.md5(); size = os.path.getsize(path); done = 0
    with open(path, 'rb') as f:
        while True:
            b = f.read(8 << 20)
            if not b:
                break
            h.update(b); done += len(b)
            progress(lo + (hi - lo) * done / max(size, 1), text)
    return h.hexdigest()


def apply_patch_words(elf, text):
    """patches.txt: lines 'ADDR VALUE' (hex, 32-bit words at virtual addresses of the file-backed segment)."""
    out = bytearray(elf)
    phoff = struct.unpack_from('<I', elf, 0x1C)[0]
    typ, off, va, pa, fsz, msz = struct.unpack_from('<6I', elf, phoff)
    n = 0
    for line in text.decode('ascii', 'replace').split('\n'):
        line = line.split('#')[0].strip()
        if not line:
            continue
        a, v = (int(x, 16) for x in line.split()[:2])
        if not va <= a < va + fsz:
            raise Fail('patch address %08X is outside the program file' % a)
        struct.pack_into('<I', out, a - va + off, v); n += 1
    return bytes(out), n


def copy_with_progress(src, dst, lo, hi, text):
    size = os.path.getsize(src)
    if sys.platform == 'darwin':                       # APFS clone: instant and takes no space; falls through if not possible
        try:
            if subprocess.run(['cp', '-c', src, dst], capture_output=True).returncode == 0:
                progress(hi, text); return
        except OSError:
            pass
    done = 0
    with open(src, 'rb') as a, open(dst, 'wb') as b:
        while True:
            blk = a.read(8 << 20)
            if not blk:
                break
            b.write(blk); done += len(blk)
            progress(lo + (hi - lo) * done / max(size, 1), text)


def build(pack, sources, server, port, account, password, out, skip_md5=False, span=(0, 100), variant=None):
    m = pack.m
    variant = variant or m.get('default_variant')
    if variant not in m.get('variants', {}):
        raise Fail('unknown variant "%s" (this patch has: %s)' % (variant, ', '.join(m.get('variant_order', []))))
    var = m['variants'][variant]
    vfiles = m.get('files', []) + var.get('files', [])
    P = lambda pct, text: progress(span[0] + (span[1] - span[0]) * pct / 100.0, text)
    cmd = make_cmdline(server, port or m.get('port', '54001'), account, password)       # validate before any work
    reqs = m['sources']
    names = [r['name'] for r in reqs]
    for k in sources:
        if k not in names:
            raise Fail('unknown source name "%s" (this patch needs: %s)' % (k, ', '.join(names)))
    src = {}
    for r in reqs:
        p = sources.get(r['name'])
        if not p:
            raise Fail('missing source disc image: --source %s=PATH  (%s)' % (r['name'], r['title']))
        if not os.path.isfile(p):
            raise Fail('source file not found: %s' % p)
        if os.path.getsize(p) != r['size']:
            raise Fail('"%s" is not the disc image "%s" (size %d bytes, expected %d)'
                       % (os.path.basename(p), r['title'], os.path.getsize(p), r['size']))
        if not skip_md5:
            global PROGRESS
            keep = PROGRESS
            h = hashlib.md5(); size = r['size']; done = 0
            with open(p, 'rb') as f:
                while True:
                    b = f.read(8 << 20)
                    if not b:
                        break
                    h.update(b); done += len(b); P(35.0 * done / size, 'Checking ' + r['title'])
            if h.hexdigest() != r['md5']:
                raise Fail('"%s" is not the disc image "%s" (different content)' % (os.path.basename(p), r['title']))
        src[r['name']] = p
    base = src[m['base']]
    out = os.path.abspath(out)
    if out in [os.path.abspath(p) for p in src.values()]:
        raise Fail('the output must not be the source image')
    odir = os.path.dirname(out) or '.'
    if not os.path.isdir(odir):
        raise Fail('the output folder does not exist: %s' % odir)
    # the game program: read from the source disc, apply our patch words
    e = var['elf']
    with open(base, 'rb') as f:
        iso = Iso(f); rec = iso.find(e['path'])
        if not rec:
            raise Fail('%s not found on the source disc' % e['path'])
        orig = iso.read(rec)
    if hashlib.md5(orig).hexdigest() != e['source_md5']:
        raise Fail('%s on the source disc is not the expected program' % e['path'])
    elf, n = apply_patch_words(orig, pack.read(e['patches']))
    if hashlib.md5(elf).hexdigest() != e['patched_md5']:
        raise Fail('the patched game program does not match the patch file (md5)')
    off = elf_cmd_offset(elf[:0x1000], CMD_VA, CMD_ROOM)
    if off is None or not elf[off:off + 7] == b'-net 3 ':
        raise Fail('the patched game program has no command line')
    elf = elf[:off] + cmd + elf[off + CMD_ROOM:]
    extra = {x['file']: pack.read(x['file']) for x in vfiles + m.get('inplace', [])}
    for name, data in extra.items():
        if m.get('md5', {}).get(name) and hashlib.md5(data).hexdigest() != m['md5'][name]:
            raise Fail('the patch file is damaged (%s)' % name)
    need = os.path.getsize(base) + len(elf) + (64 << 20)
    part = out + '.part'
    if os.path.exists(part):
        os.remove(part)
    if sys.platform != 'darwin' and shutil.disk_usage(odir).free < need:
        raise Fail('not enough free space for the new ISO (%.1f GB needed)' % (need / 1e9))
    try:
        copy_with_progress(base, part, span[0] + (span[1] - span[0]) * 0.35, span[0] + (span[1] - span[0]) * 0.92, 'Copying the disc')
        os.chmod(part, 0o644)
        with open(part, 'r+b') as f:
            iso = Iso(f)
            if iso.blocks * S != os.path.getsize(part):
                raise Fail('the source disc image has an unexpected size')
            pos = iso.blocks
            jobs = [(m['boot_record'], m.get('boot_rename'), elf)] + [(x['record'], x.get('rename'), extra[x['file']]) for x in vfiles]
            recs = []
            for path, rename, data in jobs:
                r = iso.find(path)
                if not r:
                    raise Fail('%s not found on the source disc' % path)
                recs.append((r, rename, data))
            inpl = []
            for x in m.get('inplace', []):
                r = iso.find(x['record'])
                if not r or len(extra[x['file']]) > (r['size'] + S - 1) // S * S:
                    raise Fail('%s cannot be replaced in place' % x['record'])
                inpl.append((r, extra[x['file']]))
            P(94, 'Adding the patched game')
            for r, rename, data in recs:
                f.seek(pos * S); f.write(data + b'\0' * ((-len(data)) % S))
                f.seek(r['rec_off']); rec = bytearray(f.read(r['rec_len']))
                rec[2:10] = both32(pos); rec[10:18] = both32(len(data))
                if rename:
                    nb = rename.encode('ascii')
                    if len(nb) != rec[32]:
                        raise Fail('rename %s must keep the name length' % rename)
                    rec[33:33 + len(nb)] = nb
                f.seek(r['rec_off']); f.write(bytes(rec))
                pos += (len(data) + S - 1) // S
            for r, data in inpl:
                f.seek(r['lba'] * S); f.write(data + b'\0' * ((-len(data)) % S))
                f.seek(r['rec_off']); rec = bytearray(f.read(r['rec_len'])); rec[10:18] = both32(len(data))
                f.seek(r['rec_off']); f.write(bytes(rec))
            f.seek(16 * S + 80); f.write(both32(pos))
            f.truncate(pos * S); f.flush(); os.fsync(f.fileno())
        P(97, 'Checking the new disc')
        newname = lambda path, rename: ('/'.join(path.split('/')[:-1]) + '/' + rename.split(';')[0]) if rename else path
        with open(part, 'rb') as f:
            iso = Iso(f)
            for path, rename, data in jobs:
                if iso.read(iso.find(newname(path, rename))) != data:
                    raise Fail('check failed: %s on the new disc is wrong' % newname(path, rename))
            for x in m.get('inplace', []):
                if iso.read(iso.find(x['record'])) != extra[x['file']]:
                    raise Fail('check failed: %s on the new disc is wrong' % x['record'])
        os.replace(part, out)
    except BaseException:
        if os.path.exists(part):
            try: os.remove(part)
            except OSError: pass
        raise
    P(100, 'Disc done')
    return out


# ---------------------------------------------------------------- Real PS2 install + play disc
class _Node:
    def __init__(self, name, parent=None):
        self.name, self.parent, self.dirs, self.files = name, parent, {}, {}
        self.lba = self.size = 0


class IsoWriter:
    """Plain ISO9660 the PS2 BIOS loader accepts: NAME.EXT;1, records with 14 system-use bytes, exact directory sizes,
    path tables from sector 257 (Sony layout), 512 zero sectors after the last file (the drive reads ahead)."""
    def __init__(self):
        self.root = _Node('')

    def add(self, path, src):
        """src: bytes | ('file', path, offset, size) | ('pack', Pack, member, size)"""
        parts = path.strip('/').split('/'); node = self.root
        for p in parts[:-1]:
            p = p.upper(); node = node.dirs.setdefault(p, _Node(p, node))
        node.files[parts[-1].upper()] = src

    @staticmethod
    def fsize(src):
        return len(src) if isinstance(src, bytes) else src[3]

    @staticmethod
    def rec(name, lba, size, isdir):
        ln = 33 + len(name); ln += ln & 1; ln += 14
        r = bytearray(ln); r[0] = ln
        r[2:10] = both32(lba); r[10:18] = both32(size)
        r[18:25] = bytes([126, 10, 1, 12, 0, 0, 0]); r[25] = 2 if isdir else 0
        r[28:32] = b'\x01\x00\x00\x01'; r[32] = len(name); r[33:33 + len(name)] = name
        return bytes(r)

    def _names(self, n):
        return sorted([(k.encode(), n.dirs[k], True) for k in n.dirs] + [((k + ';1').encode(), n.files[k], False) for k in n.files],
                      key=lambda x: x[0])

    def _dir_bytes(self, n):
        out = bytearray(); par = n.parent or n
        def put(r):
            nonlocal out
            if (len(out) % S) + len(r) > S: out += b'\0' * (S - len(out) % S)
            out += r
        put(self.rec(b'\0', n.lba, n.size, True)); put(self.rec(b'\1', par.lba, par.size, True))
        for nb, x, isdir in self._names(n):
            put(self.rec(nb, x.lba, x.size, True) if isdir else self.rec(nb, self.flba[id(x)], self.fsize(x), False))
        return bytes(out)

    def write(self, out_path, report=None):
        dirs = []; q = [self.root]
        while q:
            n = q.pop(0); dirs.append(n); q += [n.dirs[k] for k in sorted(n.dirs)]
        self.flba = {}
        for n in dirs:
            ln = 96
            for nb, x, isdir in self._names(n):
                r = 33 + len(nb); r += r & 1; r += 14
                if (ln % S) + r > S: ln += S - ln % S
                ln += r
            n.size = ln
        def ptable(be):
            t = bytearray(); num = {id(n): i + 1 for i, n in enumerate(dirs)}
            for n in dirs:
                nb = n.name.encode() or b'\0'
                t += bytes([len(nb), 0]) + struct.pack('>I' if be else '<I', n.lba) + struct.pack('>H' if be else '<H', num[id(n.parent or n)]) + nb
                if len(nb) & 1: t += b'\0'
            return bytes(t)
        ptlen = len(ptable(False)); ptsec = (ptlen + S - 1) // S
        lba = 257; lpt = lba; lba += 2 * ptsec; mpt = lba; lba += 2 * ptsec
        for n in dirs:
            n.lba = lba; lba += (n.size + S - 1) // S
        order = []
        for n in dirs:
            for k in sorted(n.files):
                src = n.files[k]; self.flba[id(src)] = lba; order.append(src); lba += (self.fsize(src) + S - 1) // S
        total = lba + 512
        with open(out_path, 'wb') as f:
            f.write(b'\0' * (16 * S))
            pvd = bytearray(S); pvd[0:7] = b'\x01CD001\x01'
            pvd[8:40] = b'PLAYSTATION'.ljust(32); pvd[40:72] = b' ' * 32
            pvd[80:88] = both32(total)
            pvd[120:124] = b'\x01\x00\x00\x01'; pvd[124:128] = b'\x01\x00\x00\x01'; pvd[128:132] = b'\x00\x08\x08\x00'
            pvd[132:140] = both32(ptlen)
            pvd[140:144] = struct.pack('<I', lpt); pvd[144:148] = struct.pack('<I', lpt + ptsec)
            pvd[148:152] = struct.pack('>I', mpt); pvd[152:156] = struct.pack('>I', mpt + ptsec)
            rr = bytearray(self.rec(b'\0', self.root.lba, self.root.size, True)[:34]); rr[0] = 34; pvd[156:190] = rr
            pvd[190:813] = b' ' * 623; pvd[574:702] = b'PLAYSTATION'.ljust(128)
            for o_ in (813, 830, 847, 864): pvd[o_:o_ + 17] = b'2026100112000000\x00'
            pvd[881] = 1
            f.write(pvd); f.write(b'\xffCD001\x01' + b'\0' * (S - 7)); f.write(b'\0' * ((lpt - 18) * S))
            for be in (False, False, True, True):
                t = ptable(be); f.write(t + b'\0' * (ptsec * S - len(t)))
            for n in dirs:
                b = self._dir_bytes(n)
                if len(b) != n.size: raise Fail('internal: directory layout')
                f.write(b + b'\0' * ((-len(b)) % S))
            for src in order:
                if f.tell() != self.flba[id(src)] * S: raise Fail('internal: file layout')
                n_ = 0
                if isinstance(src, bytes):
                    f.write(src); n_ = len(src)
                else:
                    g = open(src[1], 'rb') if src[0] == 'file' else src[1].open(src[2])
                    with g:
                        if src[0] == 'file': g.seek(src[2])
                        left = src[3]
                        while left:
                            blk = g.read(min(left, 4 << 20))
                            if not blk: raise Fail('a source file is shorter than expected')
                            f.write(blk); left -= len(blk); n_ += len(blk)
                            if report: report(f.tell() / (total * S))
                f.write(b'\0' * ((-n_) % S))
            f.write(b'\0' * (512 * S))
        return total


def iso_walk(iso, ext, size, prefix=''):
    for name, e in iso.listdir(ext, size).items():
        if name in ('\x00', '\x01'): continue
        if e['isdir']:
            for x in iso_walk(iso, e['lba'], e['size'], prefix + name + '/'): yield x
        else:
            yield prefix + name.split(';')[0], e


def patched_program(pack, base, var, cmd):
    e = var['elf']
    with open(base, 'rb') as f:
        iso = Iso(f); rec = iso.find(e['path'])
        if not rec: raise Fail('%s not found on the source disc' % e['path'])
        orig = iso.read(rec)
    if hashlib.md5(orig).hexdigest() != e['source_md5']:
        raise Fail('%s on the source disc is not the expected program' % e['path'])
    elf, n = apply_patch_words(orig, pack.read(e['patches']))
    if hashlib.md5(elf).hexdigest() != e['patched_md5']:
        raise Fail('the patched game program does not match the patch file (md5)')
    off = elf_cmd_offset(elf[:0x1000], CMD_VA, CMD_ROOM)
    return orig, elf[:off] + cmd + elf[off + CMD_ROOM:]


def build_ps2_disc(pack, data, source, server, port, account, password, out, variant=None, span=(0, 100)):
    """The Real PS2 install + play DVD image: Square Enix's 2012 installer (patched) as the boot program; it installs the
    whole Definitive Edition on an empty PS2 hard drive, and starts the patched game when the data is installed."""
    m = pack.m; dm = data.m
    if dm.get('format') != 'ffxips2data-1': raise Fail('the Real PS2 data file is not the expected kind')
    variant = variant or m.get('default_variant')
    if variant not in m.get('variants', {}): raise Fail('unknown variant "%s"' % variant)
    var = m['variants'][variant]
    cmd = make_cmdline(server, port or m.get('port', '54001'), account, password)
    r = m['sources'][0]
    if not os.path.isfile(source) or os.path.getsize(source) != r['size']:
        raise Fail('the source is not the disc image "%s"' % r['title'])
    orig, game = patched_program(pack, source, var, cmd)
    inst, n = apply_patch_words(orig, data.read(dm['installer']['patches']))
    w = IsoWriter()
    with open(source, 'rb') as f:
        iso = Iso(f)
        for path, e in iso_walk(iso, *iso.root):
            top = path.split('/')[0]
            if top in ('CDROM', 'MODULES') or path in ('CDNAME.DAT', 'CDTABLE.DAT', 'ICON.DAT', 'LICENSE.TXT', 'CONFIG.SYS', 'OPN.DAT'):
                w.add(path, ('file', source, e['lba'] * S, e['size']))
            if path == 'CONFIG.SYS':
                w.add('CONFIGU.SYS', ('file', source, e['lba'] * S, e['size']))
    w.add('SYSTEM.CNF', pack.read('SYSTEM.CNF'))
    w.add('SLUS_217.04', inst)
    w.add('POL/SCUSBOOT.ELF', game)
    w.add('MODULES/TCP005.ERX', pack.read('tcp005.erx')); w.add('MODULES/NDI002.ERX', pack.read('ndi002.erx'))
    for x in var.get('files', []):
        if x.get('rename'): w.add(x['rename'].split(';')[0], pack.read(x['file']))       # DANCER.BIN (full variant)
    names = data.zip.namelist() if data.zip else None
    if names is None: raise Fail('the Real PS2 data must be the .ffxips2 file')
    for nm in names:
        rel = nm[len(data.prefix):]
        if rel.startswith('disc/') and not rel.endswith('/'):
            w.add(rel[5:], ('pack', data, rel, data.zip.getinfo(nm).file_size))
    out = os.path.abspath(out); part = out + '.part'
    if shutil.disk_usage(os.path.dirname(out) or '.').free < 4 * 10 ** 9:
        raise Fail('not enough free space for the Real PS2 disc image (4 GB needed)')
    try:
        total = w.write(part, lambda fr: progress(span[0] + (span[1] - span[0]) * fr, 'Writing the Real PS2 disc'))
        if total * S > 4700372992: raise Fail('internal: the disc image is larger than a DVD-R')
        os.replace(part, out)
    except BaseException:
        if os.path.exists(part):
            try: os.remove(part)
            except OSError: pass
        raise
    return out


def set_sparse(f):
    """Windows/NTFS: mark the file sparse so skipped zero blocks take no space. Elsewhere holes are automatic."""
    if os.name != 'nt':
        return True
    try:
        import ctypes, msvcrt
        from ctypes import wintypes
        h = msvcrt.get_osfhandle(f.fileno()); ret = wintypes.DWORD(0)
        return bool(ctypes.windll.kernel32.DeviceIoControl(wintypes.HANDLE(h), 0x000900C4, None, 0, None, 0, ctypes.byref(ret), None))
    except Exception:
        return False


def unpack_hdd(pack, dest, span=(0, 100)):
    h = pack.m.get('hdd')
    if not h:
        raise Fail('this patch file holds no hard drive image')
    dest = os.path.abspath(dest); ddir = os.path.dirname(dest)
    if not os.path.isdir(ddir):
        raise Fail('the folder for the hard drive image does not exist: %s' % ddir)
    raw = h['raw_size']; tmp = dest + '.unpacking'
    CH = 1 << 20; ZERO = bytes(CH)
    d = zlib.decompressobj(16 + zlib.MAX_WBITS); md = hashlib.md5(); pos = 0; nxt = 0
    try:
        with pack.open(h['file']) as src, open(tmp, 'wb') as out:
            sparse = set_sparse(out)
            free = shutil.disk_usage(ddir).free
            if free < (h['used_bytes'] if sparse else raw) + (1 << 30):
                raise Fail('not enough free space for the hard drive image: %.0f GB needed in %s'
                           % (((h['used_bytes'] if sparse else raw) + (1 << 30)) / 1e9, ddir))
            pend = b''
            def emit(buf):
                nonlocal pos
                if sparse and buf == ZERO[:len(buf)]:
                    out.seek(len(buf), 1)
                else:
                    out.write(buf)
                pos += len(buf)
            while True:
                data = src.read(1 << 20)
                if not data:
                    break
                md.update(data)
                while data:
                    pend += d.decompress(data, CH)
                    data = d.unconsumed_tail
                    if len(pend) >= CH:
                        emit(pend[:CH]); pend = pend[CH:]
                if pos >= nxt:
                    nxt = pos + (256 << 20)
                    progress(span[0] + (span[1] - span[0]) * pos / raw, 'Unpacking the PS2 hard drive')
            pend += d.flush()
            while pend:
                emit(pend[:CH]); pend = pend[CH:]
            out.truncate(pos)
        if not d.eof or pos != raw or md.hexdigest() != h['md5']:
            raise Fail('the hard drive image inside the patch file is damaged (copy the patch file again)')
        os.replace(tmp, dest)
    except BaseException:
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except OSError: pass
        raise
    progress(span[1], 'Hard drive done')
    return dest


def main():
    global PROGRESS
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--list-requirements', action='store_true'); ap.add_argument('--patch')
    ap.add_argument('--source', action='append', default=[], metavar='NAME=PATH')
    ap.add_argument('--server'); ap.add_argument('--port'); ap.add_argument('--account'); ap.add_argument('--password')
    ap.add_argument('--out'); ap.add_argument('--hdd-out'); ap.add_argument('--ps2-disc-out'); ap.add_argument('--ps2-data'); ap.add_argument('--progress', action='store_true')
    ap.add_argument('--skip-md5', action='store_true')
    ap.add_argument('--variant', help='program variant from the patch file (default: its default, "full"); "safe" = no 3D character preview, no M3K')
    ap.add_argument('--verify', metavar='ISO'); ap.add_argument('--retarget', metavar='ISO')
    a = ap.parse_args()
    PROGRESS = a.progress
    pw = a.password if a.password is not None else os.environ.get('FFXI_PASSWORD')
    try:
        if a.verify:
            print(json.dumps(verify(a.verify))); return 0
        if a.retarget:
            if not (a.server or a.account or pw or a.port):
                raise Fail('--retarget needs --server and/or --account/--password')
            r = retarget(a.retarget, a.server, a.port, a.account, pw)
            print(json.dumps(dict(patched=True, server=r['server'], port=r['port'], account=r['account'], password_set=True)))
            return 0
        pack = Pack(a.patch or default_pack())
        m = pack.m
        if a.list_requirements:
            h = m.get('hdd') or {}
            print(json.dumps(dict(pack=m.get('name'), version=m.get('version'), output_name=m.get('output_name'),
                                  sources=m['sources'],
                                  variants=[dict(name=k, title=m['variants'][k].get('title'), default=(k == m.get('default_variant')))
                                            for k in m.get('variant_order', [])],
                                  features=m.get('features', []),
                                  hdd_image=bool(h), hdd_name=h.get('name'),
                                  hdd_size=h.get('raw_size'), hdd_disk_use=h.get('used_bytes'),
                                  notes=m.get('notes', [])), indent=1))
            return 0
        if not a.out and not a.hdd_out and not a.ps2_disc_out:
            raise Fail('nothing to do: give --out (the ISO), --hdd-out (the hard drive image) and/or --ps2-disc-out; see --help')
        res = {}
        if a.ps2_disc_out:
            if not (a.server and a.account and pw):
                raise Fail('a build needs --server, --account and a password (--password or FFXI_PASSWORD)')
            src = dict(x.split('=', 1) for x in a.source if '=' in x).get(m['base'])
            if not src: raise Fail('missing source disc image: --source %s=PATH' % m['base'])
            df = a.ps2_data or next(iter(sorted(glob.glob(os.path.join(HERE, '..', 'Real PS2', '*.ffxips2')))), None)
            if not df or not os.path.exists(df): raise Fail('the Real PS2 data file (*.ffxips2) was not found; give --ps2-data FILE')
            res['ps2_disc'] = build_ps2_disc(pack, Pack(df), os.path.expanduser(src), a.server, a.port, a.account, pw, a.ps2_disc_out, a.variant)
            res['ps2_disc_set_to'] = verify(res['ps2_disc'])
        if a.out:
            if not (a.server and a.account and pw):
                raise Fail('a build needs --server, --account and a password (--password or FFXI_PASSWORD)')
            srcs = {}
            for s_ in a.source:
                if '=' not in s_:
                    raise Fail('--source must be NAME=PATH')
                k, v = s_.split('=', 1); srcs[k] = os.path.expanduser(v)
            out = build(pack, srcs, a.server, a.port, a.account, pw, a.out, a.skip_md5, (0, 40) if a.hdd_out else (0, 100), a.variant)
            res.update(out=out, variant=a.variant or m.get('default_variant'), **verify(out))
        if a.hdd_out:
            res['hdd'] = unpack_hdd(pack, os.path.expanduser(a.hdd_out), (40, 100) if a.out else (0, 100))
        progress(100, 'Done')
        print(json.dumps(res))
        return 0
    except Fail as e:
        print('ERROR: %s' % e, file=sys.stderr); return 1
    except OSError as e:
        print('ERROR: %s' % (e.strerror or e), file=sys.stderr); return 1


if __name__ == '__main__':
    sys.exit(main())
