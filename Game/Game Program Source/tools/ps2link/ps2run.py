"""Start a test build on the PS2 over the network (stands in for ps2client's "execee").

The PS2 must be showing the PS2LINK screen. This script connects to it, asks it to run
host:<file>, and serves that one file (read only) from the folder given with --dir while the
PS2 loads it. ps2link then shuts itself down and starts the build exactly as a USB launcher would.

  python ps2run.py --ps2 192.168.1.11 --dir <folder with the builds> NETDIAG40.ELF
"""
import argparse
import os
import socket
import struct
import sys
import threading
import time

REQ_PORT = 0x4711      # TCP, the PS2 serves host: requests over it
CMD_PORT = 0x4712      # UDP, commands to the PS2 / its console text back to us

CMD_EXECEE = 0xBABE0203
REQ = {0xBABE0111: "open", 0xBABE0121: "close", 0xBABE0131: "read", 0xBABE0141: "write",
       0xBABE0151: "lseek", 0xBABE0161: "opendir", 0xBABE0171: "closedir", 0xBABE0181: "readdir",
       0xBABE0191: "remove", 0xBABE01A1: "mkdir", 0xBABE01B1: "rmdir", 0xBABE01C1: "getstat"}


def log(msg):
    print(time.strftime("%H:%M:%S ") + msg, flush=True)


def recv_all(s, n):
    b = b""
    while len(b) < n:
        c = s.recv(n - len(b))
        if not c:
            raise ConnectionError("the PS2 closed the connection")
        b += c
    return b


def console(sock, stop):
    sock.settimeout(0.5)
    while not stop.is_set():
        try:
            data, _ = sock.recvfrom(4096)
        except socket.timeout:
            continue
        except OSError:
            return
        txt = data.decode("latin-1", "replace").rstrip()
        if txt:
            for line in txt.splitlines():
                log("PS2: " + line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ps2", default="192.168.1.11")
    ap.add_argument("--dir", required=True)
    ap.add_argument("file")
    a = ap.parse_args()

    root = os.path.realpath(a.dir)
    want = os.path.basename(a.file)
    if not os.path.isfile(os.path.join(root, want)):
        log("not found: " + os.path.join(root, want))
        return 2

    stop = threading.Event()
    csock = None
    try:
        csock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        csock.bind(("", CMD_PORT))
        threading.Thread(target=console, args=(csock, stop), daemon=True).start()
    except OSError:
        csock = None   # console text is optional

    log("connecting to the PS2 (%s) ..." % a.ps2)
    try:
        r = socket.create_connection((a.ps2, REQ_PORT), timeout=5)
    except OSError as e:
        log("could not reach ps2link on the PS2 (%s). Is the PS2 on the PS2LINK screen?" % e)
        return 1
    r.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    r.settimeout(60)

    arg = ("host:" + want).encode() + b"\0"
    pkt = struct.pack(">IHi", CMD_EXECEE, 266, 1) + arg.ljust(256, b"\0")
    u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    u.sendto(pkt, (a.ps2, CMD_PORT))
    log("asked the PS2 to run host:%s" % want)

    files = {}
    nextfd = 3
    served = 0
    t0 = time.time()
    try:
        while True:
            hdr = recv_all(r, 6)
            num, length = struct.unpack(">IH", hdr)
            body = recv_all(r, length - 6) if length > 6 else b""
            kind = REQ.get(num, hex(num))
            if kind == "open":
                flags = struct.unpack(">i", body[:4])[0]
                path = body[4:].split(b"\0", 1)[0].decode("latin-1").replace("\\", "/").lstrip("/")
                name = os.path.basename(path)
                full = os.path.realpath(os.path.join(root, name))
                res = -1
                readonly = (flags & 3) in (0, 1) and not (flags & 0x0700)   # PS2 flags: 1 = read only; 0x100/0x200/0x400 = append/create/truncate
                if readonly and name == want and os.path.dirname(full) == root and os.path.isfile(full):
                    res = nextfd
                    nextfd += 1
                    files[res] = open(full, "rb")
                log("open %s -> %d" % (path, res))
                r.sendall(struct.pack(">IHi", 0xBABE0112, 10, res))
            elif kind == "close":
                fd = struct.unpack(">i", body[:4])[0]
                f = files.pop(fd, None)
                if f:
                    f.close()
                r.sendall(struct.pack(">IHi", 0xBABE0122, 10, 0 if f else -1))
            elif kind == "read":
                fd, size = struct.unpack(">ii", body[:8])
                f = files.get(fd)
                data = f.read(size) if f else b""
                res = len(data) if f else -1
                r.sendall(struct.pack(">IHii", 0xBABE0132, 14, res, len(data)) + data)
                served += len(data)
            elif kind == "lseek":
                fd, off, whence = struct.unpack(">iii", body[:12])
                f = files.get(fd)
                res = -1
                if f:
                    f.seek(off, whence)
                    res = f.tell()
                r.sendall(struct.pack(">IHi", 0xBABE0152, 10, res))
            elif kind == "getstat":
                # not needed to load an ELF: answer "no such file" (reply is 50 bytes)
                r.sendall(struct.pack(">IHi", 0xBABE01C2, 50, -1) + b"\0" * 40)
                log("getstat refused")
            else:
                # write, directories, remove...: refused (read-only)
                rnum = num + 1
                r.sendall(struct.pack(">IHi", rnum, 10, -1))
                log("%s refused" % kind)
    except (ConnectionError, OSError) as e:
        if served:
            log("sent %d bytes in %.1f s; the PS2 has started the build (%s)" % (served, time.time() - t0, e))
        else:
            log("connection ended before anything was sent: %s" % e)
    finally:
        stop.set()
        r.close()
        if csock:
            csock.close()
    return 0 if served else 1


if __name__ == "__main__":
    sys.exit(main())
