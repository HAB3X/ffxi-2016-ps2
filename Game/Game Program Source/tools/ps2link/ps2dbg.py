#!/usr/bin/env python3
"""ps2dbg.py - console for the live debug link of the NETDIAG test builds (host/dbg.c).

The PS2 connects to this PC (TCP port 54100 by default) once its network is up, and reconnects if the link drops,
so this can be started before or after the game.  Everything it receives is written to the log file with a time stamp;
the newest status line is also kept in status.txt.

Commands are typed here, or appended (one per line) to the command file, which lets another program drive it:
  ping                    the PS2 answers with its vblank count
  rate MS / stream 0|1    status line interval (default 200 ms) / status lines off or on
  peek ADDR [LEN]         memory dump (main RAM, scratchpad, kernel via 0x8xxxxxxx, EE / GS registers)
  poke ADDR VALUE [1|2|4] write main RAM
  thr / sema              all threads / semaphores
  report / beat / log     a full report, a short report, the last host log lines
  watch ADDR [r|w|rw] [MASK] [COUNT]   hardware data watchpoint (run 'wtest' once first)
  iwatch ADDR [MASK] [COUNT]           hardware instruction breakpoint
  unwatch / wtest         clear the watchpoint / check that watchpoints work on this console
  prof 0|1 / ap N ADDR    allocator profiler on/off / profiler slot N (0-4) times the jal at ADDR ('ap N 0' frees it)
  patch ADDR NEW [OLD]    write one word of code, remembering the original; with OLD only if the word holds OLD now
  unpatch ADDR [force]    put the original back (only if it still holds what patch wrote, unless force)
  unpatch all / patches   undo every patch and free the profiler slots / list them
  hist 0|1                the once-a-second frame-time line (F) off / on
  samp 1 [RATE] / samp 0  sampling profiler on (RATE samples a second of game CPU time, default 1000) / off; real PS2 only
  samp top [N] / samp clear  the N busiest functions since 'samp 1' (P top lines) / start counting again
  gsw 1 / gsw 0           graphics wait meter on (G line once a second: SyncV and SyncPath share of the time) / off
  gsw top / gsw clear     where the game waits for the graphics hardware, per call site (G site, G bits lines) / start again
  gsw nov 1 / gsw nov 0   sceGsSyncV returns at once (no vertical-blank wait, the picture may tear) / normal
  crash                   a crash report now (the PS2 also sends one by itself when the game stops: crash-HHMMSS.txt here)
  reboot                  back to PS2LINK without touching the console (this sends it PS2LINK.ELF, see --ps2link)
Local commands: sym NAME (address of a host symbol), where ADDR (nearest host symbol), help, quit.
ADDR and VALUE can be numbers (0x.. hex) or host symbol names from the .sym file (name or name+offset).
"""
import argparse, os, re, socket, struct, sys, threading, time

KEYWORDS = ('r', 'w', 'rw', 'all', 'force', 'top', 'clear', 'nov')                # command words that are not symbol names

def load_syms(path):
    syms, code = {}, {}
    if path and os.path.exists(path):
        for line in open(path, encoding='ascii', errors='replace'):
            p = line.split()
            if len(p) >= 3 and re.fullmatch(r'[0-9a-fA-F]{8}', p[0]):
                syms.setdefault(p[-1], int(p[0], 16))
                if p[1] in 'TtWw': code.setdefault(p[-1], int(p[0], 16))
    return syms, code

class Console:
    def __init__(self, a):
        self.a = a
        self.syms, code = load_syms(a.sym)
        self.by_addr = sorted((v, k) for k, v in code.items() if 0x100000 <= v < 0x2000000)   # code symbols, for epc / ra
        os.makedirs(a.dir, exist_ok=True)
        self.logf = open(os.path.join(a.dir, 'ps2dbg.log'), 'a', encoding='utf-8', buffering=1)
        self.statusp = os.path.join(a.dir, 'status.txt')
        self.cmdp = os.path.join(a.dir, 'cmd.txt')
        self.conn = None
        self.lock = threading.Lock(); self.slock = threading.Lock()
        self.last_s = 0.0; self.last_s_line = ''; self.last_shown = 0.0; self.warned = 0.0
        self.running = True
        self.crashf = None                                  # crash report being written (C begin .. C end)

    def log(self, kind, text, show=True):
        t = time.strftime('%H:%M:%S') + ('%.3f' % (time.time() % 1))[1:]
        self.logf.write('%s %s %s\n' % (t, kind, text))
        if show:
            print('%s %s' % (t[:8], text), flush=True)

    def where(self, v):
        import bisect
        i = bisect.bisect_right(self.by_addr, (v, '￿')) - 1
        if i < 0 or 0x1D6000 <= v < 0x251000: return None          # the lifted kernel has no symbols
        a, n = self.by_addr[i]
        return '%s+0x%x' % (n, v - a) if v - a < 0x4000 else None

    def annotate(self, line):
        def rep(m):
            v = int(m.group(2), 16); w = self.where(v) if 0x100000 <= v < 0x280000 else None
            return m.group(0) + (' <%s>' % w if w else '')
        return re.sub(r'\b(epc|ra|func) ([0-9a-f]{8})\b', rep, line)

    def resolve(self, cmd):
        parts = cmd.split()
        out = parts[:1]
        for p in parts[1:]:
            m = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_.]*)(?:\+(0x[0-9a-fA-F]+|\d+))?', p)
            if m and p in KEYWORDS:
                pass
            elif m and m.group(1) in self.syms:
                v = self.syms[m.group(1)] + (int(m.group(2), 0) if m.group(2) else 0)
                p = '0x%08x' % v
            elif m:
                raise ValueError('unknown symbol %s' % m.group(1))
            out.append(p)
        return ' '.join(out)

    def command(self, cmd, src='you'):
        cmd = cmd.strip()
        if not cmd: return
        w = cmd.split()
        if w[0] == 'quit': self.running = False; return
        if w[0] == 'help': print(__doc__); return
        if w[0] == 'sym':
            for n in w[1:]: print('%s = %s' % (n, '0x%08x' % self.syms[n] if n in self.syms else 'unknown'))
            return
        if w[0] == 'where':
            for n in w[1:]:
                try: print('%s = %s' % (n, self.where(int(n, 16)) or '?'))
                except ValueError: print('where: hex address please')
            return
        try: line = self.resolve(cmd)
        except ValueError as e: print('!! %s' % e); return
        self.log('CMD', '%s (%s)' % (line, src), show=(src != 'you'))
        with self.lock:
            c = self.conn
        if not c: print('!! the PS2 is not connected'); return
        try:
            with self.slock: c.sendall((line + '\n').encode())
        except OSError as e: print('!! send failed: %s' % e)

    def stdin_loop(self):
        while self.running:
            try: s = input()
            except EOFError: return
            self.command(s)

    def file_loop(self):
        pos = os.path.getsize(self.cmdp) if os.path.exists(self.cmdp) else 0
        while self.running:
            time.sleep(0.3)
            try:
                if not os.path.exists(self.cmdp): continue
                n = os.path.getsize(self.cmdp)
                if n < pos: pos = 0
                if n == pos: continue
                with open(self.cmdp, 'r', encoding='utf-8', errors='replace') as f:
                    f.seek(pos); data = f.read(); pos = f.tell()
                for l in data.splitlines(): self.command(l, 'file')
            except OSError: pass

    def watch_loop(self):
        while self.running:
            time.sleep(0.5)
            now = time.time()
            with self.lock: up = self.conn is not None
            if up and self.last_s and now - self.last_s > 2 and now - self.warned > 10:
                self.warned = now
                self.log('!!', 'no status from the PS2 for %d s - last: %s' % (now - self.last_s, self.last_s_line))
            if up:
                with self.lock: c = self.conn
                try:
                    with self.slock: c.sendall(b'\n')         # keepalive (the PS2 drops the link after 10 s without one)
                except OSError: pass

    def handle(self, c, addr):
        self.log('--', 'PS2 connected from %s:%d' % addr)
        buf = b''
        c.settimeout(1.0)
        while self.running:
            try: d = c.recv(65536)
            except socket.timeout: continue
            except OSError as e: self.log('--', 'link error: %s' % e); break
            if not d: self.log('--', 'PS2 closed the link'); break
            buf += d
            while b'\n' in buf:
                l, buf = buf.split(b'\n', 1)
                line = l.decode('latin-1').rstrip('\r')
                self.crash_line(line)
                if line == 'R getelf':
                    self.send_elf(c); continue
                if line.startswith('R getchunk '):
                    self.send_chunk(c, line); continue
                if line.startswith('S '):
                    self.last_s = time.time(); self.last_s_line = line; self.warned = 0
                    try:
                        with open(self.statusp, 'w') as f: f.write(time.strftime('%H:%M:%S ') + line + '\n')
                    except OSError: pass
                    show = self.a.all or time.time() - self.last_shown >= self.a.every
                    if show: self.last_shown = time.time()
                    self.log('S', line[2:], show=show)
                else:
                    line = self.annotate(line)
                    self.log(line[:1], line, show=line.startswith(('P top', 'G site', 'G bits')) or not line.startswith(('P ', 'F ', 'A ', 'G ')))   # once-a-second data lines: log file only
        with self.lock:
            if self.conn is c: self.conn = None
        try: c.close()
        except OSError: pass

    def crash_line(self, line):
        if line.startswith('C begin'):
            path = os.path.join(self.a.dir, time.strftime('crash-%H%M%S.txt'))
            self.crashf = open(path, 'w', encoding='utf-8')
            self.log('C', 'crash report from the PS2 -> %s' % path)
        if self.crashf and not line.startswith('S ') and not re.match(r'T \d+ st 0 prio 0 .*func 00000000', line):
            self.crashf.write(time.strftime('%H:%M:%S ') + self.annotate(line) + '\n')
            if line.startswith('C end'):
                self.crashf.close(); self.crashf = None

    def send_elf(self, c):
        """'reboot': the PS2 asks for PS2LINK.ELF; it gets 'ELF vaddr filesz memsz entry' and the program segment."""
        try:
            d = open(self.a.ps2link, 'rb').read()
            if d[:4] != b'\x7fELF': raise ValueError('not an ELF file')
            entry, phoff = struct.unpack_from('<II', d, 24); phnum = struct.unpack_from('<H', d, 44)[0]
            for i in range(phnum):
                t, off, va, pa, fs, ms = struct.unpack_from('<IIIIII', d, phoff + 32 * i)
                if t == 1: break
            else: raise ValueError('no program segment')
            self.seg = d[off:off + fs]
            with self.slock: c.sendall(b'ELF %x %x %x %x\n' % (va, fs, ms, entry))
            self.log('--', 'sending %s to the PS2 (%d bytes at %08x, entry %08x)' % (self.a.ps2link, fs, va, entry))
        except (OSError, ValueError, struct.error) as e:
            self.log('!!', 'reboot: cannot send %s: %s' % (self.a.ps2link, e))
            with self.slock: c.sendall(b'ERR %s\n' % str(e).encode()[:60])

    def send_chunk(self, c, line):
        try:
            o, n = (int(x, 16) for x in line.split()[2:4])
            data = self.seg[o:o + n]
            if len(data) != n: raise ValueError('outside the segment')
            with self.slock: c.sendall(data)
            if o + n >= len(self.seg): self.log('--', 'PS2LINK.ELF sent (%d bytes)' % len(self.seg))
        except (AttributeError, ValueError) as e:
            self.log('!!', 'reboot: bad chunk request %s: %s' % (line, e))

    def run(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(('0.0.0.0', self.a.port)); srv.listen(2); srv.settimeout(1.0)
        self.log('--', 'ps2dbg listening on port %d, %d host symbols, log %s, command file %s'
                 % (self.a.port, len(self.syms), self.logf.name, self.cmdp))
        for f in (self.stdin_loop, self.file_loop, self.watch_loop):
            threading.Thread(target=f, daemon=True).start()
        while self.running:
            try: c, addr = srv.accept()
            except socket.timeout: continue
            c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            with self.lock:
                old, self.conn = self.conn, c
            if old:
                try: old.close()
                except OSError: pass
            threading.Thread(target=self.handle, args=(c, addr), daemon=True).start()

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description='console for the NETDIAG debug link')
    ap.add_argument('--port', type=int, default=54100)
    ap.add_argument('--sym', help='symbol file (nm output) of the build')
    ap.add_argument('--dir', default=os.path.join(here, 'ps2dbg'), help='where the log, status.txt and cmd.txt go')
    ap.add_argument('--every', type=float, default=5.0, help='show a status line on screen every N seconds (all are logged)')
    ap.add_argument('--all', action='store_true', help='show every status line')
    ap.add_argument('--ps2link', default=os.path.join(here, '..', '..', 'outputs', 'USB', 'PS2LINK', 'PS2LINK.ELF'),
                    help="PS2LINK.ELF for 'reboot' (default: outputs\\USB\\PS2LINK\\PS2LINK.ELF)")
    a = ap.parse_args()
    try: Console(a).run()
    except KeyboardInterrupt: pass

if __name__ == '__main__':
    main()
