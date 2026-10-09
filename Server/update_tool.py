#!/usr/bin/env python3
"""update_tool.py: publish a game update that every PS2 gets the next time it signs in (Fan Project by Habex).

  python3 update_tool.py publish --host host2016.elf
  python3 update_tool.py publish --data "image/ffxi/pol/some/file.dat=/path/to/new_file.dat"
  python3 update_tool.py publish --host host2016.elf --data "A=file1" --data "B=file2"
  python3 update_tool.py status
  python3 update_tool.py clear

--host is the new game program (host2016.elf). The PS2 downloads it to its hard drive and starts it instead of the one on the disc.
--data TARGET=FILE puts FILE at TARGET on the PS2 hard drive (a path below pfs1:/image/ffxi/, no "..", e.g. "pol/ps2/data/x.dat").
Each publish raises the version number by one, so every PS2 that has an older one downloads what changed. The files are served by the
login proxy on the lobby port (the same port players already use), from Server/updates/.
"""
import argparse, os, re, shutil, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, 'updates')
FILES = os.path.join(ROOT, 'files')
MANIFEST = os.path.join(ROOT, 'manifest.txt')
TARGET_OK = re.compile(r'^[A-Za-z0-9._/-]{1,100}$')


def crc_of(path):
    c = 0
    with open(path, 'rb') as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                return c & 0xFFFFFFFF
            c = zlib.crc32(b, c)


def read_manifest():
    """(version, [lines]) of what is published now; (0, []) when nothing is."""
    try:
        lines = open(MANIFEST, encoding='utf-8').read().splitlines()
    except OSError:
        return 0, []
    ver = 0
    for l in lines:
        if l.startswith('version '):
            ver = int(l.split()[1])
    return ver, [l for l in lines if l[:2] in ('H ', 'D ')]


def put_file(src):
    c = crc_of(src)
    name = '%08x-%s' % (c, re.sub(r'[^A-Za-z0-9._-]', '_', os.path.basename(src))[:48])
    os.makedirs(FILES, exist_ok=True)
    dst = os.path.join(FILES, name)
    if not os.path.exists(dst):
        shutil.copyfile(src, dst + '.part')
        os.replace(dst + '.part', dst)
    return name, os.path.getsize(src), c


def publish(args):
    ver, items = read_manifest()
    items = [l for l in items if not (l.startswith('H ') and args.host)]
    new = []
    if args.host:
        if not os.path.isfile(args.host):
            sys.exit('The game program %s was not found.' % args.host)
        name, size, c = put_file(args.host)
        new.append('H %d %08x %s' % (size, c, name))
    for spec in args.data or []:
        target, _, src = spec.partition('=')
        target = target.strip().lstrip('/')
        if not src or not TARGET_OK.match(target) or '..' in target.split('/'):
            sys.exit('--data wants TARGET=FILE with a plain path below image/ffxi, got "%s".' % spec)
        if not os.path.isfile(src):
            sys.exit('%s was not found.' % src)
        items = [l for l in items if not (l.startswith('D ') and l.split(' ', 4)[4] == target)]
        name, size, c = put_file(src)
        new.append('D %d %08x %s %s' % (size, c, name, target))
    if not new:
        sys.exit('Nothing to publish. Use --host and/or --data.')
    items += new
    ver += 1
    text = 'FFXIUPD 1\nversion %d\n%s\n' % (ver, '\n'.join(items))
    os.makedirs(ROOT, exist_ok=True)
    with open(MANIFEST + '.part', 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    os.replace(MANIFEST + '.part', MANIFEST)
    used = {l.split(' ')[3] for l in items}
    for n in os.listdir(FILES):
        if n not in used:
            os.remove(os.path.join(FILES, n))
    print('Published update %d: %s' % (ver, ', '.join(l.split(' ')[0] + ':' + l.split(' ')[3] for l in new)))


def status(args):
    ver, items = read_manifest()
    if not items:
        print('No update is published.')
        return
    print('Update %d is published (%d file%s):' % (ver, len(items), '' if len(items) == 1 else 's'))
    for l in items:
        print('  ' + l)


def clear(args):
    for p in (MANIFEST,):
        if os.path.exists(p):
            os.remove(p)
    shutil.rmtree(FILES, ignore_errors=True)
    print('The published update was removed. PS2s that already have it keep it.')


def main():
    ap = argparse.ArgumentParser(description='Publish a game update to the PS2s.')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('publish')
    p.add_argument('--host', help='the new game program (host2016.elf)')
    p.add_argument('--data', action='append', metavar='TARGET=FILE', help='a data file and where it goes on the PS2 hard drive')
    p.set_defaults(fn=publish)
    sub.add_parser('status').set_defaults(fn=status)
    sub.add_parser('clear').set_defaults(fn=clear)
    a = ap.parse_args()
    a.fn(a)


if __name__ == '__main__':
    main()
