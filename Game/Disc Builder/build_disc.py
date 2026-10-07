#!/usr/bin/env python3
"""build_2016_install_disc_v3.py (6 Oct 2026, v3 = Square Enix's installer + packed CONTAINER data copied as plain records)
build_2016_install_disc.py - the FFXI 2016 INSTALL + PLAY DVD for a PS2 with a hard drive (and for PCSX2 tests).

One single-layer DVD that installs the 2016 game data onto the PS2 hard drive with Square Enix's own 2012 installer
(the Adoulin disc's INSTALL.ELF in installer mode, patched: install_2016_disc.pnach) and then boots the 2016 host
(work/b52_installer/host: the C host that runs the unlocked 2016 program ffxi_pol.pex without PlayOnline).

Disc layout (plain ISO9660, PS2 style NAME.EXT;1):
  SYSTEM.CNF               BOOT2 = cdrom0:\\SLUS_217.04;1
  SLUS_217.04              the Adoulin INSTALL.ELF (md5 2b196919...) + the patch words of install_2016_disc.pnach
  POL/SCUSBOOT.ELF         the 2016 host ELF (stripped); the installer's LoadExecPS2 path
  MODULES/                 the Adoulin disc's IOP modules (IOPRP.IMG, SQIOPMEM, SCE000-002, HID000 ... used by installer
                           and host) + TCP005.ERX / NDI002.ERX from the data tree
  CDROM/ CDNAME.DAT CDTABLE.DAT ICON.DAT LICENSE.TXT CONFIG.SYS (+CONFIGU.SYS)   installer resources (Adoulin disc)
  HDD.SYS                  -> pfs1:/config.sys      DATA/PATCH.VER, DATA/FILE.TXT -> the installer writes them to
                           /image/ffxi/pfs1:/patch.ver and /file.txt (a folder literally named "pfs1:", as on the 2012
                           drives); the 2016 program reads /patch.ver, so patch.ver is also a MISC record (../../patch.ver)
  DATA/ROMn/ROMn.DAT       romarc LZ streams (the installer's own codec), one per file ROMn/<dir>/<file>.DAT, ascending
                           path code dir*128+file; STABLEn.DAT = u32 raw size per path code (0 = no file)
  DATA/ROMn/FTABLEn.DAT, VTABLEn.DAT   the tables (copied as they are)
  DATA/ROMn/MISCn.DAT      uncompressed records {u32 0x104+len, name[0x100] (relative to /image/ffxi), data}: sound, pol,
                           prog, SYS, res (as ../../res/...), the ROM10-13 tables, and the 2016 marker SYS/FFXI2016.VER
                           (last record of MISC9; the boot decision starts the host only when it exists)
No opening movie (OPN.DAT): the 2016 program does not play it.

Input = a data tree = the root of the FFXI partition (config.sys, patch.ver, res/, image/ffxi/...), e.g. made with
  python3 research/tools/pfs_native.py DRIVE.raw extract PP.SCUS-97266.0001.FFXI OUTDIR
Run-time / personal files are never put on the disc (--exclude defaults: image/ffxi/USER/, image/ffxi/TEMP/,
SYS/lb*.bin, SYS/err*.bin, every *.enc). Any file layout works (also an already-compressed tree for a host that decodes
at load time): files are installed byte for byte.

usage: build_2016_install_disc.py --tree DIR --out OUT.iso [--host-elf host/host2016.elf] [--adoulin ISO]
                                  [--work DIR] [--jobs 8] [--chain 1024] [--verify] [--exclude REGEX ...]
The result is reproducible: the same inputs give a byte-identical ISO (fixed dates, sorted order, deterministic packer).
"""
import argparse, hashlib, os, re, struct, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(HERE, 'tools'))
import iso_engine_copy as eng                      # ISO9660 reader of the release engine (copy)
ADOULIN = os.path.join(ROOT, 'work/b41_release/adoulin/Final Fantasy XI - Adoulin no Makyou (Japan).iso')
INSTALL_MD5 = '2b1969190e0566b0d8d3133e2987df19'
S = 2048
DVD5 = 4700372992                                   # single-layer DVD-R: 2,295,104 sectors
DEFAULT_EXCLUDES = [r'^image/ffxi/USER(/|$)', r'^image/ffxi/TEMP(/|$)', r'^image/ffxi/SYS/lb\d+\.bin$',
                    r'^image/ffxi/SYS/err\d+\.bin$', r'\.enc$', r'(^|/)\.']
MARKER = 'SYS/FFXI2016.VER'


def die(m): sys.exit('ERROR: ' + m)
def setname(n): return 'ROM' if n == 1 else 'ROM%d' % n
def sfx(n): return '' if n == 1 else str(n)


def md5_file(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''): h.update(b)
    return h.hexdigest()


# ------------------------------------------------------------------ data tree -> install plan
def scan_tree(tree, excludes):
    rx = [re.compile(x) for x in excludes]
    files, skipped = [], []
    for r, ds, fs in os.walk(tree):
        ds.sort()
        for f in sorted(fs):
            rel = os.path.relpath(os.path.join(r, f), tree).replace(os.sep, '/')
            (skipped if any(x.search(rel) for x in rx) else files).append(rel)
    return sorted(files), skipped


def plan(tree, files):
    """-> dict: sets {n: {code: rel}}, tables {(n, 'FTABLE'|'VTABLE'): rel}, misc [(name, rel)], hdd_sys, patch_ver"""
    P = dict(sets={n: {} for n in range(1, 10)}, tables={}, misc=[], hdd_sys=None, patch_ver=None)
    for rel in files:
        m = re.match(r'^image/ffxi/(ROM(\d*))/(\d+)/(\d+)\.DAT$', rel)
        n = (int(m.group(2)) if m.group(2) else 1) if m else None
        if m and 1 <= n <= 9:
            d, f = int(m.group(3)), int(m.group(4))
            if f > 127: die('file number > 127: ' + rel)
            if os.path.getsize(os.path.join(tree, rel)) == 0:     # STABLE 0 means "no file": install empty files as MISC
                P['misc'].append((rel[len('image/ffxi/'):], rel)); continue
            P['sets'][n][d * 128 + f] = rel; continue
        m = re.match(r'^image/ffxi/(?:ROM(\d)/)?(FTABLE|VTABLE)(\d*)\.DAT$', rel)
        if m and (m.group(1) or '') == m.group(3) and (m.group(1) or '1') != '0' and (not m.group(1) or 2 <= int(m.group(1)) <= 9):
            P['tables'][(int(m.group(1) or 1), m.group(2))] = rel; continue
        if rel == 'config.sys': P['hdd_sys'] = rel; continue
        if rel == 'patch.ver':                  # the installer copies DATA/PATCH.VER to image/ffxi/pfs1:/patch.ver (sic); the 2016
            P['patch_ver'] = rel                 # program reads pfs1:/patch.ver, so it also goes in as a MISC record at the root
            P['misc'].append(('../../patch.ver', rel)); continue
        name = rel[len('image/ffxi/'):] if rel.startswith('image/ffxi/') else '../../' + rel
        if len(name.encode()) > 0xFF: die('MISC name too long: ' + name)
        if os.path.getsize(os.path.join(tree, rel)) >= (6 << 20) - 0x104: die('MISC file >= 6 MB (installer buffer): ' + rel)
        P['misc'].append((name, rel))
    for n in range(1, 10):
        for t in ('FTABLE', 'VTABLE'):
            if (n, t) not in P['tables']: die('missing table %s%s for set %d' % (t, sfx(n), n))
        if not P['sets'][n]: die('set %s has no files' % setname(n))
    if not P['hdd_sys'] or not P['patch_ver']: die('the tree needs config.sys and patch.ver at its root')
    return P


def misc_sets(misc, tree=None):
    """v3: spread the MISC records over the 9 per-set archives (the installer writes them all the same way), largest first onto
    the archive with the fewest bytes, so every MISCn.DAT stays far below 2 GB (the 2012 installer fails with "An error occurred
    while reading special files" on a 2.76 GB MISC.DAT - a signed 32-bit size)."""
    out = {n: [] for n in range(1, 10)}; tot = {n: 0 for n in range(1, 10)}
    sz = lambda rel: os.path.getsize(os.path.join(tree, rel)) if tree and isinstance(rel, str) else 0
    for name, rel in sorted(misc, key=lambda x: -sz(x[1])):
        n = min(tot, key=lambda k: (tot[k], k)); out[n].append((name, rel)); tot[n] += sz(rel) + 0x104
    for n in out: out[n].sort(key=lambda x: x[0])            # path order inside each archive (directories fill in order)
    return out


# ------------------------------------------------------------------ packing
def encode_all(tree, items, work, jobs, chain):
    """items: {md5: rel}. Writes work/lz/<md5>.lz (cache by content), returns the lz dir."""
    lz = os.path.join(work, 'lz'); st = os.path.join(work, 'stage'); os.makedirs(lz, exist_ok=True); os.makedirs(st, exist_ok=True)
    todo = []
    for h, rel in items.items():
        if os.path.exists(os.path.join(lz, h + '.lz')): continue
        ln = os.path.join(st, h)
        if os.path.lexists(ln): os.remove(ln)
        os.symlink(os.path.abspath(os.path.join(tree, rel)), ln)
        todo.append((os.path.getsize(os.path.join(tree, rel)), ln))
    if not todo: return lz
    todo.sort(reverse=True)
    lists = [[] for _ in range(jobs)]
    for i, (_, ln) in enumerate(todo): lists[i % jobs].append(ln)
    procs = []
    for j, L in enumerate(lists):
        if not L: continue
        lp = os.path.join(work, 'list%d.txt' % j); open(lp, 'w').write('\n'.join(L) + '\n')
        procs.append(subprocess.Popen(['nice', '-n', '19', os.path.join(HERE, 'tools', 'romarc_opt'), lp, lz, str(chain)],
                                      stdout=open(os.path.join(work, 'enc%d.log' % j), 'w')))
    print('encoding %d distinct files (%.0f MB) with %d jobs...' % (len(todo), sum(s for s, _ in todo) / 1e6, len(procs)), flush=True)
    for p in procs:
        if p.wait(): die('romarc_opt failed')
    for _, ln in todo:
        if not os.path.exists(os.path.join(lz, os.path.basename(ln) + '.lz')): die('no packed stream for ' + ln)
    return lz


def build_misc(tree, recs, path):
    """v3: returns ('parts', [...]) - small record-header files written next to path, data files streamed into the ISO"""
    hd = path + '.hdr'; os.makedirs(hd, exist_ok=True); parts = []
    for i, (name, src) in enumerate(recs):
        if isinstance(src, bytes):
            fp = os.path.join(hd, '%05d.data' % i); open(fp, 'wb').write(src)
        else: fp = src if os.path.isabs(src) else os.path.join(tree, src)
        nb = name.encode('ascii'); hp = os.path.join(hd, '%05d.hdr' % i)
        open(hp, 'wb').write(struct.pack('<I', 0x104 + os.path.getsize(fp)) + nb.ljust(0x100, b'\0'))
        parts += [hp, fp]
    return ('parts', parts)


# ------------------------------------------------------------------ ISO9660 writer (Sony-style layout, from work/b41_release)
class Node:
    def __init__(self, name, parent=None):
        self.name, self.parent, self.dirs, self.files = name, parent, {}, {}
        self.lba = self.size = 0


class IsoWriter:
    def __init__(self): self.root = Node('')

    def add(self, path, src):
        """src: bytes | filesystem path | ('parts', [paths]) | ('slice', path, offset, size)"""
        parts = path.strip('/').split('/'); node = self.root
        for p in parts[:-1]:
            p = p.upper(); node = node.dirs.setdefault(p, Node(p, node))
        node.files[parts[-1].upper()] = src

    @staticmethod
    def fsize(src):
        if isinstance(src, bytes): return len(src)
        if isinstance(src, str): return os.path.getsize(src)
        if src[0] == 'parts': return sum(os.path.getsize(p) for p in src[1])
        return src[3]

    @staticmethod
    def rec(name, lba, size, isdir):
        nb = name; ln = 33 + len(nb); ln += ln & 1; ln += 14
        r = bytearray(ln); r[0] = ln
        r[2:10] = struct.pack('<I', lba) + struct.pack('>I', lba); r[10:18] = struct.pack('<I', size) + struct.pack('>I', size)
        r[18:25] = bytes([126, 10, 6, 12, 0, 0, 40]); r[25] = 2 if isdir else 0
        r[28:32] = struct.pack('<H', 1) + struct.pack('>H', 1); r[32] = len(nb); r[33:33 + len(nb)] = nb
        return bytes(r)

    def dir_bytes(self, node):
        items = [(n.encode(), d, True) for n, d in node.dirs.items()] + [((n + ';1').encode(), s, False) for n, s in node.files.items()]
        items.sort(key=lambda x: x[0])
        out = bytearray(); par = node.parent or node
        def put(r):
            nonlocal out
            if (len(out) % S) + len(r) > S: out += b'\0' * (S - len(out) % S)
            out += r
        put(self.rec(b'\0', node.lba, node.size, True)); put(self.rec(b'\1', par.lba, par.size, True))
        for nb, x, isdir in items:
            if isdir: put(self.rec(nb, x.lba, x.size, True))
            else: put(self.rec(nb, self.flba[id(x)], self.fsize(x), False))
        return bytes(out)

    @staticmethod
    def _acc(ln, r):
        if (ln % S) + r > S: ln += S - ln % S
        return ln + r

    def layout(self):
        dirs = []; q = [self.root]
        while q:
            n = q.pop(0); dirs.append(n); q += [n.dirs[k] for k in sorted(n.dirs)]
        self.flba = {}
        for n in dirs:
            ln = 96
            for nb in sorted([k.encode() for k in n.dirs] + [(k + ';1').encode() for k in n.files]):
                ln_ = 33 + len(nb); ln_ += ln_ & 1; ln_ += 14; ln = self._acc(ln, ln_)
            n.size = ln
        self.dirs = dirs
        ptlen = len(self.ptable(False)); ptsec = (ptlen + S - 1) // S
        lba = 257; self.lpt = lba; lba += 2 * ptsec; self.mpt = lba; lba += 2 * ptsec
        for n in dirs: n.lba = lba; lba += (n.size + S - 1) // S
        self.order = []
        for n in dirs:
            for k in sorted(n.files):
                src = n.files[k]; self.flba[id(src)] = lba; self.order.append(src); lba += (self.fsize(src) + S - 1) // S
        self.ptlen, self.ptsec = ptlen, ptsec
        self.total = lba + 512                       # trailing zero sectors: the drive reads ahead past the last file
        return self.total

    def ptable(self, be):
        t = bytearray(); num = {id(n): i + 1 for i, n in enumerate(self.dirs)}
        for n in self.dirs:
            nb = n.name.encode() or b'\0'
            t += bytes([len(nb), 0]) + struct.pack('>I' if be else '<I', n.lba) + struct.pack('>H' if be else '<H', num[id(n.parent or n)]) + nb
            if len(nb) & 1: t += b'\0'
        return bytes(t)

    def write(self, out_path, volid):
        total = self.layout(); ptsec, ptlen, lpt, mpt = self.ptsec, self.ptlen, self.lpt, self.mpt
        with open(out_path, 'wb') as f:
            f.write(b'\0' * (16 * S))
            pvd = bytearray(S); pvd[0:7] = b'\x01CD001\x01'
            pvd[8:40] = b'PLAYSTATION'.ljust(32); pvd[40:72] = volid.encode().ljust(32)
            pvd[80:88] = struct.pack('<I', total) + struct.pack('>I', total)
            pvd[120:124] = b'\x01\x00\x00\x01'; pvd[124:128] = b'\x01\x00\x00\x01'; pvd[128:132] = b'\x00\x08\x08\x00'
            pvd[132:140] = struct.pack('<I', ptlen) + struct.pack('>I', ptlen)
            pvd[140:144] = struct.pack('<I', lpt); pvd[144:148] = struct.pack('<I', lpt + ptsec)
            pvd[148:152] = struct.pack('>I', mpt); pvd[152:156] = struct.pack('>I', mpt + ptsec)
            rr = bytearray(self.rec(b'\0', self.root.lba, self.root.size, True)[:34]); rr[0] = 34; pvd[156:190] = rr
            pvd[190:318] = b' ' * 128; pvd[318:446] = b' ' * 128; pvd[446:574] = b' ' * 128
            pvd[574:702] = b'PLAYSTATION'.ljust(128); pvd[702:813] = b' ' * 111
            for o_ in (813, 830, 847, 864): pvd[o_:o_ + 17] = b'2026100600000000\x00'
            pvd[881] = 1
            f.write(pvd); f.write(b'\xffCD001\x01' + b'\0' * (S - 7))
            f.write(b'\0' * ((lpt - 18) * S))
            for be in (False, False, True, True):
                t = self.ptable(be); f.write(t + b'\0' * (ptsec * S - len(t)))
            for n in self.dirs:
                b = self.dir_bytes(n)
                if len(b) != n.size: die('directory size mismatch for /%s' % n.name)
                f.write(b + b'\0' * ((-len(b)) % S))
            done = 0; t0 = time.time()
            for src in self.order:
                if f.tell() != self.flba[id(src)] * S: die('layout error')
                n_ = 0
                if isinstance(src, bytes): f.write(src); n_ = len(src)
                else:
                    if isinstance(src, str): chunks = [(src, 0, os.path.getsize(src))]
                    elif src[0] == 'parts': chunks = [(p, 0, os.path.getsize(p)) for p in src[1]]
                    else: chunks = [(src[1], src[2], src[3])]
                    for p, off, sz in chunks:
                        with open(p, 'rb') as g:
                            g.seek(off); left = sz
                            while left:
                                blk = g.read(min(left, 8 << 20))
                                if not blk: die('short read ' + p)
                                f.write(blk); left -= len(blk); n_ += len(blk)
                f.write(b'\0' * ((-n_) % S)); done += n_
            f.write(b'\0' * (512 * S))
            if f.tell() != total * S: die('size error')
        return total


# ------------------------------------------------------------------ installer program
def patched_installer(iso_path, pnach):
    with open(iso_path, 'rb') as f:
        iso = eng.Iso(f); e = iso.find('/INSTALL.ELF')
        if not e: die('INSTALL.ELF not found on the Adoulin disc')
        elf = bytearray(iso.read(e))
    if hashlib.md5(elf).hexdigest() != INSTALL_MD5: die('INSTALL.ELF on the source disc is not the expected program')
    phoff, phnum = struct.unpack_from('<I', elf, 0x1C)[0], struct.unpack_from('<H', elf, 0x2C)[0]
    segs = []
    for i in range(phnum):
        t, off, va, pa, fsz = struct.unpack_from('<5I', elf, phoff + 32 * i)
        if t == 1: segs.append((va, off, fsz))
    n = 0
    for l in open(pnach):
        m = re.match(r'^patch=\d,EE,([0-9A-Fa-f]{8}),word,([0-9A-Fa-f]{8})', l)
        if not m: continue
        va, v = int(m.group(1), 16), int(m.group(2), 16)
        for sva, off, fsz in segs:
            if sva <= va < sva + fsz: struct.pack_into('<I', elf, off + va - sva, v); n += 1; break
        else: die('patch address %08X outside the file' % va)
    return bytes(elf), n


def stripped_host(elf, work):
    out = os.path.join(work, 'SCUSBOOT.ELF')
    strip = os.path.expanduser('~/ps2dev/ee/bin/mips64r5900el-ps2-elf-strip')
    subprocess.run([strip, '-o', out, elf], check=True)      # debug sections only (they carry build paths); load segments unchanged
    d = open(out, 'rb').read()
    if d[:4] != b'\x7fELF': die('host ELF?')
    return out


# ------------------------------------------------------------------ verification (decode what is on the disc)
def verify_iso(iso_path, P, manifest, work):
    """decode every DATA/ROMn/ROMn.DAT with the romarc decoder and read every MISC record: each installed file must have
    the md5 of the source; tables / HDD.SYS / PATCH.VER byte-identical."""
    bad = 0; checked = 0
    with open(iso_path, 'rb') as f:
        iso = eng.Iso(f)
        def get(path):
            e = iso.find(path)
            if not e: die('verify: %s missing on the disc' % path)
            return e
        for n in range(1, 10):
            d = '/DATA/%s/' % setname(n)
            st = iso.read(get(d + 'STABLE%s.DAT' % sfx(n))); codes = [c for c in range(len(st) // 4) if struct.unpack_from('<I', st, 4 * c)[0]]
            if sorted(P['sets'][n]) != codes: die('verify: STABLE%s codes differ from the plan' % sfx(n))
            e = get(d + '%s.DAT' % setname(n))
            tmp_r = os.path.join(work, 'v_rom.dat'); tmp_s = os.path.join(work, 'v_stable.dat')
            with open(tmp_r, 'wb') as o:
                f.seek(e['lba'] * S); left = e['size']
                while left:
                    b = f.read(min(left, 8 << 20)); o.write(b); left -= len(b)
            open(tmp_s, 'wb').write(st)
            p = subprocess.Popen([os.path.join(HERE, 'tools', 'romdec'), tmp_r, tmp_s], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            for c in codes:
                sz = struct.unpack_from('<I', st, 4 * c)[0]; h = hashlib.md5(); left = sz
                while left:
                    b = p.stdout.read(min(left, 8 << 20))
                    if not b: break
                    h.update(b); left -= len(b)
                rel = P['sets'][n][c]; checked += 1
                if left or h.hexdigest() != manifest[rel][1]: bad += 1; print('  BAD stream %s (code %d)' % (rel, c))
            p.stdout.close(); p.wait(); os.remove(tmp_r); os.remove(tmp_s)
            for t in ('FTABLE', 'VTABLE'):
                checked += 1
                if hashlib.md5(iso.read(get(d + '%s%s.DAT' % (t, sfx(n))))).hexdigest() != manifest[P['tables'][(n, t)]][1]:
                    bad += 1; print('  BAD table %s%s' % (t, sfx(n)))
            me = get(d + 'MISC%s.DAT' % sfx(n)); i = 0; mbase = me['lba'] * S
            while i < me['size']:
                f.seek(mbase + i); h_ = f.read(0x104)
                tot = struct.unpack_from('<I', h_, 0)[0]; name = h_[4:0x104].split(b'\0')[0].decode(); data = f.read(tot - 0x104)
                i += tot; checked += 1
                rel = ('image/ffxi/' + name) if not name.startswith('../../') else name[6:]
                if name == MARKER: continue
                if rel not in manifest or hashlib.md5(data).hexdigest() != manifest[rel][1]: bad += 1; print('  BAD misc record ' + name)
            print('  %s verified' % setname(n), flush=True)
        for disc, rel in (('/HDD.SYS', P['hdd_sys']), ('/DATA/PATCH.VER', P['patch_ver'])):
            checked += 1
            if hashlib.md5(iso.read(get(disc))).hexdigest() != manifest[rel][1]: bad += 1; print('  BAD ' + disc)
    return checked, bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tree', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--host-elf', default=os.path.join(HERE, 'host', 'host2016.elf'))
    ap.add_argument('--adoulin', default=ADOULIN); ap.add_argument('--pnach', default=os.path.join(HERE, 'install_2016_disc.pnach'))
    ap.add_argument('--work', default=os.path.join(HERE, 'build', 'disc_work')); ap.add_argument('--jobs', type=int, default=8)
    ap.add_argument('--chain', type=int, default=1024); ap.add_argument('--verify', action='store_true')
    ap.add_argument('--exclude', action='append', default=None, help='regex on tree-relative paths (replaces the defaults)')
    ap.add_argument('--label', default='FFXI_2016_INSTALL')
    ap.add_argument('--override', default=None, help='folder with replacement disc files by ISO path (e.g. CDROM/0/17.DAT)')
    a = ap.parse_args(); t0 = time.time(); os.makedirs(a.work, exist_ok=True)
    tree = os.path.abspath(a.tree)
    files, skipped = scan_tree(tree, a.exclude if a.exclude is not None else DEFAULT_EXCLUDES)
    print('tree %s: %d files to install, %d left out (run-time / personal / locked)' % (tree, len(files), len(skipped)))
    P = plan(tree, files)
    # manifest = what the drive must hold afterwards (md5 per file); its md5 is the data id written into the marker
    print('hashing...', flush=True)
    manifest = {rel: (os.path.getsize(os.path.join(tree, rel)), md5_file(os.path.join(tree, rel))) for rel in files}
    man_txt = ''.join('%s\t%d\t%s\n' % (rel, manifest[rel][0], manifest[rel][1]) for rel in files)
    data_id = hashlib.md5(man_txt.encode()).hexdigest()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or '.', exist_ok=True)
    open(a.out + '.manifest.tsv', 'w').write(man_txt)
    host = stripped_host(os.path.abspath(a.host_elf), a.work); host_md5 = md5_file(host)
    marker = ('FFXI 2016 install disc\nprogram ver.20160203_0 (2016 host, md5 %s)\ndata %s (%d files)\n' % (host_md5, data_id, len(files))).encode()
    # pack
    uniq = {}
    for n in range(1, 10):
        for c, rel in P['sets'][n].items(): uniq.setdefault(manifest[rel][1], rel)
    lz = encode_all(tree, uniq, a.work, a.jobs, a.chain)
    # disc
    w = IsoWriter()
    with open(a.adoulin, 'rb') as f:
        iso = eng.Iso(f)
        for path, e in eng.iso_walk(iso, *iso.root):
            top = path.split('/')[0]
            if top in ('CDROM', 'MODULES') or path in ('CDNAME.DAT', 'CDTABLE.DAT', 'ICON.DAT', 'LICENSE.TXT', 'CONFIG.SYS'):
                ov = os.path.join(a.override, path) if a.override else None
                if ov and os.path.isfile(ov): w.add(path, ov); print('override', path, os.path.getsize(ov))   # new installer art/messages
                else: w.add(path, ('slice', os.path.abspath(a.adoulin), e['lba'] * S, e['size']))
            if path == 'CONFIG.SYS': w.add('CONFIGU.SYS', ('slice', os.path.abspath(a.adoulin), e['lba'] * S, e['size']))
    inst, nwords = patched_installer(a.adoulin, a.pnach)
    global MARKER
    MARKER = 'SYS/FFXI2016_%s.VER' % data_id[:8].upper()      # v3: the marker names this disc's data (cave.S MARKNAME, 32 bytes room)
    ph = b'SYS/FFXI2016.VER\0'; k = inst.find(ph)
    if k < 0 or inst.find(ph, k + 1) >= 0: die('marker name placeholder not found exactly once in the installer')
    inst = inst[:k] + MARKER.encode().ljust(33, b'\0') + inst[k + 33:]
    w.add('SYSTEM.CNF', b'BOOT2 = cdrom0:\\SLUS_217.04;1\r\nVER = 1.00\r\nVMODE = NTSC\r\nHDDUNITPOWER = NICHDD\r\n')
    w.add('SLUS_217.04', inst)
    w.add('POL/SCUSBOOT.ELF', host)
    for m_ in ('tcp005.erx', 'ndi002.erx'):
        p_ = os.path.join(tree, 'image/ffxi/prog/ps2/modules', m_)
        if os.path.exists(p_): w.add('MODULES/' + m_.upper(), p_)
    w.add('HDD.SYS', os.path.join(tree, P['hdd_sys']))
    w.add('DATA/PATCH.VER', os.path.join(tree, P['patch_ver']))
    w.add('DATA/FILE.TXT', b'FFXI 2016 install disc: no PlayOnline version data.\n')
    ms = misc_sets(P['misc'], tree); ms[9].append((MARKER, marker))
    summary = []
    for n in range(1, 10):
        codes = sorted(P['sets'][n]); stab = bytearray(4 * (codes[-1] + 1)); raw = 0
        for c in codes:
            sz = manifest[P['sets'][n][c]][0]; raw += sz; struct.pack_into('<I', stab, 4 * c, sz)
        parts = [os.path.join(lz, manifest[P['sets'][n][c]][1] + '.lz') for c in codes]
        d = 'DATA/%s/' % setname(n)
        w.add(d + '%s.DAT' % setname(n), ('parts', parts))
        w.add(d + 'STABLE%s.DAT' % sfx(n), bytes(stab))
        for t in ('FTABLE', 'VTABLE'): w.add(d + '%s%s.DAT' % (t, sfx(n)), os.path.join(tree, P['tables'][(n, t)]))
        recs = ms[n] or [('SYS/info00.bin', 'image/ffxi/SYS/info00.bin')]        # never an empty archive
        mp = os.path.join(a.work, 'MISC%s.DAT' % sfx(n)); msrc = build_misc(tree, recs, mp)
        w.add(d + 'MISC%s.DAT' % sfx(n), msrc)
        summary.append((setname(n), len(codes), raw, sum(os.path.getsize(p) for p in parts), sum(os.path.getsize(p) for p in msrc[1]), len(recs)))
    part = a.out + '.part'
    total = w.write(part, a.label)
    os.replace(part, a.out)
    print('set\tfiles\traw MB\tpacked MB\tMISC MB (records)')
    for s_, c, r_, p_, m_, k in summary: print('%s\t%d\t%.1f\t%.1f\t%.1f (%d)' % (s_, c, r_ / 1e6, p_ / 1e6, m_ / 1e6, k))
    size = total * S
    print('installer: %d patch words; host %s (md5 %s); marker data id %s' % (nwords, os.path.basename(a.host_elf), host_md5, data_id))
    print('ISO: %s  %d sectors = %d bytes = %.3f GiB (single-layer DVD 4,700,372,992 bytes = 4.378 GiB: %s, margin %.1f MB)  %.0f s'
          % (a.out, total, size, size / 2 ** 30, 'FITS' if size <= DVD5 else 'TOO BIG', (DVD5 - size) / 1e6, time.time() - t0))
    if a.verify:
        print('verifying the disc contents (decode every packed stream)...', flush=True)
        checked, bad = verify_iso(a.out, P, manifest, a.work)
        print('verify: %d items checked, %d bad' % (checked, bad))
        if bad: sys.exit(1)
    if size > DVD5: sys.exit(2)


if __name__ == '__main__':
    main()
