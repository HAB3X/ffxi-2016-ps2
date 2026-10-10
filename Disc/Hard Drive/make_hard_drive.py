#!/usr/bin/env python3
"""make_hard_drive.py: makes a ready to use PS2 hard drive for PCSX2 (FFXI 2016, Fan Project by Habex).

The installer needs a FORMATTED PS2 hard drive. The "Create" button in PCSX2 makes an empty, unformatted one,
and the installer then says a hard drive is needed. This makes a 40 GB drive that is already formatted.
Plain Python 3, works on Windows, Mac and Linux.

  python3 make_hard_drive.py "FFXI 2016 HDD.raw"

As a module:  make_hard_drive.make(path)

On a Mac or Linux the file only takes a few MB of real space at first and grows as the game installs.
On Windows the file is made sparse (on an NTFS drive) so it is ready in a moment; on other Windows drives it is written out in
full, which can take a few minutes.
"""
import base64, os, sys, zlib

SIZE = 42949672960
TABLE = '0:200;1000:200;1400:200;1800:200;1c00:200;8000000:200;8400000:400;8402000:200;8404000:200;8424000:400;8426000:200;10000000:200;10400000:400;10402000:200;10404000:200;10424000:400;10426000:200;20000000:200;20400000:400;20402000:200;20404000:200;20424000:400;20426000:200;40000000:200;40400000:400;40402000:200;40406000:200;40426000:400;40428000:200'
DATA = """
eNrtmzFLw0AUgC9Ji0WKprbgpGZyzCSIY9EqgkOhg+AS0hLRIYm0cSgdXQRn9w76Exz9B67+CeeuWkOu1VoaiDjYNN8Hr5cr5SDv
9d31K61Web2t1qtCiFwYhrAst9kW8dw923Zvb/g4HuWzOaGMX7BbXMkvvy2JlNDwva6x77tX14HTNmpe+BjYl57reIFx7LVMNaX3
lZQTWXzIKDenzQ/5FjDCKIT93+l2Wr53nngFXYYyu0/yKjmeZ9bts8H3FqCH9W/5rut7yVcwZFD/VKJx/mf6/N8cPPVk/QvR3LI8
J/jVCjkZ9H86aRzWtXBQ1Ynt/Guui7VoVMgT9YcFZPhnVklimv0/7H+ykF362y/3B0e1xvQ+Hzcvcx4A/P+5Xer/9K3pcfR5Th1F
XMdGfa0UdXN8rQ5Kpkl+s8LGxc679H898vjo+9/AcZOvUJCB/+N/QP0B/wf8H/B/AMD/YW7h91/4H/5H/ak//o//4/+A/+P/APg/
LD78/wf/m+V/2sj/OO+pP/XH/+PZIon4P6SUh5H/T+/zcfMK5wHAwvh/ecL/y/h/5vgE86upGg==
"""


def _sparse(f):
    """Windows only: mark the file sparse so making it 40 GB long does not write 40 GB of zeros. Ignored where it is not supported."""
    if os.name != 'nt':
        return
    try:
        import ctypes, msvcrt
        from ctypes import wintypes
        done = wintypes.DWORD()
        ctypes.windll.kernel32.DeviceIoControl(wintypes.HANDLE(msvcrt.get_osfhandle(f.fileno())), 0x900C4, None, 0, None, 0,
                                               ctypes.byref(done), None)
    except Exception:
        pass


def make(path):
    """Write a new formatted 40 GB PS2 drive to `path`. Never overwrites an existing file."""
    if os.path.exists(path):
        raise ValueError('There is already a file called %s. Pick a new name, or move the old one away first.' % os.path.basename(path))
    data = zlib.decompress(base64.b64decode(''.join(DATA.split())))
    with open(path + '.part', 'wb') as f:
        _sparse(f)
        f.truncate(SIZE)
        pos = 0
        for item in TABLE.split(';'):
            off, n = (int(x, 16) for x in item.split(':'))
            f.seek(off)
            f.write(data[pos:pos + n])
            pos += n
    os.replace(path + '.part', path)
    return path


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    try:
        print('Made your PS2 hard drive:', make(sys.argv[1]))
    except (ValueError, OSError) as e:
        print('Problem:', e)
        sys.exit(1)
