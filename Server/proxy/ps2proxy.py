#!/usr/bin/env python3
"""ps2proxy - lets the patched PS2 FFXI client log into a LandSandBoat (LSB) server.

The PS2 client (Vana'diel Collection / WotG INSTALL.ELF in game mode, command line
"-net 3 -ip <proxy> -port 54001 -accunt <account> -pass <password>", no -POLCON, key patch P4) talks only
to one lobby TCP address and then to the zone (UDP) address the lobby hands it. LSB needs more than that
:

  * a TLS 1.3 JSON login on the auth port (54231) that creates a session [client IP][16-byte session hash];
  * a plaintext "data" channel (54230) that stays open and answers 0x01 -> 0xA1 and 0x02 -> 0xA2;
  * every lobby (view) packet from the client must carry the session hash in bytes 12..27
    (the PS2 client writes the packet's own MD5 there);
  * the zone server only accepts UDP from the IP that did the lobby login (accounts_sessions.client_addr).

This proxy does all of it. Per PS2 lobby connection:

  1. read the PS2's 0x26 (RequestLobbyLogin), take the account name from it, look the password up in the
     players file, log into LSB over TLS (account_id + session hash);
  2. open the data channel, send 0xFE+hash, answer 0x01 with 0xA1 and 0x02 with 0xA2
     (0xA2 key = password zero-padded to 16 bytes + le32(K0 + 9), the patched client's world key);
  3. relay lobby packets both ways, writing the session hash into bytes 12..27 of every PS2 packet;
  4. rewrite the zone address in 0x0B (ResponseNextLogin) to the proxy's UDP relay and fix the MD5;
  5. relay the zone UDP traffic. The relay knows the Blowfish key (it knows the password and the lobby key),
     so it decrypts every frame for the trace, rewrites s2c 0x00B (zone change) addresses so the PS2 stays
     on the relay, and offers per-packet translation hooks (C2S_HOOKS / S2C_HOOKS) for PS2 layout fixes.

All three LSB login connections (auth, data, view) and the zone UDP come from this proxy's host, so LSB
sees one consistent client IP.

Python 3.8+, standard library only (ssl for TLS). Run with --help for options.
"""

import argparse
import datetime
import hashlib
import json
import os
import selectors
import signal
import socket
import ssl
import struct
import sys
import threading
import time
import traceback
import ipaddress

VERSION = '1.0'

DEFAULT_LSB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lsb')   # release: Server/lsb
DEFAULT_PLAYERS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'players.txt')   # release: Server/data

IXFF = b'IXFF'
LSB_K0 = 0xAD5DE04F                      # LSB ResponseKey constant (view_session.cpp)
MAX_CHARS = 16                           # PS2 lpkt_work holds 16 x 0x8C character records (0x148..0xA08)
FFXI_HEADER = 0x1C                       # zone UDP frame header size
ZONE_MAX_FRAME = 0x578                   # PS2 enAcvGet rejects frames larger than this

LOBBY_NAMES = {
    0x26: 'RequestLobbyLogin', 0x1F: 'RequestGetChr', 0x24: 'RequestQueryWorldList', 0x07: 'RequestSelectChr',
    0x22: 'RequestCreateChrPre', 0x21: 'RequestCreateChr', 0x14: 'RequestDeleteChr', 0x28: 'RequestRenameChr',
    0x2B: 'RequestGMMove',
    0x05: 'ResponseKey', 0x20: 'ResponseChrInfo2', 0x23: 'ResponseWorldList', 0x03: 'ResponseOk',
    0x04: 'ResponseError', 0x0B: 'ResponseNextLogin',
}
# Offset of the 16-byte digest MD5(passwd || le32(key)) in PS2 client lobby packets (LobbyPktCreate).
EXCODE_2012 = int(os.environ.get('PS2PROXY_EXCODE_2012', '0x07FF'), 0)   # 0x0FFF only with a pnach made with --soa-installed; expansion bits for the 2012 client = what it can mark installed:
                          # base, RoZ, CoP, ToAU, WotG (ROM2-5), ACP, AMK, ASA (ROM6-8), the 3 Abyssea (auto with RoZ+WotG).
                          # NOT 0x800 Seekers of Adoulin: only a "ROM12" set marks it installed, which the 2012 program never
                          # probes -> with 0x0FFF the client said "Expansion pack data has not been installed" (30 Sep).
LOBBY_DIGEST_AT = {0x1F: 0x1C, 0x24: 0x1C, 0x07: 0x34, 0x28: 0x34, 0x2B: 0x34, 0x22: 0x30, 0x21: 0x20, 0x14: 0x24}
LOBBY_ERRORS = {
    305: 'Unable to connect to the world server', 313: 'Character name unavailable',
    201: 'Same character already logged in', 208: 'World server congested', 314: 'Failed to register with the name server',
    321: "Character's parameters are incorrect", 331: "The game's data has been updated",
    332: 'Could not connect to lobby server',
}
ERR_LOBBY = 332

ZONE_S2C_NAMES = {0x008: 'ZoneIn?', 0x00A: 'LOGIN', 0x00B: 'LOGOUT/ZONE', 0x00D: 'CHAR_PC', 0x00E: 'CHAR_NPC',
                  0x017: 'CHAT', 0x01B: 'JOB_INFO', 0x01C: 'ITEM_MAX', 0x01F: 'ITEM_LIST', 0x020: 'ITEM_ATTR',
                  0x037: 'SERVERSTATUS', 0x051: 'GRAP_LIST', 0x061: 'CLISTATUS', 0x063: 'MISCDATA',
                  0x0AA: 'MAGIC_DATA', 0x0AC: 'COMMAND_DATA', 0x0B4: 'CONFIG'}
ZONE_C2S_NAMES = {0x00A: 'LOGIN', 0x00C: 'GAMEOK', 0x00D: 'NETEND', 0x00F: 'CLSTAT', 0x011: 'ZONE_TRANSITION',
                  0x015: 'POS', 0x01A: 'ACTION', 0x05E: 'MAPRECT', 0x0E7: 'REQLOGOUT'}


def u32(b, o):
    return struct.unpack_from('<I', b, o)[0]


def cstr(b):
    return bytes(b).split(b'\0', 1)[0].decode('latin-1', 'replace')


def ip_str(n_bytes):
    return socket.inet_ntoa(bytes(n_bytes))


def hexdump(data, prefix='        ', width=16):
    out = []
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        hx = ' '.join('%02x' % c for c in chunk)
        asc = ''.join(chr(c) if 32 <= c < 127 else '.' for c in chunk)
        out.append('%s%04x  %-*s  %s' % (prefix, i, width * 3 - 1, hx, asc))
    return '\n'.join(out)


# --------------------------------------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------------------------------------

class Log:
    def __init__(self, path=None, dump=False, quiet=False, zone_trace=True):
        self.lock = threading.Lock()
        if path and os.path.exists(path) and os.path.getsize(path) > 20 * 1024 * 1024:
            os.replace(path, path + '.1')                 # keep one old log; start a fresh one
        self.fh = open(path, 'a', buffering=1, encoding='utf-8') if path else None
        self.dump = dump
        self.quiet = quiet
        self.zone_trace = zone_trace

    def __call__(self, tag, msg, data=None):
        ts = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
        line = '%s [%s] %s' % (ts, tag, msg)
        if data is not None and self.dump:
            line += '\n' + hexdump(data)
        with self.lock:
            if not self.quiet:
                print(line, flush=True)
            if self.fh:
                self.fh.write(line + '\n')


# --------------------------------------------------------------------------------------------------------
# Players file
# --------------------------------------------------------------------------------------------------------

class Player:
    def __init__(self, name, account, password, ps2_ip=None):
        self.name, self.account, self.password, self.ps2_ip = name, account, password, ps2_ip

    def __repr__(self):
        return 'Player(%s, account=%s%s)' % (self.name, self.account, ', ps2=' + self.ps2_ip if self.ps2_ip else '')


def load_players(path, log=None):
    """players.txt: one player per line: name, account, password [, PS2 IP]. Commas or tabs/spaces.
    Lines starting with # are comments."""
    players = []
    if not path or not os.path.exists(path):
        return players
    with open(path, encoding='utf-8', errors='replace') as f:
        for lineno, line in enumerate(f, 1):
            s = line.strip()
            if not s or s.startswith('#'):
                continue
            parts = [p.strip() for p in s.split(',')] if ',' in s else s.split()
            if len(parts) < 3 or not parts[1] or not parts[2]:
                if log:
                    log('config', '%s line %d ignored: need "name, account, password"' % (path, lineno))
                continue
            players.append(Player(parts[0], parts[1], parts[2], parts[3] if len(parts) > 3 and parts[3] else None))
    return players


def find_player(players, account, ps2_ip):
    acc = (account or '').lower()
    for p in players:
        if acc and p.account.lower() == acc:
            return p, 'account name in the PS2 login packet'
    for p in players:
        if p.ps2_ip and p.ps2_ip == ps2_ip:
            return p, 'PS2 IP address'
    return None, None


def pw16(password):
    """The patched PS2 client's 16-byte password field: the -pass string zero-padded (or cut) to 16 bytes."""
    return password.encode('latin-1', 'replace')[:16].ljust(16, b'\0')


def world_key20(password, k4):
    return pw16(password) + struct.pack('<I', k4 & 0xFFFFFFFF)


# --------------------------------------------------------------------------------------------------------
# LSB login (auth, TLS 1.3 JSON) and the data channel
# --------------------------------------------------------------------------------------------------------

class LoginError(Exception):
    pass


AUTH_RESULTS = {0: 'account banned or not normal', 2: 'wrong account name or password', 0x0A: 'already logged in',
                0x13: 'trust token invalid'}


def lsb_login(host, port, user, password, timeout=10.0, source_ip=None):
    """xiloader-equivalent login. Returns (account_id, session_hash[16])."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE           # LSB uses a self-signed cert; xiloader does not verify either
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    raw = socket.create_connection((host, port), timeout, (source_ip, 0) if source_ip else None)
    try:
        s = ctx.wrap_socket(raw)
        req = {'username': user, 'password': password, 'otp': '', 'new_password': '', 'version': [2, 2, 0],
               'command': 0x10, 'trust_token': '', 'trust_this_computer': False}
        s.sendall(json.dumps(req).encode())
        buf = b''
        rep = None
        while rep is None:
            chunk = s.recv(8192)
            if not chunk:
                break
            buf += chunk
            try:
                rep = json.loads(buf.decode('utf-8', 'replace'))
            except ValueError:
                continue
        try:
            s.close()
        except OSError:
            pass
    except socket.timeout:
        raise LoginError('LSB auth server did not answer (timeout)')
    finally:
        raw.close()
    if rep is None:
        raise LoginError('LSB auth server closed the connection without a reply')
    if 'error_message' in rep:
        raise LoginError('LSB auth: %s' % rep['error_message'])
    res = rep.get('result')
    if res != 1:
        raise LoginError('LSB auth refused: result %s (%s)' % (res, AUTH_RESULTS.get(res, '')))
    h = bytes(rep.get('session_hash') or [])
    if len(h) != 16:
        raise LoginError('LSB auth reply has no 16-byte session_hash')
    return int(rep['account_id']), h


class DataChannel:
    """The POL-side lobby channel xiloader keeps open (plain TCP, LSB data port)."""

    def __init__(self, sess):
        self.sess = sess
        self.sock = None
        self.thread = None
        self.closed = False

    def open(self):
        s = self.sess
        self.sock = socket.create_connection((s.cfg.lsb_host, s.cfg.data_port), 10,
                                             (s.cfg.source_ip, 0) if s.cfg.source_ip else None)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock.settimeout(None)
        self.send(b'\xFE' + b'\0' * 11 + s.hash, '0xFE hello (session hash)')
        self.thread = threading.Thread(target=self._run, name='data-%s' % s.tag, daemon=True)
        self.thread.start()

    def send(self, pkt, what, shown=None):
        """`shown` replaces pkt in --dump output (0xA2 carries the password bytes, which are never logged)."""
        self.sess.log(self.sess.tag, 'data  proxy -> LSB  %s (%d B)' % (what, len(pkt)), pkt if shown is None else shown)
        self.sock.sendall(pkt)

    def close(self):
        self.closed = True
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.sock.close()

    def _run(self):
        s = self.sess
        buf = b''
        try:
            while True:
                chunk = self.sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
                while buf:
                    if len(buf) >= 8 and buf[4:8] == IXFF:            # a lobby packet written on the data socket
                        n = u32(buf, 0)
                        if n < 0x1C or n > 0x1000:
                            s.log(s.tag, 'data  LSB -> proxy  bad lobby-format packet, dropping %d B' % len(buf), buf)
                            buf = b''
                            break
                        if len(buf) < n:
                            break
                        pkt, buf = buf[:n], buf[n:]
                        s.on_data_lobby_packet(pkt)
                        continue
                    op = buf[0]
                    need = {0x01: 5, 0x02: 5, 0x03: 0x148}.get(op)
                    if need is None:
                        s.log(s.tag, 'data  LSB -> proxy  unknown opcode 0x%02X, dropping %d B' % (op, len(buf)), buf)
                        buf = b''
                        break
                    if len(buf) < need:
                        break
                    pkt, buf = buf[:need], buf[need:]
                    s.on_data_packet(op, pkt)
        except OSError as e:
            if not self.closed:
                s.log(s.tag, 'data  channel error: %s' % e)
        if not self.closed:
            s.log(s.tag, 'data  channel closed by LSB')


# --------------------------------------------------------------------------------------------------------
# Lobby helpers
# --------------------------------------------------------------------------------------------------------

LOBBY_FIRST_TIMEOUT = 30          # s until the first lobby packet (0x26)
LOBBY_IDLE_TIMEOUT = 1800         # s a lobby connection may stay silent (character select screen)
MAX_LOBBY_SESSIONS = 64
MAX_ZONE_CLIENTS = 256


def lobby_md5_fix(pkt):
    pkt = bytearray(pkt)
    pkt[12:28] = b'\0' * 16
    pkt[12:28] = hashlib.md5(bytes(pkt)).digest()
    return bytes(pkt)


def lobby_md5_ok(pkt):
    z = bytearray(pkt)
    z[12:28] = b'\0' * 16
    return hashlib.md5(bytes(z)).digest() == bytes(pkt[12:28])


def lobby_error(code):
    p = bytearray(0x24)
    p[0] = 0x24
    p[4:8] = IXFF
    p[8] = 0x04
    p[28] = 0x10
    struct.pack_into('<H', p, 32, code)
    return lobby_md5_fix(p)


def read_lobby_packet(sock, pending):
    """Read one lobby packet (u32 size | IXFF | u32 cmd | 16-byte id | data) from a stream socket.
    `pending` is a bytearray carried between calls. Returns bytes, or None on EOF."""
    while True:
        if len(pending) >= 8:
            n = u32(pending, 0)
            if pending[4:8] != IXFF or n < 0x1C or n > 0xFC0:
                # Not lobby framing: hand back whatever we have so the relay keeps working.
                out = bytes(pending)
                del pending[:]
                return out
            if len(pending) >= n:
                out = bytes(pending[:n])
                del pending[:n]
                return out
        chunk = sock.recv(65536)
        if not chunk:
            if pending:
                out = bytes(pending)
                del pending[:]
                return out
            return None
        pending += chunk


def lobby_cmd(pkt):
    return u32(pkt, 8) & 0x7FFFFFFF if len(pkt) >= 12 else -1


def lobby_name(cmd):
    return '0x%02X %s' % (cmd, LOBBY_NAMES.get(cmd, '?'))


# --------------------------------------------------------------------------------------------------------
# Lobby session (one per PS2 TCP connection)
# --------------------------------------------------------------------------------------------------------

def internet_ip_for(cfg, client_ip):
    """release: the public address to hand a player who connected from a public (internet) address, else None.
    Read from --internet-ip-file on every login, so the Server App can change it without a restart."""
    path = getattr(cfg, 'internet_ip_file', None)
    if not path:
        return None
    try:
        a = ipaddress.ip_address(client_ip)
    except ValueError:
        return None
    if (a.is_private or a.is_loopback or a.is_link_local or a.is_multicast or a.is_unspecified
            or a in ipaddress.ip_network('100.64.0.0/10')):     # home network, this computer, Tailscale
        return None
    try:
        with open(path) as f:
            ip = f.read().split()[0]
        socket.inet_aton(ip)
        return ip
    except (OSError, IndexError):
        return None


class LobbySession(threading.Thread):
    counter = 0
    active = 0
    counter_lock = threading.Lock()
    # LSB locks an IP out after 5 failed logins in 60 s, and every PS2 reaches LSB from this proxy's IP. So a
    # wrong password in the players file must not be retried for a while, or it would lock everyone out.
    auth_failures = {}

    def __init__(self, cfg, log, relay, csock, caddr):
        super().__init__(daemon=True)
        with LobbySession.counter_lock:
            LobbySession.counter += 1
            self.tag = 'L%d' % LobbySession.counter
        self.name = 'lobby-' + self.tag
        self.cfg, self.log, self.relay = cfg, log, relay
        self.csock, self.caddr = csock, caddr
        self.facing_ip = csock.getsockname()[0]           # the proxy address the PS2 dialled
        if self.facing_ip in ('0.0.0.0', ''):
            self.facing_ip = cfg.public_ip or '127.0.0.1'
        self.public_ip = cfg.public_ip or internet_ip_for(cfg, caddr[0]) or self.facing_ip   # release: per connection
        self.usock = None
        self.data = None
        self.player = None
        self.account_id = None
        self.hash = None
        self.closing = False
        self.send_lock = threading.Lock()
        # Model of the PS2 client's lobby key counter (lpkt_work+0x138).
        self.k0 = None
        self.key = None
        self.digest_checked = False
        self.digest_mode = None                           # 'patched' / 'unpatched' / 'mismatch'
        self.last_ccmd = None
        with LobbySession.counter_lock:
            LobbySession.active += 1
        # Mirror of LSB's own key adjustments for this login session (data_session.cpp 0xA2).
        self.lsb_created = False
        self.lsb_increment = 0
        self.sent_a2_k4 = None

    # -- plumbing ------------------------------------------------------------------------------------------
    def to_client(self, pkt, note=''):
        cmd = lobby_cmd(pkt)
        self.log(self.tag, 'lobby proxy -> PS2  %s (%d B)%s' % (lobby_name(cmd), len(pkt), note), pkt)
        with self.send_lock:
            self.csock.sendall(pkt)

    def fail(self, why, code=ERR_LOBBY):
        self.log(self.tag, 'ERROR: %s -> sending lobby error %d to the PS2 (it shows FFXI-%d)' % (why, code, 3000 + code))
        try:
            self.to_client(lobby_error(code))
        except OSError:
            pass

    def close(self):
        if self.closing:
            return
        self.closing = True
        for s in (self.usock, self.csock):
            if s:
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    s.close()
                except OSError:
                    pass
        if self.data:
            d = self.data
            # LSB writes 0x0B and closes the view right after our 0xA2; give it a moment, then close data.
            t = threading.Timer(self.cfg.data_linger, d.close)
            t.daemon = True
            t.start()

    def run(self):
        try:
            self._run()
        except Exception as e:                                                   # noqa: BLE001
            if not self.closing:
                self.log(self.tag, 'session error: %s\n%s' % (e, traceback.format_exc()))
        finally:
            self.close()
            with LobbySession.counter_lock:
                LobbySession.active -= 1
            self.log(self.tag, 'lobby connection from %s:%d closed' % self.caddr)

    # -- main flow -----------------------------------------------------------------------------------------
    def _run(self):
        self.log(self.tag, 'PS2 %s:%d connected to lobby %s:%d' % (self.caddr[0], self.caddr[1], self.facing_ip,
                                                                  self.csock.getsockname()[1]))
        self.csock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.csock.settimeout(LOBBY_FIRST_TIMEOUT)            # silent connections do not hold a thread
        cpend = bytearray()
        try:
            first = read_lobby_packet(self.csock, cpend)
        except socket.timeout:
            self.log(self.tag, 'no lobby packet within %ds; closing' % LOBBY_FIRST_TIMEOUT)
            return
        if first is None:
            return
        self.csock.settimeout(LOBBY_IDLE_TIMEOUT)
        cmd = lobby_cmd(first)
        self.log_client_packet(first)
        if cmd != 0x26:
            self.fail('first PS2 packet is %s, expected 0x26 RequestLobbyLogin' % lobby_name(cmd))
            return
        account = cstr(first[0x1C:0x2C]) if len(first) >= 0x2C else ''
        players = load_players(self.cfg.players, self.log)
        self.player, how = find_player(players, account, self.caddr[0])
        if not self.player:
            self.fail('no player in %s for account "%s" / PS2 %s' % (self.cfg.players, account, self.caddr[0]))
            return
        self.log(self.tag, 'player "%s" (account %s) chosen by %s' % (self.player.name, self.player.account, how))
        if account and account.lower() != self.player.account.lower():
            self.log(self.tag, 'note: PS2 sent account "%s", logging into LSB as "%s"' % (account, self.player.account))

        # 1. auth (TLS JSON); a hash starting with 0x00 cannot be matched by LSB, so retry.
        fkey = (self.player.account.lower(), self.player.password)
        last = LobbySession.auth_failures.get(fkey)
        if last and time.time() - last[0] < 65:
            self.fail('LSB refused account %s %ds ago (%s); not retrying yet so LSB does not lock this proxy '
                      'out for every player' % (self.player.account, time.time() - last[0], last[1]))
            return
        for attempt in range(4):
            try:
                self.account_id, self.hash = lsb_login(self.cfg.lsb_host, self.cfg.auth_port, self.player.account,
                                                       self.player.password, source_ip=self.cfg.source_ip)
            except LoginError as e:
                LobbySession.auth_failures[fkey] = (time.time(), str(e))
                self.fail('LSB login for account %s failed: %s. Check the password in %s' % (
                    self.player.account, e, self.cfg.players))
                return
            except OSError as e:
                self.fail('cannot reach the LSB login server %s:%d: %s' % (self.cfg.lsb_host, self.cfg.auth_port, e))
                return
            LobbySession.auth_failures.pop(fkey, None)
            if self.hash[0] != 0:
                break
            self.log(self.tag, 'session hash starts with 0x00 (LSB cannot match it); logging in again')
        self.log(self.tag, 'LSB auth OK: account %s id %d, session hash %s..' % (self.player.account, self.account_id,
                                                                                self.hash[:2].hex()))

        # 2. data channel
        self.data = DataChannel(self)
        try:
            self.data.open()
        except OSError as e:
            self.fail('cannot open the LSB data channel %s:%d: %s' % (self.cfg.lsb_host, self.cfg.data_port, e))
            return

        # 3. view (lobby) upstream
        try:
            self.usock = socket.create_connection((self.cfg.lsb_host, self.cfg.view_port), 10,
                                                  (self.cfg.source_ip, 0) if self.cfg.source_ip else None)
        except OSError as e:
            self.fail('cannot connect to the LSB lobby (view) port %s:%d: %s' % (self.cfg.lsb_host, self.cfg.view_port, e))
            return
        self.usock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.usock.settimeout(None)
        pump = threading.Thread(target=self.pump_server, name='view-' + self.tag, daemon=True)
        pump.start()

        self.to_server(first)
        while not self.closing:
            try:
                pkt = read_lobby_packet(self.csock, cpend)
            except socket.timeout:
                self.log(self.tag, 'PS2 idle in the lobby for %ds; closing' % LOBBY_IDLE_TIMEOUT)
                break
            if pkt is None:
                self.log(self.tag, 'PS2 closed the lobby connection')
                break
            self.log_client_packet(pkt)
            self.track_client_packet(pkt)
            if not self.verified_client(pkt):
                return
            self.to_server(pkt)

    def log_client_packet(self, pkt):
        cmd = lobby_cmd(pkt)
        extra = ''
        if cmd == 0x26 and len(pkt) >= 0x83:
            extra = ' account="%s" version="%s"' % (cstr(pkt[0x1C:0x2C]), cstr(pkt[0x74:0x83]))
        elif cmd in (0x07, 0x28, 0x2B) and len(pkt) >= 0x33:
            extra = ' charid=%d name="%s"' % (u32(pkt, 0x1C), cstr(pkt[0x24:0x33]))
        elif cmd == 0x22 and len(pkt) >= 0x2F:
            extra = ' name="%s"' % cstr(pkt[0x20:0x2F])
        elif cmd == 0x14 and len(pkt) >= 0x20:
            extra = ' charid=%d' % u32(pkt, 0x1C)
        md5 = 'md5 ok' if lobby_md5_ok(pkt) else 'md5 BAD'
        self.log(self.tag, 'lobby PS2 -> proxy  %s (%d B, %s)%s' % (lobby_name(cmd), len(pkt), md5, extra), pkt)

    def track_client_packet(self, pkt):
        cmd = lobby_cmd(pkt)
        self.last_ccmd = cmd
        at = LOBBY_DIGEST_AT.get(cmd)
        if at is None or self.key is None or len(pkt) < at + 16:
            return
        if not self.digest_checked:
            self.digest_checked = True
            dig = bytes(pkt[at:at + 16])
            pw = self.player.password.encode('latin-1', 'replace')
            for d in (0, -1, 1, -2, 2, 3) + tuple(range(4, 64)) + tuple(range(-16, -2)):   # the client's key counter advances with every lobby reconnect inside one emulator run (create / select / back): accept a wide drift (only an unrelated password can fail)
                k = struct.pack('<I', (self.key + d) & 0xFFFFFFFF)
                if hashlib.md5(pw16(self.player.password) + k).digest() == dig or hashlib.md5(pw[:15] + k).digest() == dig:
                    self.key = (self.key + d) & 0xFFFFFFFF
                    break
            k = struct.pack('<I', self.key & 0xFFFFFFFF)
            if hashlib.md5(pw16(self.player.password) + k).digest() == dig:
                self.digest_mode = 'patched'
                self.log(self.tag, 'check: PS2 password matches the players file and the client has the key patch '
                                   '(digest = MD5(pass16 || key))')
            elif hashlib.md5(pw[:15] + k).digest() == dig:
                self.digest_mode = 'unpatched'
                self.log(self.tag, 'WARNING: PS2 password matches but the client is NOT key-patched (P4 missing): '
                                   'its world key will not match LSB; zone-in will fail')
            else:
                self.digest_mode = 'mismatch'
                self.log(self.tag, 'WARNING: the PS2 lobby digest does not match the password in the players file '
                                   '(or the lobby key count is off). The world key will not match; fix players.txt '
                                   'or the PS2 -pass value')
        self.key += 1

    def verified_client(self, pkt):
        """the proxy logs into LSB with the password from players.txt, so a PS2 must prove it knows that
        password (the lobby digest MD5(pass || key)) before any of its packets after 0x26 reach LSB. Otherwise anyone on
        the LAN who knows an account name could list, create or delete that player's characters."""
        if self.digest_mode in ('patched', 'unpatched') or getattr(self.cfg, 'allow_unverified_lobby', False):
            return True
        cmd = lobby_cmd(pkt)
        if self.digest_mode == 'mismatch':
            self.fail('the PS2 did not prove the password of account %s (lobby digest mismatch); refusing %s' % (
                self.player.account, lobby_name(cmd)))
        else:
            self.fail('PS2 sent %s before any password proof; refusing' % lobby_name(cmd))
        return False

    def to_server(self, pkt):
        out = bytearray(pkt)
        if len(out) >= 28 and out[4:8] == IXFF:
            out[12:28] = self.hash
        ver = os.environ.get('PS2PROXY_CLIENT_VERSION', '30260906_0' if getattr(self.cfg, 'client', '2007') == '2012' else '')
        if ver and lobby_cmd(out) == 0x26 and len(out) >= 0x83:       # the server wants its own client-version string (LSB: 'incorrect client version' makes it refuse character creation)
            out[0x74:0x83] = ver.encode('latin-1')[:15].ljust(15, b'\0')
        self.usock.sendall(bytes(out))
        self.log(self.tag, 'lobby proxy -> LSB  %s (%d B, session hash written at 12..27)' % (lobby_name(lobby_cmd(out)),
                                                                                           len(out)))

    # -- LSB -> PS2 ----------------------------------------------------------------------------------------
    def pump_server(self):
        spend = bytearray()
        try:
            while not self.closing:
                pkt = read_lobby_packet(self.usock, spend)
                if pkt is None:
                    self.log(self.tag, 'LSB closed the lobby (view) connection')
                    break
                self.on_server_packet(pkt, 'view')
        except OSError as e:
            if not self.closing:
                self.log(self.tag, 'lobby upstream error: %s' % e)
        finally:
            # Like LSB after 0x0B: the client waits for the server to close. Close the PS2 side too.
            time.sleep(0.2)
            self.close()

    def on_server_packet(self, pkt, via):
        cmd = lobby_cmd(pkt)
        md5 = 'md5 ok' if lobby_md5_ok(pkt) else 'md5 BAD'
        self.log(self.tag, 'lobby LSB -> proxy  %s (%d B, %s, via %s)' % (lobby_name(cmd), len(pkt), md5, via), pkt)
        note = ''
        if cmd == 0x05 and len(pkt) >= 0x24:
            self.k0 = u32(pkt, 0x1C)
            self.key = self.k0 + 1
            self.log(self.tag, 'lobby key K0 = 0x%08X, excode_server = 0x%08X' % (self.k0, u32(pkt, 0x20)))
            if getattr(self.cfg, 'client', '2007') == '2012' and u32(pkt, 0x20) != EXCODE_2012:
                # 2012 client: every expansion the client can mark installed (0x07FF);
                # LSB's login.lua keeps the 2007 disc's set for 2007 clients.
                p = bytearray(pkt); struct.pack_into('<I', p, 0x20, EXCODE_2012)
                pkt = bytes(lobby_md5_fix(p))
                note = ' [2012: excode_server -> 0x%04X, md5 fixed]' % EXCODE_2012
        elif cmd == 0x20 and len(pkt) >= 0x20:
            pkt, note = self.fix_chrinfo(pkt)
            self.bump()
        elif cmd == 0x23:
            n = u32(pkt, 0x1C) if len(pkt) >= 0x20 else 0
            worlds = [cstr(pkt[0x24 + i * 0x14:0x34 + i * 0x14]) for i in range(min(n, 8))]
            self.log(self.tag, 'world list: %s' % ', '.join(worlds))
            self.bump()
        elif cmd == 0x03:
            if self.last_ccmd == 0x21:
                self.lsb_created = True
            elif self.last_ccmd in (0x14, 0x28):
                self.lsb_increment += 4
            self.bump()
        elif cmd == 0x04 and len(pkt) >= 0x22:
            code = struct.unpack_from('<H', pkt, 0x20)[0]
            if code == 201:
                self.lsb_increment += 1
            self.log(self.tag, 'LSB lobby error %d (PS2 shows FFXI-%d): %s' % (code, 3000 + code,
                                                                               LOBBY_ERRORS.get(code, '?')))
        elif cmd == 0x0B and len(pkt) >= 0x48:
            pkt, note = self.fix_nextlogin(pkt)
            self.bump()
        self.to_client(pkt, note)

    def bump(self):
        if self.key is not None:
            self.key += 1

    def fix_chrinfo(self, pkt):
        n = u32(pkt, 0x1C)
        names = []
        for i in range(min(n, MAX_CHARS)):
            off = 0x20 + i * 0x8C
            if off + 0x8C > len(pkt):
                break
            nm = cstr(pkt[off + 0x0C:off + 0x1C])
            if nm.strip():
                names.append('%s (id %d, status %d)' % (nm, u32(pkt, off), struct.unpack_from('<H', pkt, off + 8)[0]))
        self.log(self.tag, 'character list received: %d slots, characters: %s' % (n, ', '.join(names) or 'none'))
        if n <= MAX_CHARS:
            return pkt, ''
        # The PS2 client copies every record into a 16-slot table; more would overwrite its lobby state.
        p = bytearray(pkt[:0x20 + MAX_CHARS * 0x8C])
        struct.pack_into('<I', p, 0, len(p))
        struct.pack_into('<I', p, 0x1C, MAX_CHARS)
        return lobby_md5_fix(p), ' [clamped %d -> %d slots, md5 fixed]' % (n, MAX_CHARS)

    def fix_nextlogin(self, pkt):
        p = bytearray(pkt)
        charid = u32(p, 0x1C)
        name = cstr(p[0x24:0x34])
        zip_, zport = ip_str(p[0x38:0x3C]), u32(p, 0x3C)
        sip, sport = ip_str(p[0x40:0x44]), u32(p, 0x44)
        self.log(self.tag, 'LSB hands out zone %s:%d, search %s:%d for "%s" (charid %d)' % (zip_, zport, sip, sport,
                                                                                         name, charid))
        # Predicted zone keys: the client counts +1 for this 0x0B and +2 in cliinit.
        client_k4 = (self.key + 1 + 2) if self.key is not None else None
        srv_k4 = self.lsb_final_k4()
        if client_k4 is not None and srv_k4 is not None:
            same = client_k4 == srv_k4
            self.log(self.tag, 'zone key: PS2 model key[4]=0x%08X, LSB stored key[4]=0x%08X -> %s' % (
                client_k4, srv_k4, 'match' if same else 'DIFFER (the relay will bridge the two keys)'))
        note = ''
        if self.relay is not None:
            self.relay.add_ticket(ZoneTicket(self, charid, name, (zip_, zport), client_k4, srv_k4))
            p[0x38:0x3C] = socket.inet_aton(self.public_ip)
            struct.pack_into('<I', p, 0x3C, self.relay.port)
            note = ' [zone address rewritten to the relay %s:%d' % (self.public_ip, self.relay.port)
            if getattr(self.cfg, 'search_relay_port', None):
                # The 2007 search query/reply formats differ from LSB's: send /sea through the proxy.
                p[0x40:0x44] = socket.inet_aton(self.public_ip)
                struct.pack_into('<I', p, 0x44, self.cfg.search_relay_port)
                note += ', search to %s:%d' % (self.public_ip, self.cfg.search_relay_port)
            p = bytearray(lobby_md5_fix(p))
            note += ', md5 fixed]'
        return bytes(p), note

    def lsb_final_k4(self):
        if self.sent_a2_k4 is None:
            return None
        k = self.sent_a2_k4
        low = (k + (6 if self.lsb_created else 0) + self.lsb_increment) & 0xFF   # LSB adds to key3[16] (one byte)
        return (k & ~0xFF) | low

    # -- data channel events -------------------------------------------------------------------------------
    def on_data_packet(self, op, pkt):
        if op == 0x01:
            self.log(self.tag, 'data  LSB -> proxy  0x01 (send account; PS2 asked for its characters)', pkt)
            a1 = (b'\xA1' + struct.pack('<I', self.account_id) + socket.inet_aton(self.public_ip) + b'\0' * 3
                  + self.hash)
            self.data.send(a1, '0xA1 account %d, server ip %s' % (self.account_id, self.public_ip))
        elif op == 0x02:
            self.log(self.tag, 'data  LSB -> proxy  0x02 (send world key; PS2 selected a character)', pkt)
            k0 = self.k0 if self.k0 is not None else LSB_K0
            self.sent_a2_k4 = (k0 + 9) & 0xFFFFFFFF
            key = world_key20(self.player.password, self.sent_a2_k4)
            a2 = b'\xA2' + key + b'\0' * 7
            self.data.send(a2, '0xA2 world key = pass16 || le32(K0+9 = 0x%08X)' % self.sent_a2_k4,
                           shown=b'\xA2' + b'*' * 16 + a2[17:])
        elif op == 0x03:
            n = pkt[1]
            ids = []
            for i in range(n):
                off = 16 * (i + 1)
                if off + 8 <= len(pkt):
                    cid = u32(pkt, off)
                    if cid:
                        ids.append(str(cid))
            self.log(self.tag, 'data  LSB -> proxy  0x03 content-id list: %d slots, used ids: %s' % (
                n, ', '.join(ids) or 'none'), pkt)

    def on_data_lobby_packet(self, pkt):
        cmd = lobby_cmd(pkt)
        self.log(self.tag, 'data  LSB -> proxy  lobby-format %s on the data channel; passing it to the PS2' % lobby_name(cmd))
        self.on_server_packet(pkt, 'data')


# --------------------------------------------------------------------------------------------------------
# Zone crypto: FFXI Blowfish variant and the FFXI Huffman codec (both as LSB and the PS2 client use them)
# --------------------------------------------------------------------------------------------------------

def _pi_hex_words(nwords):
    """Fractional hex digits of pi as 32-bit words (the standard Blowfish P/S initialisation)."""
    bits = nwords * 32 + 64
    one = 1 << bits

    def arctan_inv(x):
        total, term, x2, n, sign = 0, one // x, x * x, 1, 1
        while term:
            total += sign * (term // n)
            term //= x2
            n += 2
            sign = -sign
        return total

    pi = 16 * arctan_inv(5) - 4 * arctan_inv(239)
    frac = pi - 3 * one
    frac >>= 64
    return [(frac >> (32 * (nwords - 1 - i))) & 0xFFFFFFFF for i in range(nwords)]


_PI = None


def _pi_tables():
    global _PI
    if _PI is None:
        w = _pi_hex_words(18 + 1024)
        assert w[0] == 0x243F6A88 and w[1] == 0x85A308D3 and w[18] == 0xD1310BA6, 'pi table self-check failed'
        _PI = (w[:18], w[18:])
    return _PI


class FFXIBlowfish:
    """LSB common/blowfish.cpp, including its quirks: the key schedule sign-extends key bytes, and the
    round function is ((S1[b]&1)^32) + ((S3[a]&1)^32) + S2[c] + S0[d]."""

    def __init__(self, key16):
        p0, s0 = _pi_tables()
        self.P = list(p0)
        S = list(s0)
        self.S = S
        j = 0
        n = len(key16)
        for i in range(18):
            data = 0
            for _ in range(4):
                b = key16[j]
                if b & 0x80:
                    b |= 0xFFFFFF00
                data = ((data << 8) | b) & 0xFFFFFFFF
                j = (j + 1) % n
            self.P[i] ^= data
        l = r = 0
        for i in range(0, 18, 2):
            l, r = self._enc(l, r)
            self.P[i], self.P[i + 1] = l, r
        for i in range(4):
            for k in range(0, 256, 2):
                l, r = self._enc(l, r)
                S[i * 256 + k], S[i * 256 + k + 1] = l, r

    def _enc(self, l, r):
        P, S = self.P, self.S
        for i in range(16):
            l ^= P[i]
            r ^= ((((S[256 + ((l >> 8) & 0xFF)] & 1) ^ 32) + ((S[768 + (l >> 24)] & 1) ^ 32)
                   + S[512 + ((l >> 16) & 0xFF)] + S[l & 0xFF]) & 0xFFFFFFFF)
            l, r = r, l
        l, r = r, l
        return l ^ P[17], r ^ P[16]

    def _dec(self, l, r):
        P, S = self.P, self.S
        for i in range(17, 1, -1):
            l ^= P[i]
            r ^= ((((S[256 + ((l >> 8) & 0xFF)] & 1) ^ 32) + ((S[768 + (l >> 24)] & 1) ^ 32)
                   + S[512 + ((l >> 16) & 0xFF)] + S[l & 0xFF]) & 0xFFFFFFFF)
            l, r = r, l
        l, r = r, l
        return l ^ P[0], r ^ P[1]

    def crypt_blocks(self, buf, decrypt):
        """In place over whole 8-byte blocks of `buf` (bytearray); a trailing partial block stays clear."""
        f = self._dec if decrypt else self._enc
        for o in range(0, len(buf) - len(buf) % 8, 8):
            l, r = struct.unpack_from('<II', buf, o)
            l, r = f(l, r)
            struct.pack_into('<II', buf, o, l, r)


def blowfish_for_key20(key20):
    h = bytearray(hashlib.md5(key20).digest())
    if 0 in h:                                            # LSB map_session.cpp: zero from the first 0x00 on
        z = h.index(0)
        h[z:] = b'\0' * (16 - z)
    return FFXIBlowfish(bytes(h))


class Huffman:
    """FFXI packet compression (LSB common/zlib.cpp with res/compress.dat + res/decompress.dat; the PS2 client's
    huffman.c uses the same format: flag byte 1, LSB-first bitstream, stored length = bits + 8)."""

    def __init__(self, res_dir):
        enc = open(os.path.join(res_dir, 'compress.dat'), 'rb').read()
        dec = open(os.path.join(res_dir, 'decompress.dat'), 'rb').read()
        e = struct.unpack('<%dI' % (len(enc) // 4), enc)
        self.codes = []
        for b in range(256):
            s = b - 256 if b >= 128 else b
            self.codes.append((e[s + 0x80], e[s + 0x180]))       # (code, length)
        d = struct.unpack('<%dI' % (len(dec) // 4), dec)
        base = d[0] - 4
        # Tree as index arrays; node n has children at d[n], d[n+1] (pointers), symbol at d[n+3] on a leaf.
        self.d, self.base = d, base
        self.root = (d[0] - base) // 4
        # Flatten to child tables for speed.
        nn = len(d)
        self.child0 = [-1] * nn
        self.child1 = [-1] * nn
        self.leaf = [None] * nn
        for n in range(nn - 3):
            c0, c1 = d[n], d[n + 1]
            if c0 == 0 and c1 == 0:
                self.leaf[n] = d[n + 3] & 0xFF
            else:
                if c0 > 0xFF:
                    self.child0[n] = (c0 - base) // 4
                if c1 > 0xFF:
                    self.child1[n] = (c1 - base) // 4
        # Self-check: every code from compress.dat must decode to its byte through the decompress tree.
        for b, (code, ln) in enumerate(self.codes):
            n = self.root
            for i in range(ln):
                n = self.child1[n] if (code >> i) & 1 else self.child0[n]
                if n < 0:
                    raise ValueError('Huffman tables inconsistent at byte 0x%02X' % b)
            if self.leaf[n] != b:
                raise ValueError('Huffman tables inconsistent at byte 0x%02X' % b)
        # Decode acceleration: map (length, code) -> byte.
        self.lookup = {(ln, code & ((1 << ln) - 1)): b for b, (code, ln) in enumerate(self.codes)}
        self.maxlen = max(ln for _, ln in self.codes)

    def encode(self, data):
        """Returns (compressed bytes incl. flag byte, bitcount_as_stored)."""
        acc = 0
        pos = 0
        codes = self.codes
        for c in data:
            code, ln = codes[c]
            acc |= (code & ((1 << ln) - 1)) << pos
            pos += ln
        body = acc.to_bytes((pos + 7) // 8, 'little') if pos else b''
        return b'\x01' + body, pos + 8

    def decode(self, comp, stored_bits):
        if not comp:
            return b''
        nbits = min(stored_bits - 8, (len(comp) - 1) * 8)        # never trust the stored bit count
        if comp[0] != 1:                                  # flag 0: stored raw (PS2 huffman_packet_decode)
            return bytes(comp[1:1 + max(nbits, 0) // 8])
        val = int.from_bytes(comp[1:], 'little')
        out = bytearray()
        c0, c1, leaf = self.child0, self.child1, self.leaf
        n = self.root
        for i in range(nbits):
            n = c1[n] if (val >> i) & 1 else c0[n]
            if n < 0:
                raise ValueError('bad Huffman stream')
            lv = leaf[n]
            if lv is not None:
                out.append(lv)
                n = self.root
        return bytes(out)


def zone_subpackets(payload):
    """Split a zone payload into (id, bytes) sub-packets (9-bit id, 7-bit size in 4-byte units, u16 sync)."""
    out = []
    o = 0
    while o + 4 <= len(payload):
        hdr = struct.unpack_from('<H', payload, o)[0]
        size = ((hdr >> 9) & 0x7F) * 4
        if size == 0 or o + size > len(payload):
            break
        out.append((hdr & 0x1FF, bytes(payload[o:o + size])))
        o += size
    return out, bytes(payload[o:])


def zone_join(subs, tail=b''):
    return b''.join(p for _, p in subs) + tail


def set_subpacket_size(pkt, new_len):
    """Return pkt cut or zero-padded to new_len (multiple of 4) with the size field updated."""
    new_len = (new_len + 3) & ~3
    p = bytearray(pkt[:new_len].ljust(new_len, b'\0'))
    hdr = struct.unpack_from('<H', p, 0)[0]
    hdr = (hdr & 0x1FF) | ((new_len // 4) << 9)
    struct.pack_into('<H', p, 0, hdr)
    return bytes(p)


def is_plain_login(frame):
    """First zone frame from the client: header + raw 0x00A + MD5(raw)."""
    if len(frame) < FFXI_HEADER + 0x5C + 16:
        return False
    if (struct.unpack_from('<H', frame, FFXI_HEADER)[0] & 0x1FF) != 0x00A:
        return False
    return hashlib.md5(frame[FFXI_HEADER:-16]).digest() == frame[-16:]


# --------------------------------------------------------------------------------------------------------
# Translation hooks. fn(ctx, pkt: bytes) -> bytes (replacement; b'' drops it) or None (unchanged).
# ctx is the ZoneClient. Register with @c2s_hook(0x015) / @s2c_hook(0x00D). Optional ones are enabled
# with --translate NAME.
# --------------------------------------------------------------------------------------------------------

C2S_HOOKS = {}
S2C_HOOKS = {}
OPTIONAL_HOOKS = {}          # name -> (direction, id, fn, description)
TRANSLATION_ALIASES = {}     # group name -> [optional hook names] (e.g. "mp", filled by ps2proxy_mp.register)
# On unless --no-default-translations / --no-translate NAME (verified against the 2007 client code)
# Order matters: c2s index mapping back to LSB first; s2c looks on LSB's layout (before s2c-00d moves the 0x00D look);
# s2c NPC ids (npc) before the index renumbering (core-index).
DEFAULT_TRANSLATIONS = ['core-index-c2s', 'core-looks', 'mp', 's2c-00d', 'npc', 'core']   # 'core' = ps2proxy_core, 'npc' = ps2proxy_npc
ENABLED_TRANSLATIONS = []


def c2s_hook(pid, optional=None, desc=''):
    def deco(fn):
        if optional:
            OPTIONAL_HOOKS.setdefault(optional, []).append(('c2s', pid, fn, desc))
        else:
            C2S_HOOKS.setdefault(pid, []).append(fn)
        return fn
    return deco


def s2c_hook(pid, optional=None, desc=''):
    def deco(fn):
        if optional:
            OPTIONAL_HOOKS.setdefault(optional, []).append(('s2c', pid, fn, desc))
        else:
            S2C_HOOKS.setdefault(pid, []).append(fn)
        return fn
    return deco


def expand_translations(names):
    out = []
    for name in names:
        for n in TRANSLATION_ALIASES.get(name, [name]):
            if n not in out:
                out.append(n)
    return out


def resolve_translations(cfg):
    """--translate + DEFAULT_TRANSLATIONS (unless --no-default-translations) - --no-translate."""
    defaults = getattr(cfg, 'client_defaults', None) or DEFAULT_TRANSLATIONS      # --client 2012: ps2proxy_2012.DEFAULT_2012
    names = ([] if getattr(cfg, 'no_default_translations', False) else list(defaults)) + list(cfg.translate)
    drop = set(expand_translations(getattr(cfg, 'no_translate', []) or []))
    return [n for n in expand_translations(names) if n not in drop]


def enable_optional_hooks(names, log):
    for name in expand_translations(names):
        if name not in OPTIONAL_HOOKS:
            raise SystemExit('unknown --translate %s (known: %s)' % (name, ', '.join(sorted(
                list(OPTIONAL_HOOKS) + list(TRANSLATION_ALIASES)))))
        if name in ENABLED_TRANSLATIONS:
            continue
        ENABLED_TRANSLATIONS.append(name)
        for direction, pid, fn, desc in OPTIONAL_HOOKS[name]:
            (C2S_HOOKS if direction == 'c2s' else S2C_HOOKS).setdefault(pid, []).append(fn)
        log('proxy', 'translation "%s" enabled: %s' % (name, OPTIONAL_HOOKS[name][0][3]))


@s2c_hook(0x00B)
def _s2c_zone_change(ctx, pkt):
    """s2c 0x00B (LOGOUT / zone change): keep the PS2 on the relay by rewriting the next zone's IP:port."""
    if len(pkt) < 0x10:
        return None
    state = pkt[4]
    ip = pkt[8:12]
    port = u32(pkt, 12)
    ctx.saw_zone_change(state, ip_str(ip), port)
    if ctx.relay.cfg.zone_mode != 'relay' or state == 1 or ip == b'\0\0\0\0':
        return None
    p = bytearray(pkt)
    p[8:12] = socket.inet_aton(ctx.public_ip)
    struct.pack_into('<I', p, 12, ctx.relay.port)
    ctx.log(ctx.tag, 'zone  s2c 0x00B zone change (state %d) to %s:%d rewritten to the relay %s:%d' % (
        state, ip_str(ip), port, ctx.public_ip, ctx.relay.port))
    return bytes(p)


# c2s sizes where the 2007 client and LSB disagree: id -> (client size, LSB size).
C2S_SIZE_FIX = {0x01B: (0x1C, 0x08), 0x059: (0x08, 0x10), 0x061: (0x04, 0x08), 0x09B: (0x08, 0x0C),
                0x0DD: (0x0C, 0x10), 0x0E1: (0x8C, 0x90), 0x0E2: (0x8C, 0x90), 0x0FA: (0x0C, 0x10),
                0x0FE: (0x08, 0x0C)}


def _make_c2s_size_fix(pid, want):
    def fix(ctx, pkt):
        if len(pkt) == want:
            return None
        return set_subpacket_size(pkt, want)
    return fix


for _pid, (_cli, _lsb) in C2S_SIZE_FIX.items():
    c2s_hook(_pid, optional='c2s-sizes',
             desc='EXPERIMENTAL: pad/cut the 9 c2s packets whose PS2 size LSB rejects to LSB size')(
        _make_c2s_size_fix(_pid, _lsb))


# ---- NPC talk / event trace (always on; logs only, never changes a packet)..
ACTION_NAMES = {0x00: 'talk', 0x02: 'attack', 0x03: 'cast', 0x04: 'disengage', 0x07: 'weaponskill',
                0x09: 'ability', 0x0B: 'homepoint', 0x0D: 'raise-menu', 0x0E: 'fish', 0x0F: 'change-target',
                0x10: 'shoot', 0x14: 'zone-in-ready'}


def _u16(p, o):
    return struct.unpack_from('<H', p, o)[0] if len(p) >= o + 2 else 0


@c2s_hook(0x01A)
def _trace_c2s_action(ctx, pkt):
    if len(pkt) >= 0x0C:
        a = _u16(pkt, 0x0A)
        ctx.log(ctx.tag, 'event PS2 action %s (0x%02X) target %d index %d (%d B)' % (
            ACTION_NAMES.get(a, '?'), a, u32(pkt, 4), _u16(pkt, 8), len(pkt)))
    return None


@c2s_hook(0x01A)
def _c2s_action_size(ctx, pkt):
    """The 2007 client sends 0x01A ACTION as 0x10 bytes (ActionBuf[1]); LSB requires 0x1C (ActionBuf[4]) and drops
    the shorter one ("Bad packet size for GP_CLI_COMMAND_ACTION ... got 16, expected [28, 28]"), so NPC talk,
    attack, spells etc. never reached the server. Zero-padding is exact: the extra words are unused by the 2007
    client's actions."""
    if len(pkt) == 0x10:
        return set_subpacket_size(pkt, 0x1C)
    return None


@c2s_hook(0x05B)
def _trace_c2s_eventend(ctx, pkt):
    if len(pkt) >= 0x14:
        ctx.log(ctx.tag, 'event PS2 event end: event %d (event file %d) option %d target %d index %d mode %d' % (
            _u16(pkt, 0x12), _u16(pkt, 0x10), u32(pkt, 8), u32(pkt, 4), _u16(pkt, 0x0C), _u16(pkt, 0x0E)))
    return None


@s2c_hook(0x032)
def _trace_s2c_event(ctx, pkt):
    if len(pkt) >= 0x10:
        # EventNum = the event DAT to load (zone number; file 5820 + it), EventPara = the event (cutscene) id
        ctx.log(ctx.tag, 'event LSB event start (0x032): event %d (event file %d) target %d index %d mode %d' % (
            _u16(pkt, 0x0C), _u16(pkt, 0x0A), u32(pkt, 4), _u16(pkt, 8), _u16(pkt, 0x0E)))
    return None


@s2c_hook(0x034)
def _trace_s2c_eventnum(ctx, pkt):
    if len(pkt) >= 0x30:
        nums = struct.unpack_from('<8i', pkt, 8)
        ctx.log(ctx.tag, 'event LSB event start (0x034): event %d (event file %d) target %d index %d mode %d '
                         'params %s' % (_u16(pkt, 0x2C), _u16(pkt, 0x2A), u32(pkt, 4), _u16(pkt, 0x28), _u16(pkt, 0x2E),
            ','.join(str(n) for n in nums)))
    return None


@s2c_hook(0x036)
def _trace_s2c_talknum(ctx, pkt):
    if len(pkt) >= 0x0E:
        m = _u16(pkt, 0x0A)
        ctx.log(ctx.tag, 'event LSB message (0x036): text id %d%s from %d index %d' % (
            m & 0x7FFF, ' (no name)' if m & 0x8000 else '', u32(pkt, 4), _u16(pkt, 8)))
    return None


@s2c_hook(0x02A)
def _trace_s2c_talknumwork(ctx, pkt):
    if len(pkt) >= 0x1C:
        m = _u16(pkt, 0x1A)
        nums = struct.unpack_from('<4i', pkt, 8)
        ctx.log(ctx.tag, 'event LSB message (0x02A): text id %d%s params %s from %d' % (
            m & 0x7FFF, ' (no name)' if m & 0x8000 else '', ','.join(str(n) for n in nums), u32(pkt, 4)))
    return None


@s2c_hook(0x052)
def _trace_s2c_release(ctx, pkt):
    ctx.log(ctx.tag, 'event LSB release (0x052) mode %d' % (u32(pkt, 4) if len(pkt) >= 8 else -1))
    return None


# ---- entity / login checks (always on; log only, never change a packet). They show the things that make the PS2 client
# ignore an NPC: its first 0x00E must carry position, status and flags (SendFlg & 7 == 7), every 0x00E must be full length, and
# a login packet whose state is 3, 4 or 5 makes the client drop entity packets until its fade-out has finished.
@s2c_hook(0x00A)
def _diag_s2c_login(ctx, pkt):
    ctx.entities = {}
    if len(pkt) < 0x84:
        ctx.log(ctx.tag, 'diag  LSB login (0x00A) is only %d B; the PS2 reads up to 0x104' % len(pkt))
        return None
    state = u32(pkt, 0x80)
    if state in (3, 4, 5):
        ctx.log(ctx.tag, 'diag  LSB login (0x00A) state %d: the PS2 drops entity packets until its zone fade-out has ended' % state)
    return None


@s2c_hook(0x00E)
def _diag_s2c_npc(ctx, pkt):
    if len(pkt) < 0x0C:
        return None
    idx, send = _u16(pkt, 8), pkt[0x0A]
    seen = getattr(ctx, 'entities', None)
    if seen is None:
        seen = ctx.entities = {}
    if send & 0x20:                                              # despawn: the next one is a first spawn again
        seen.pop(idx, None)
        return None
    if idx not in seen and (send & 7) != 7:
        ctx.warn_once('ent-first-%d' % idx, 'diag  LSB entity %d (0x00E) first update has SendFlg 0x%02X; the PS2 drops it unless '
                                            'position, status and flags are all in it (SendFlg & 7 == 7)' % (idx, send))
    seen[idx] = seen.get(idx, 0) | send
    if len(pkt) < 0x44:
        ctx.warn_once('ent-short', 'diag  LSB entity update (0x00E) of %d B is shorter than the 0x48 the PS2 expects' % len(pkt))
    return None


@c2s_hook(0x017)
def _diag_c2s_entity_again(ctx, pkt):
    if len(pkt) >= 0x0C:
        ctx.log(ctx.tag, 'diag  PS2 asks for entity %d again (0x017, id %08X)' % (_u16(pkt, 4), u32(pkt, 8)))
    return None


@s2c_hook(0x00D, optional='s2c-00d',
          desc='EXPERIMENTAL: s2c 0x00D (other PCs) to the 2007 PS2 layout: models 0x48->0x3E, name 0x5A->0x50')
def _s2c_char_pc_2007(ctx, pkt):
    if len(pkt) <= 0x3E:
        return None
    # LSB 0x3E..0x47 are post-2007 fields (Monstrosity, Geo, Flags6); the 2007 client reads models at 0x3E.
    body = pkt[:0x3E] + (pkt[0x48:] if len(pkt) > 0x48 else b'')
    return set_subpacket_size(body, len(body))


# Person-to-person translations (chat/tells, party/alliance, linkshell, /check) and the search relay:.
try:
    import ps2proxy_mp as _mp                                                    # noqa: E402
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ps2proxy_mp as _mp                                                    # noqa: E402
_mp.register(sys.modules[__name__])

# Core gameplay translations (0x028 actions, 0x037 status icons, item containers, c2s sizes):.
try:
    import ps2proxy_core as _core                                                # noqa: E402
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ps2proxy_core as _core                                                # noqa: E402
_core.register(sys.modules[__name__])

# NPC-side translations (shop list layout, NPC server ids LSB <-> 2007 entity lists):.
try:
    import ps2proxy_npc as _npc                                                  # noqa: E402
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ps2proxy_npc as _npc                                                  # noqa: E402
_npc.register(sys.modules[__name__])

# The 2012 client (Seekers of Adoulin disc engine): its own translation set, selected with --client 2012.
try:
    import ps2proxy_2012 as _c12                                                 # noqa: E402
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ps2proxy_2012 as _c12                                                 # noqa: E402
_c12.register(sys.modules[__name__])

# The 2016 host build: chat text offset, party member names, beta music ids - optional group "soc-2016"
#.
try:
    import ps2proxy_social as _soc                                               # noqa: E402
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ps2proxy_social as _soc                                               # noqa: E402
_soc.register(sys.modules[__name__])
# release: chat rules for every player - optional group "chat-rules" (FFXI 2016 Server App)
try:
    import ps2proxy_chatrules as _chat                                         # noqa: E402
    _chat.register(sys.modules[__name__])
except ImportError:
    pass
# 2016 client zone text ids / event guard - optional group "text-2016".
try:
    import ps2proxy_text2016 as _t16                                             # noqa: E402
    _t16.register(sys.modules[__name__])
except ImportError:
    pass


# --------------------------------------------------------------------------------------------------------
# Zone UDP relay
# --------------------------------------------------------------------------------------------------------

class ZoneTicket:
    """What the lobby session learned for one character select (from 0x0B)."""

    def __init__(self, lobby, charid, name, upstream, client_k4, server_k4):
        self.raw_key = getattr(lobby, 'digest_mode', None) == 'unpatched'   # 2016 client: zone key = MD5(raw password || key[4]), no 16-byte padding
        self.tag = lobby.tag
        self.player = lobby.player
        self.ps2_ip = lobby.caddr[0]
        self.public_ip = lobby.public_ip
        self.charid, self.name, self.upstream = charid, name, upstream
        self.client_k4, self.server_k4 = client_k4, server_k4
        self.created = time.time()
        self.used = False


class KeyTrack:
    """One side's zone key: key[4] values, current and previous (LSB keeps the old one while zoning)."""

    def __init__(self, password, k4, raw=False):
        self.password = password
        self.raw = raw
        self.k4 = k4
        self.prev = None
        self.known = False
        self.cache = {}

    def cipher(self, k4):
        k4 &= 0xFFFFFFFF
        bf = self.cache.get(k4)
        if bf is None:
            bf = blowfish_for_key20(self.key20(k4))
            if len(self.cache) > 8:
                self.cache.clear()
            self.cache[k4] = bf
        return bf

    def key20(self, k4):
        if self.raw:                                      # unpatched 2016 client: the password at its own length (max 15) + le32(key[4])
            return self.password.encode('latin-1', 'replace')[:15] + struct.pack('<I', k4 & 0xFFFFFFFF)
        return world_key20(self.password, k4)

    def advance(self):
        self.prev = self.k4
        self.k4 = (self.k4 + 2) & 0xFFFFFFFF


def try_decrypt(frame, bf):
    body = bytearray(frame[FFXI_HEADER:])
    if len(body) < 16 + 4 + 1:
        return None
    bf.crypt_blocks(body, decrypt=True)
    if hashlib.md5(bytes(body[:-16])).digest() != bytes(body[-16:]):
        return None
    return bytes(body)


class ZoneClient:
    counter = 0

    def __init__(self, relay, addr, ticket):
        ZoneClient.counter += 1
        self.tag = 'Z%d' % ZoneClient.counter
        self.relay, self.log, self.addr = relay, relay.log, addr
        self.up = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if relay.cfg.source_ip:
            self.up.bind((relay.cfg.source_ip, 0))
        self.up.setblocking(False)
        self.last = time.time()
        self.frames = [0, 0]
        self.login_retry = None
        self.opaque_warned = set()
        self.pending_zone = None
        self.attach(ticket)

    def attach(self, ticket):
        self.ticket = ticket
        if ticket:
            ticket.used = True
            self.upstream = ticket.upstream
            self.public_ip = ticket.public_ip
            pw = ticket.player.password
            ck = ticket.client_k4 if ticket.client_k4 is not None else (LSB_K0 + 9)
            sk = ticket.server_k4 if ticket.server_k4 is not None else (LSB_K0 + 9)
            self.ckey = KeyTrack(pw, ck, raw=ticket.raw_key)
            self.skey = KeyTrack(pw, sk)
            if ticket.raw_key:
                self.log(self.tag, 'zone  unpatched (2016) client: its zone key is MD5(raw password || key[4]); translating to the LSB key')
            self.log(self.tag, 'PS2 %s:%d is "%s" (charid %d, lobby %s); relaying to zone server %s:%d' % (
                self.addr[0], self.addr[1], ticket.name, ticket.charid, ticket.tag, self.upstream[0], self.upstream[1]))
        else:
            self.upstream = (self.relay.cfg.lsb_host, self.relay.cfg.map_port)
            self.public_ip = self.relay.default_public_ip
            self.ckey = self.skey = None
            self.log(self.tag, 'PS2 %s:%d not matched to a lobby login; passing through to %s:%d without '
                               'decryption' % (self.addr[0], self.addr[1], self.upstream[0], self.upstream[1]))

    def saw_zone_change(self, state, ip, port):
        self.pending_zone = (state, ip, port)
        if state != 1 and ip != '0.0.0.0' and port and (ip, port) != tuple(self.upstream):
            self.log(self.tag, 'zone  next zone server is %s:%d (was %s:%d)' % (ip, port, self.upstream[0],
                                                                              self.upstream[1]))
            self.upstream = (ip, port)

    def key_from_ticket(self, frame):
        """The plain 0x00A carries Ticket = MD5(account[15] || zone key) (2003 decompile: gczone.c StepCalc ->
        createLoginTicket; zone key = the 16-byte "Passwd to Login to Zone", MD5(pass16 || le32(key[4])) cut at
        its first 0x00). Matching it tells us the PS2's key[4] before the first encrypted frame. LSB ignores it."""
        base = FFXI_HEADER
        ticket = bytes(frame[base + 0x40:base + 0x50])
        if ticket == b'\0' * 16:
            return
        acc = bytes(frame[base + 0x31:base + 0x40])
        pw = self.ckey.key20(0)[:-4] if self.ckey.raw else pw16(self.ckey.password)
        model = self.ckey.k4
        order = [model, (model + 2) & 0xFFFFFFFF] + [(model & ~0xFF) | ((model + d) & 0xFF) for d in range(-16, 240)]
        seen = set()
        for k4 in order:
            if k4 in seen:
                continue
            seen.add(k4)
            h = bytearray(hashlib.md5(pw + struct.pack('<I', k4)).digest())
            n = h.index(0) if 0 in h else 16
            for key in (bytes(h[:n]).ljust(16, b'\0'), bytes(h[:n])):
                if hashlib.md5(acc + key).digest() == ticket:
                    if k4 != model:
                        self.log(self.tag, 'zone  PS2 key[4]=0x%08X from the 0x00A ticket (model said 0x%08X)' % (k4, model))
                        self.ckey.k4 = k4
                    else:
                        self.log(self.tag, 'zone  0x00A ticket confirms the PS2 key[4]=0x%08X' % k4)
                    self.ckey.known = True
                    return
        self.warn_once('ticket', 'zone  the 0x00A ticket matches no key candidate (password differs from players.txt, '
                                 'or the ticket formula of the 2003 decompile does not hold for this build)')

    # -- key search --------------------------------------------------------------------------------------
    def find_key(self, frame, track, side, other=None):
        """Decrypt `frame` with `track`, trying current, previous, next; then a one-time search of the low
        byte of key[4] (LSB adds its adjustments to that byte). Returns (body, k4) or (None, None)."""
        cands = [track.k4]
        if track.prev is not None:
            cands.append(track.prev)
        cands.append((track.k4 + 2) & 0xFFFFFFFF)
        if other is not None and other.known:
            cands.append(other.k4)
        for k4 in cands:
            body = try_decrypt(frame, track.cipher(k4))
            if body is not None:
                return body, k4
        if track.known or getattr(track, 'searched', False):
            return None, None
        track.searched = True
        t0 = time.time()
        hi = track.k4 & ~0xFF
        order = list(range(0, 64)) + list(range(-16, 0)) + list(range(64, 240))
        tried = set(cands)
        for d in order:
            k4 = hi | ((track.k4 + d) & 0xFF)
            if k4 in tried:
                continue
            tried.add(k4)
            body = try_decrypt(frame, blowfish_for_key20(track.key20(k4)))
            if body is not None:
                self.log(self.tag, 'zone  %s key found by search: key[4]=0x%08X (model was 0x%08X, %.1fs)' % (
                    side, k4, track.k4, time.time() - t0))
                return body, k4
        self.log(self.tag, 'zone  %s key NOT found (%d keys tried in %.1fs): wrong password in players.txt, or '
                           'an unpatched client. Frames will pass through unmodified.' % (side, len(tried),
                                                                                           time.time() - t0))
        return None, None

    # -- frames --------------------------------------------------------------------------------------------
    def decode(self, body):
        body_nomd5 = body[:-16]
        stored = u32(body_nomd5, len(body_nomd5) - 4)
        comp = body_nomd5[:-4]
        return self.relay.huff.decode(comp, stored)

    def encode(self, header, payload, bf):
        comp, stored = self.relay.huff.encode(payload)
        body = bytearray(comp + struct.pack('<I', stored))
        body += hashlib.md5(bytes(body)).digest()
        bf.crypt_blocks(body, decrypt=False)
        return bytes(header) + bytes(body)

    @staticmethod
    def describe(subs, names):
        """'063:MISCDATA(148)x12 055(136)x7 ...' - runs of the same id and size are grouped."""
        parts = []
        for pid, p in subs:
            item = '%03X%s(%d)' % (pid, ':' + names[pid] if pid in names else '', len(p))
            if parts and parts[-1][0] == item:
                parts[-1][1] += 1
            else:
                parts.append([item, 1])
        return ' '.join(i if n == 1 else '%sx%d' % (i, n) for i, n in parts) or '(no packets)'


    def run_hooks(self, subs, hooks):
        changed = False
        out = []
        for pid, p in subs:
            for fn in hooks.get(pid, ()):
                try:
                    r = fn(self, p)
                except Exception as e:                                           # noqa: BLE001
                    self.log(self.tag, 'hook %s failed on %03X: %s' % (fn.__name__, pid, e))
                    r = None
                if r is not None:
                    changed = True
                    p = r
                    if not p:
                        break
            if p:
                out.append((pid, p))
        return out, changed

    def c2s(self, frame):
        """PS2 -> zone server. Returns the bytes to send upstream."""
        self.last = time.time()
        self.frames[0] += 1
        if is_plain_login(frame):
            charid = u32(frame, FFXI_HEADER + 0x0C)
            t = self.relay.take_ticket(charid, self.addr[0])
            if t is not None and t is not self.ticket and (t.ps2_ip == self.addr[0] or
                                                           getattr(self.relay.cfg, 'zone_open', False)):
                self.attach(t)
            subs, tail = zone_subpackets(frame[FFXI_HEADER:-16])
            self.log(self.tag, 'zone  PS2 -> LSB  plain login frame: %s charid=%d name="%s" account="%s" '
                               'platform="%s"' % (self.describe(subs, ZONE_C2S_NAMES), charid,
                                                  cstr(frame[FFXI_HEADER + 0x22:FFXI_HEADER + 0x31]),
                                                  cstr(frame[FFXI_HEADER + 0x31:FFXI_HEADER + 0x40]),
                                                  cstr(frame[FFXI_HEADER + 0x54:FFXI_HEADER + 0x58])), frame)
            if self.ckey:
                self.ckey.known = False
                self.skey.known = False
                self.key_from_ticket(frame)
            new, changed = self.run_hooks(subs, C2S_HOOKS)
            if changed:
                raw = zone_join(new, tail)
                frame = bytes(frame[:FFXI_HEADER]) + raw + hashlib.md5(raw).digest()
            if self.ckey and self.ckey.raw:
                self.login_retry = [bytes(frame), 0, time.time() + 1.0]
            return frame
        if not self.ckey or len(frame) < FFXI_HEADER + 21:
            return frame
        body, k4 = self.find_key(frame, self.ckey, 'PS2', self.skey)
        if body is None:
            self.warn_once('c2s', 'zone  PS2 -> LSB  %d B cannot be decrypted; passed through' % len(frame), frame)
            return frame
        if not self.ckey.known:
            self.ckey.known = True
            if k4 not in (self.ckey.k4, self.ckey.prev):      # the model was off; the found key is current
                self.ckey.k4 = k4
            self.log(self.tag, 'zone  PS2 key confirmed: key[4]=0x%08X' % k4)
        try:
            payload = self.decode(body)
        except ValueError as e:
            self.warn_once('c2sdec', 'zone  PS2 -> LSB  decompression failed (%s); passed through' % e, frame)
            return frame
        subs, tail = zone_subpackets(payload)
        if self.relay.log.zone_trace:
            self.log(self.tag, 'zone  PS2 -> LSB  %d B: %s' % (len(frame), self.describe(subs, ZONE_C2S_NAMES)),
                     payload)
        new, changed = self.run_hooks(subs, C2S_HOOKS)
        # Which server key matches the PS2 key used? Same relative position (current/previous).
        srv_k4 = self.map_key(k4, self.ckey, self.skey)
        if not changed and srv_k4 == k4 and not self.ckey.raw:
            return frame
        return self.encode(frame[:FFXI_HEADER], zone_join(new, tail), self.skey.cipher(srv_k4))

    def s2c(self, frame):
        """Zone server -> PS2. Returns the bytes to send to the PS2."""
        self.last = time.time()
        self.frames[1] += 1
        self.login_retry = None
        if not self.skey or len(frame) < FFXI_HEADER + 21:
            return frame               # includes LSB's empty datagrams: forward as they are, never decrypt
        body, k4 = self.find_key(frame, self.skey, 'LSB', None)
        if body is None:
            self.warn_once('s2c', 'zone  LSB -> PS2  %d B cannot be decrypted; passed through' % len(frame), frame)
            return frame
        if not self.skey.known:
            self.skey.known = True
            if k4 not in (self.skey.k4, self.skey.prev):      # the model was off; the found key is current
                self.skey.k4 = k4
            self.log(self.tag, 'zone  LSB key confirmed: key[4]=0x%08X' % k4)
        try:
            payload = self.decode(body)
        except ValueError as e:
            self.warn_once('s2cdec', 'zone  LSB -> PS2  decompression failed (%s); passed through' % e, frame)
            return frame
        subs, tail = zone_subpackets(payload)
        if self.relay.log.zone_trace:
            self.log(self.tag, 'zone  LSB -> PS2  %d B: %s' % (len(frame), self.describe(subs, ZONE_S2C_NAMES)),
                     payload)
        self.pending_zone = None
        new, changed = self.run_hooks(subs, S2C_HOOKS)
        cli_k4 = self.map_key(k4, self.skey, self.ckey)
        out = frame
        if changed or cli_k4 != k4 or self.ckey.raw:
            enc = self.encode(frame[:FFXI_HEADER], zone_join(new, tail), self.ckey.cipher(cli_k4))
            if len(enc) > ZONE_MAX_FRAME:
                self.log(self.tag, 'zone  rewritten frame is %d B (> 0x%X the PS2 accepts); sending the original' % (
                    len(enc), ZONE_MAX_FRAME))
            else:
                out = enc
        if self.pending_zone is not None and k4 != self.skey.k4:
            # A 0x00B under the previous key is LSB re-sending it (the client missed it); keys already moved.
            self.log(self.tag, 'zone  0x00B re-sent by LSB under the previous key; keys unchanged')
        elif self.pending_zone is not None:
            # LSB increments its key after sending 0x00B; the client does the same on zoning.
            self.skey.advance()
            self.ckey.advance()
            self.log(self.tag, 'zone  keys advanced for the zone change: LSB key[4]=0x%08X, PS2 key[4]=0x%08X' % (
                self.skey.k4, self.ckey.k4))
        return out

    @staticmethod
    def map_key(k4, src, dst):
        if k4 == src.k4:
            return dst.k4
        if src.prev is not None and k4 == src.prev and dst.prev is not None:
            return dst.prev
        return (dst.k4 + (k4 - src.k4)) & 0xFFFFFFFF

    def warn_once(self, key, msg, data=None):
        if key in self.opaque_warned:
            return
        self.opaque_warned.add(key)
        self.log(self.tag, msg + ' (further ones not logged)', data)

    def close(self):
        try:
            self.up.close()
        except OSError:
            pass


class ZoneRelay(threading.Thread):
    def __init__(self, cfg, log):
        super().__init__(daemon=True, name='zone-relay')
        self.cfg, self.log = cfg, log
        self.huff = Huffman(os.path.join(cfg.lsb_dir, 'res'))
        _pi_tables()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((cfg.listen_host, cfg.udp_port))
        self.sock.setblocking(False)
        self.port = self.sock.getsockname()[1]
        self.default_public_ip = cfg.public_ip or '127.0.0.1'
        self.sel = selectors.DefaultSelector()
        self.sel.register(self.sock, selectors.EVENT_READ, None)
        self.clients = {}
        self.refused = {}
        self.tickets = {}
        self.lock = threading.Lock()

    def add_ticket(self, t):
        with self.lock:
            self.tickets[t.charid] = t
        self.log(t.tag, 'zone ticket stored for charid %d; waiting for the PS2 on UDP %d' % (t.charid, self.port))

    def take_ticket(self, charid, ps2_ip):
        """The newest ticket for this character id; else an unused ticket from the same PS2 address."""
        with self.lock:
            t = self.tickets.get(charid)
            if t:
                return t
            for t in sorted(self.tickets.values(), key=lambda x: -x.created):
                if t.ps2_ip == ps2_ip and not t.used:
                    return t
        return None

    def run(self):
        last_gc = time.time()
        while True:
            for key, _ in self.sel.select(1.0):
                if key.data is None:
                    self.from_ps2()
                else:
                    self.from_zone(key.data)
            self.retry_logins()
            if time.time() - last_gc > 30:
                last_gc = time.time()
                self.gc()

    def retry_logins(self):
        """Re-send a PS2's plain 0x00A once a second until LSB answers (the 2012 client did this itself; the 2016 one sends it once)."""
        now = time.time()
        for c in list(self.clients.values()):
            r = c.login_retry
            if r is None or now < r[2]:
                continue
            if r[1] >= 45:
                c.login_retry = None
                self.log(c.tag, 'zone  LSB never answered the 0x00A after %d re-sends' % r[1])
                continue
            r[1] += 1
            r[2] = now + 1.0
            try:
                c.up.sendto(r[0], c.upstream)
            except OSError:
                pass
            if r[1] == 1:
                self.log(c.tag, 'zone  re-sending the 0x00A login once a second until LSB answers')

    def from_ps2(self):
        while True:
            try:
                frame, addr = self.sock.recvfrom(4096)
            except (BlockingIOError, InterruptedError):
                return
            except OSError as e:
                self.log('zone', 'UDP receive error: %s' % e)
                return
            c = self.clients.get(addr)
            if c is None:
                t = None
                if is_plain_login(frame):
                    t = self.take_ticket(u32(frame, FFXI_HEADER + 0x0C), addr[0])
                    if t is not None and t.ps2_ip != addr[0] and not getattr(self.cfg, 'zone_open', False):
                        self.refuse(addr, 'zone login for charid %d from %s, but that character was selected from %s' % (
                            t.charid, addr[0], t.ps2_ip))
                        continue
                if t is None and not getattr(self.cfg, 'zone_open', False):
                    # a PS2 always starts with a plain 0x00A for the character it just selected in the
                    # lobby; anything else (garbage, scans, stale sessions) must not open a relay entry and socket.
                    self.refuse(addr, 'UDP from %s:%d is not a zone login for a character selected in the lobby' % addr)
                    continue
                if len(self.clients) >= MAX_ZONE_CLIENTS:
                    self.refuse(addr, 'too many zone relay entries (%d)' % len(self.clients))
                    continue
                c = ZoneClient(self, addr, t)
                self.clients[addr] = c
                self.sel.register(c.up, selectors.EVENT_READ, c)
            try:
                out = c.c2s(frame)
            except Exception as e:                                               # noqa: BLE001
                self.log(c.tag, 'c2s processing error (%s); forwarding unmodified\n%s' % (e, traceback.format_exc()))
                out = frame
            if out is not None:
                try:
                    c.up.sendto(out, c.upstream)
                except OSError as e:
                    self.log(c.tag, 'send to zone server %s:%d failed: %s' % (c.upstream[0], c.upstream[1], e))

    def refuse(self, addr, why):
        now = time.time()
        last = self.refused.get(addr[0], 0)
        self.refused[addr[0]] = now
        if len(self.refused) > 1024:
            self.refused.clear()
        if now - last > 30:
            self.log('zone', 'dropped: %s (further ones from %s logged every 30 s at most)' % (why, addr[0]))

    def from_zone(self, c):
        while True:
            try:
                frame, addr = c.up.recvfrom(4096)
            except (BlockingIOError, InterruptedError):
                return
            except OSError as e:
                self.log(c.tag, 'zone server receive error: %s' % e)
                return
            try:
                out = c.s2c(frame)
            except Exception as e:                                               # noqa: BLE001
                self.log(c.tag, 's2c processing error (%s); forwarding unmodified\n%s' % (e, traceback.format_exc()))
                out = frame
            if out is not None:
                try:
                    self.sock.sendto(out, c.addr)
                except OSError as e:
                    self.log(c.tag, 'send to PS2 failed: %s' % e)

    def gc(self):
        now = time.time()
        for addr, c in list(self.clients.items()):
            if now - c.last > self.cfg.zone_idle:
                self.log(c.tag, 'zone relay for %s:%d idle %ds, closing (%d frames up, %d down)' % (
                    addr[0], addr[1], int(now - c.last), c.frames[0], c.frames[1]))
                self.sel.unregister(c.up)
                c.close()
                del self.clients[addr]
        with self.lock:
            for cid, t in list(self.tickets.items()):
                if now - t.created > 6 * 3600:
                    del self.tickets[cid]


# --------------------------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------------------------

def parse_args(argv=None):
    ap = argparse.ArgumentParser(description='Login/zone proxy between the patched PS2 FFXI client and LandSandBoat.')
    ap.add_argument('--players', default=DEFAULT_PLAYERS,
                    help='players file: "name, account, password[, PS2 IP]" per line (default: %(default)s)')
    ap.add_argument('--listen-host', default='0.0.0.0', help='address to listen on (default: all)')
    ap.add_argument('--lobby-port', type=int, default=54001, help='TCP port the PS2 connects to (its -port; default 54001)')
    ap.add_argument('--udp-port', type=int, default=54240, help='UDP zone relay port handed to the PS2 (default 54240)')
    ap.add_argument('--lsb-host', default='127.0.0.1', help='LSB server address (default 127.0.0.1)')
    ap.add_argument('--auth-port', type=int, default=54231)
    ap.add_argument('--data-port', type=int, default=54230)
    ap.add_argument('--view-port', type=int, default=54011,
                    help="LSB's lobby/view port (settings/network.lua LOGIN_VIEW_PORT; default 54011)")
    ap.add_argument('--map-port', type=int, default=54230, help='zone server port for unmatched UDP (default 54230)')
    ap.add_argument('--public-ip', default=None,
                    help='address to tell the PS2 for the relay and search server (default: the address it dialled)')
    ap.add_argument('--internet-ip-file', default=None,
                    help='file holding the public address handed to players who connect from the internet')
    ap.add_argument('--source-ip', default=None, help='local address for connections to LSB (default: automatic)')
    ap.add_argument('--zone-mode', choices=('relay', 'direct'), default='relay',
                    help='relay: rewrite 0x0B to this proxy and relay UDP (default). direct: pass 0x0B unchanged '
                         '(only works if LSB accepts UDP from the PS2 IP; stock LSB does not)')
    ap.add_argument('--translate', action='append', default=[],
                    help='enable an optional packet translation: %s (on by default: %s)' % (
                        ', '.join(sorted(list(OPTIONAL_HOOKS) + list(TRANSLATION_ALIASES))),
                        ', '.join(DEFAULT_TRANSLATIONS)))
    ap.add_argument('--no-translate', action='append', default=[], help='switch off one translation (or group)')
    ap.add_argument('--client', choices=('2007', '2012'), default='2007',
                    help='PS2 client build: 2007 (Vana\'diel Collection / WotG engine, default) or 2012 (Adoulin disc engine, '
                         'ps2proxy_2012 translation set, 2012 NPC id map, 2012 search widths)')
    ap.add_argument('--no-default-translations', action='store_true',
                    help='only the --translate ones (the pre-report-26 behaviour)')
    ap.add_argument('--search-port', type=int, default=54242,
                    help='TCP port of the search (/sea) relay handed to the PS2 in 0x0B; 0 = PS2 talks to xi_search '
                         'directly (default 54242)')
    ap.add_argument('--lsb-search-port', type=int, default=54002, help="xi_search's port (default 54002)")
    ap.add_argument('--no-search-translate', dest='search_translate', action='store_false',
                    help='relay /sea replies without translating them')
    ap.add_argument('--lsb-dir', default=DEFAULT_LSB_DIR, help='LSB folder (for res/compress.dat, res/decompress.dat)')
    ap.add_argument('--log', default=None, help='also append the trace to this file')
    ap.add_argument('--dump', action='store_true', help='hex-dump every packet (zone payloads decrypted)')
    ap.add_argument('--no-zone-trace', action='store_true', help='do not log every zone frame')
    ap.add_argument('--quiet', action='store_true', help='no console output (use with --log)')
    ap.add_argument('--data-linger', type=float, default=5.0, help='seconds to keep the data channel after the lobby closes')
    ap.add_argument('--zone-idle', type=float, default=180.0, help='seconds before an idle zone relay entry is dropped')
    ap.add_argument('--allow-unverified-lobby', action='store_true',
                    help='forward lobby packets even when the PS2 did not prove the players.txt password (old behaviour; '
                         ')')
    ap.add_argument('--zone-open', action='store_true',
                    help='relay UDP from any address, and zone logins from another IP than the lobby (old behaviour; '
                         ')')
    ap.add_argument('--version', action='version', version='ps2proxy ' + VERSION)
    return ap.parse_args(argv)


def serve(cfg, log, ready=None):
    if cfg.lsb_host in ('127.0.0.1', 'localhost') and cfg.view_port == cfg.lobby_port:
        raise SystemExit('LSB view port and proxy lobby port are both %d; move LSB (settings/network.lua '
                         'LOGIN_VIEW_PORT) or use --lobby-port/--view-port' % cfg.view_port)
    players = load_players(cfg.players, log)
    if not players:
        log('proxy', 'WARNING: no players in %s yet; PS2 logins will be refused until it has "name, account, '
                     'password" lines' % cfg.players)
    else:
        log('proxy', 'players file %s: %s' % (cfg.players, ', '.join('%s (%s)' % (p.name, p.account) for p in players)))
    relay = None
    if cfg.zone_mode == 'relay':
        relay = ZoneRelay(cfg, log)
        relay.start()
        log('proxy', 'zone UDP relay listening on %s:%d' % (cfg.listen_host, relay.port))
    cfg.search_relay_port = None
    if relay is not None and getattr(cfg, 'search_port', 0):
        try:
            sr = _mp.SearchRelay(sys.modules[__name__], cfg, log)
            sr.start()
            cfg.search_relay_port = sr.port
            log('proxy', 'search relay listening on %s:%d -> xi_search %s:%d (query/reply translation %s)' % (
                cfg.listen_host, sr.port, cfg.lsb_host, cfg.lsb_search_port, 'on' if cfg.search_translate else 'off'))
        except OSError as e:
            log('proxy', 'WARNING: search relay not started (%s); the PS2 will talk to xi_search directly' % e)
    log('proxy', 'translations enabled: %s' % (', '.join(ENABLED_TRANSLATIONS) or 'none'))
    ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        ls.bind((cfg.listen_host, cfg.lobby_port))
    except OSError as e:
        raise SystemExit('cannot listen on TCP %s:%d (%s). Is LSB still using it? LSB\'s LOGIN_VIEW_PORT must be %d.'
                         % (cfg.listen_host, cfg.lobby_port, e, cfg.view_port))
    ls.listen(16)
    cfg.lobby_port = ls.getsockname()[1]
    log('proxy', 'ps2proxy %s: lobby listening on %s:%d -> LSB %s (auth %d, data %d, view %d)' % (
        VERSION, cfg.listen_host, cfg.lobby_port, cfg.lsb_host, cfg.auth_port, cfg.data_port, cfg.view_port))
    if ready:
        ready(cfg, relay)
    while True:
        try:
            cs, ca = ls.accept()
        except OSError as e:
            log('proxy', 'accept failed: %s' % e)
            time.sleep(0.5)
            continue
        if LobbySession.active >= MAX_LOBBY_SESSIONS:          # connection flood
            log('proxy', 'lobby connection from %s:%d refused: %d sessions open' % (ca[0], ca[1], LobbySession.active))
            try:
                cs.close()
            except OSError:
                pass
            continue
        LobbySession(cfg, log, relay, cs, ca).start()


def main(argv=None):
    cfg = parse_args(argv)
    log = Log(cfg.log, dump=cfg.dump, quiet=cfg.quiet, zone_trace=not cfg.no_zone_trace)
    signal.signal(signal.SIGTERM, lambda *a: (log('proxy', 'stopping (SIGTERM)'), os._exit(0)))
    if getattr(cfg, 'client', '2007') == '2012':
        cfg.client_defaults = _c12.apply_client(cfg, sys.modules[__name__], log)
    enable_optional_hooks(resolve_translations(cfg), log)
    try:
        serve(cfg, log)
    except KeyboardInterrupt:
        log('proxy', 'stopping (Ctrl-C)')


if __name__ == '__main__':
    main()
