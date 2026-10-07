#!/usr/bin/env python3
"""patch_iso.py: the FFXI 2016 disc patcher (Fan Project by Habex).

Turns the original disc image into the patched install disc. Works on Windows, Mac and Linux with plain Python 3
(nothing else to install).

  Patch a disc:   python3 patch_iso.py ORIGINAL.iso PATCHFILE.ffxipatch PATCHED.iso
  Make a patch:   python3 patch_iso.py --make ORIGINAL.iso PATCHED.iso PATCHFILE.ffxipatch

As a module:      patch_iso.apply(original, patchfile, out, progress=callback(fraction, text))

A patch can also come in parts (NAME.ffxipatch.001, NAME.ffxipatch.002 ...). Keep all the parts in the same folder and
give the name of the first part, or the name without the number: the parts are read as one file.

The patch only stores what is new. Everything that is already on the original disc is copied from it, sector by sector,
so the patch is useless without the original disc. Both the original and the finished disc are checked (MD5), so a
wrong or damaged disc image is caught instead of producing a broken disc.

File format: b'FFXIPATCH1\\n', u32 header length, JSON header, then records:
  b'C' + u32 first original sector + u32 count            copy sectors from the original disc
  b'D' + u32 count + u32 compressed length + zlib data     new sectors
  b'E'                                                     end
"""
import hashlib, json, os, struct, sys, zlib

SECTOR = 2048
MAGIC = b'FFXIPATCH1\n'


class _Parts:
    """Read-only file over NAME.001, NAME.002 ... as if they were one file."""
    def __init__(self, paths):
        self.f = [open(p, 'rb') for p in paths]; self.size = [os.path.getsize(p) for p in paths]; self.pos = 0
    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else sum(self.size) + off
        return self.pos
    def tell(self):
        return self.pos
    def read(self, n=-1):
        out = []; base = 0
        if n < 0: n = sum(self.size) - self.pos
        for f, sz in zip(self.f, self.size):
            if n <= 0: break
            if self.pos < base + sz:
                f.seek(self.pos - base); b = f.read(min(n, base + sz - self.pos)); out.append(b); self.pos += len(b); n -= len(b)
            base += sz
        return b''.join(out)
    def close(self):
        for f in self.f: f.close()
    def __enter__(self): return self
    def __exit__(self, *a): self.close()


def _patch_parts(patchfile):
    """The list of files that make up the patch: the file itself, or NAME.001, NAME.002 ... (no gaps)."""
    base = patchfile[:-4] if patchfile[-4:-3] == '.' and patchfile[-3:].isdigit() else patchfile
    if os.path.exists(base) and base == patchfile:
        return [base]
    parts, i = [], 1
    while os.path.exists('%s.%03d' % (base, i)):
        parts.append('%s.%03d' % (base, i)); i += 1
    if not parts:
        raise ValueError('The patch file was not found. Put it (all of its parts) in the Disc/Patch folder.')
    return parts


def _open_patch(patchfile):
    parts = _patch_parts(patchfile)
    return open(parts[0], 'rb') if len(parts) == 1 else _Parts(parts)


def _md5(path, progress=None, label='Checking'):
    h = hashlib.md5(); size = os.path.getsize(path); done = 0
    with open(path, 'rb') as f:
        while True:
            b = f.read(8 << 20)
            if not b: break
            h.update(b); done += len(b)
            if progress: progress(done / max(size, 1), label)
    return h.hexdigest()


def make(original, patched, patchfile, progress=None):
    """Write a patch that turns `original` into `patched`."""
    say = progress or (lambda f, t: None)
    osize, psize = os.path.getsize(original), os.path.getsize(patched)
    index = {}
    with open(original, 'rb') as f:
        n = (osize + SECTOR - 1) // SECTOR
        for i in range(n):
            s = f.read(SECTOR).ljust(SECTOR, b'\0')
            index.setdefault(hashlib.sha1(s).digest(), i)
            if i % 4096 == 0: say(i / n * 0.3, 'Reading the original disc')
    header = {'original_size': osize, 'original_md5': _md5(original), 'patched_size': psize,
              'patched_md5': _md5(patched), 'sector': SECTOR, 'note': 'FFXI 2016 install disc. Fan Project by Habex'}
    hb = json.dumps(header).encode()
    copied = new = 0
    with open(patched, 'rb') as f, open(patchfile + '.part', 'wb') as out:
        out.write(MAGIC + struct.pack('<I', len(hb)) + hb)
        n = (psize + SECTOR - 1) // SECTOR
        run_src = run_len = 0; lit = []
        def flush_copy():
            nonlocal run_len
            if run_len: out.write(b'C' + struct.pack('<II', run_src, run_len)); run_len = 0
        def flush_lit():
            if lit:
                z = zlib.compress(b''.join(lit), 6)
                out.write(b'D' + struct.pack('<II', len(lit), len(z)) + z); lit.clear()
        for i in range(n):
            s = f.read(SECTOR)
            full = s.ljust(SECTOR, b'\0')
            j = index.get(hashlib.sha1(full).digest())
            if j is not None and len(s) == SECTOR:
                flush_lit()
                if run_len and j == run_src + run_len: run_len += 1
                else: flush_copy(); run_src, run_len = j, 1
                copied += 1
            else:
                flush_copy(); lit.append(full); new += 1
                if len(lit) >= 2048: flush_lit()
            if i % 4096 == 0: say(0.3 + i / n * 0.7, 'Writing the patch')
        flush_copy(); flush_lit(); out.write(b'E')
    os.replace(patchfile + '.part', patchfile)
    return {'copied_sectors': copied, 'new_sectors': new, 'patch_bytes': os.path.getsize(patchfile)}


def read_header(patchfile):
    with _open_patch(patchfile) as f:
        if f.read(len(MAGIC)) != MAGIC: raise ValueError('This is not an FFXI patch file.')
        n = struct.unpack('<I', f.read(4))[0]
        return json.loads(f.read(n))


def apply(original, patchfile, out, progress=None):
    """Build the patched disc `out` from `original` + `patchfile`. Raises ValueError with a plain message on any problem."""
    say = progress or (lambda f, t: None)
    hdr = read_header(patchfile)
    if os.path.getsize(original) != hdr['original_size']:
        raise ValueError('That is not the right disc image (wrong size). Pick the original disc image (.iso) named in the read me.')
    if _md5(original, lambda f, t: say(f * 0.25, 'Checking your disc')) != hdr['original_md5']:
        raise ValueError('That disc image does not match the original disc (it may be damaged or a different version).')
    total = hdr['patched_size']; written = 0
    with _open_patch(patchfile) as p, open(original, 'rb') as src, open(out + '.part', 'wb') as dst:
        p.seek(len(MAGIC)); p.seek(struct.unpack('<I', p.read(4))[0], 1)
        while True:
            op = p.read(1)
            if op == b'E': break
            if op == b'C':
                first, count = struct.unpack('<II', p.read(8)); src.seek(first * SECTOR)
                left = count * SECTOR
                while left:
                    b = src.read(min(left, 8 << 20)); dst.write(b); left -= len(b); written += len(b)
            elif op == b'D':
                count, zlen = struct.unpack('<II', p.read(8))
                b = zlib.decompress(p.read(zlen)); dst.write(b); written += len(b)
            else:
                raise ValueError('The patch file is damaged. Copy it again from the release folder.')
            say(0.25 + 0.6 * written / max(total, 1), 'Building your patched disc')
        dst.truncate(total)
    if _md5(out + '.part', lambda f, t: say(0.85 + f * 0.15, 'Checking the patched disc')) != hdr['patched_md5']:
        os.replace(out + '.part', out + '.bad')
        raise ValueError('The patched disc did not come out right. Try again; if it keeps failing, copy the release folder again.')
    os.replace(out + '.part', out)
    say(1.0, 'Done')
    return out


def _bar(f, text, _last=[-1]):
    pct = int(f * 100)
    if pct != _last[0]:
        _last[0] = pct
        sys.stdout.write('\r%-30s %3d%%' % (text, pct)); sys.stdout.flush()


if __name__ == '__main__':
    a = sys.argv[1:]
    try:
        if len(a) == 4 and a[0] == '--make':
            r = make(a[1], a[2], a[3], _bar); print('\npatch written:', a[3], r)
        elif len(a) == 3:
            apply(a[0], a[1], a[2], _bar); print('\nDone. Your patched disc is:', a[2])
        else:
            print(__doc__); sys.exit(2)
    except ValueError as e:
        print('\nProblem:', e); sys.exit(1)
