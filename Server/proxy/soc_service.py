#!/usr/bin/env python3
"""soc_service.py - the LAN "PlayOnline friend service" for the 2016 PS2 host build (b49_social).

The 2016 FFXI program keeps its friend list in PlayOnline. There is no PlayOnline, so the host (work/b49_social/host/social.c) asks this
small TCP service instead. Friend lists and friend messages are stored here (SQLite file); who is online, where and as what job is read
from the LandSandBoat database (read-only: accounts, chars, char_stats, accounts_sessions, zone_settings, job names).

Protocol (one short TCP connection per exchange, ASCII lines, '\n'):
  client: HELLO <account> <md5hex(password)>        (password = 3rd comma field of players.txt, as for the lobby)
  client: zero or more commands, then SYNC
          ADD <charname>          send a friend request (pending until the other player accepts; kept across logouts)
          ACCEPT <charname>       accept a friend request -> both are on each other's list
          DECLINE <charname>      refuse a friend request
          DEL <charname>          remove a friend (both ways)
          MSG <charname> <text>   leave a message for that character's account (delivered on their next SYNC, even if offline now)
          LIST                    list friends as readable lines
  server: N <text>      a line for the chat log (answers, errors, delivered messages)
          F <accid> <online 0/1> <charid> <name> <zone> <mjob> <mlvl> <sjob> <slvl>   one per friend (for the friend list window)
          END
usage: soc_service.py [--port 54460] [--db FILE] [--players FILE] [--log FILE]
"""
import argparse, hashlib, os, re, socket, sqlite3, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'research', 'tools'))
JOBS = ['', 'WAR', 'MNK', 'WHM', 'BLM', 'RDM', 'THF', 'PLD', 'DRK', 'BST', 'BRD', 'RNG', 'SAM', 'NIN', 'DRG', 'SMN', 'BLU', 'COR', 'PUP',
        'DNC', 'SCH', 'GEO', 'RUN']
MAX_FRIENDS = 100
MUTE_FILE = os.environ.get('PS2PROXY_MUTE_FILE') or os.path.expanduser('~/Downloads/FFXI/Server/.tools/muted.txt')


def is_muted(name):
    """FFXI Server app mute list (same file the PS2 proxy uses): muted characters cannot leave friend messages either."""
    try:
        return name.lower() in {l.split('#', 1)[0].strip().lower() for l in open(MUTE_FILE, errors='replace')}
    except OSError:
        return False


class Lsb:
    """Read-only access to xidb (credentials from work/lsb/LOCAL_CREDENTIALS.txt through research/tools/lsb_db; never printed)."""
    def __init__(self, query=None):
        self._q = query
        self._conn = None
        self._lock = threading.Lock()

    def q(self, sql, args=()):
        if self._q:
            return self._q(sql, args)
        with self._lock:
            for attempt in (1, 2):
                try:
                    if self._conn is None:
                        import lsb_db
                        try:
                            import mariadb
                        except ImportError:                 # release: no extra Python modules needed
                            return lsb_db.query(sql, args)
                        c = lsb_db._creds()
                        self._conn = mariadb.connect(host=c['host'], port=int(c['port']), user=c['user'], password=c['password'], database=c['database'])
                        self._conn.autocommit = True
                    cur = self._conn.cursor()
                    cur.execute(sql, args)
                    rows = cur.fetchall() if cur.description else []
                    cur.close()
                    return rows
                except Exception:
                    self._conn = None
                    if attempt == 2:
                        raise

    def account_id(self, login):
        r = self.q('SELECT id FROM accounts WHERE login=?', (login,))
        return int(r[0][0]) if r else None

    def char_by_name(self, name):
        r = self.q('SELECT charid, accid, charname FROM chars WHERE LOWER(charname)=LOWER(?)', (name,))
        return (int(r[0][0]), int(r[0][1]), r[0][2]) if r else None

    def presence(self, accid, fallback_charid):
        """(online, charid, name, zone_id, zone_name, mjob, mlvl, sjob, slvl) for an account: the logged-in character, else fallback."""
        s = self.q('SELECT charid FROM accounts_sessions WHERE accid=? LIMIT 1', (accid,))
        online = bool(s)
        cid = int(s[0][0]) if s else fallback_charid
        if not cid:
            c = self.q('SELECT charid FROM chars WHERE accid=? ORDER BY charid LIMIT 1', (accid,))
            cid = int(c[0][0]) if c else 0
        r = self.q('SELECT c.charname, c.pos_zone, s.mjob, s.mlvl, s.sjob, s.slvl, IFNULL(z.name, "") FROM chars c LEFT JOIN char_stats s ON s.charid=c.charid '
                   'LEFT JOIN zone_settings z ON z.zoneid=c.pos_zone WHERE c.charid=?', (cid,))
        if not r:
            return (False, cid, '?', 0, '', 0, 0, 0, 0)
        n, z, mj, ml, sj, sl, zn = r[0]
        return (online, cid, n, int(z or 0), (zn or '').replace('_', ' '), int(mj or 0), int(ml or 0), int(sj or 0), int(sl or 0))


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()
        with self.lock:
            self.db.executescript('''
              CREATE TABLE IF NOT EXISTS friends (owner INTEGER, friend INTEGER, friend_char INTEGER, added REAL, PRIMARY KEY (owner, friend));
              CREATE TABLE IF NOT EXISTS requests (from_acc INTEGER, from_char INTEGER, to_acc INTEGER, created REAL, PRIMARY KEY (from_acc, to_acc));
              CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, to_acc INTEGER, from_name TEXT, text TEXT, created REAL, delivered REAL);
            ''')
            self.db.commit()

    def friends(self, owner):
        with self.lock:
            return self.db.execute('SELECT friend, friend_char FROM friends WHERE owner=? ORDER BY added', (owner,)).fetchall()

    def add(self, a, a_char, b, b_char):
        with self.lock:
            n = self.db.execute('SELECT COUNT(*) FROM friends WHERE owner=?', (a,)).fetchone()[0]
            if n >= MAX_FRIENDS:
                return False
            t = time.time()
            self.db.execute('INSERT OR REPLACE INTO friends VALUES (?,?,?,?)', (a, b, b_char, t))
            self.db.execute('INSERT OR IGNORE INTO friends VALUES (?,?,?,?)', (b, a, a_char, t))
            self.db.commit()
            return True

    def request(self, a, a_char, b):
        with self.lock:
            if self.db.execute('SELECT 1 FROM requests WHERE from_acc=? AND to_acc=?', (a, b)).fetchone():
                return False
            self.db.execute('INSERT INTO requests VALUES (?,?,?,?)', (a, a_char, b, time.time()))
            self.db.commit()
            return True

    def pending_from(self, frm, to):
        with self.lock:
            r = self.db.execute('SELECT from_char FROM requests WHERE from_acc=? AND to_acc=?', (frm, to)).fetchone()
            return r[0] if r else None

    def drop_request(self, frm, to):
        with self.lock:
            c = self.db.execute('DELETE FROM requests WHERE (from_acc=? AND to_acc=?) OR (from_acc=? AND to_acc=?)', (frm, to, to, frm)).rowcount
            self.db.commit()
            return c > 0

    def requests_to(self, to):
        with self.lock:
            return self.db.execute('SELECT from_acc, from_char FROM requests WHERE to_acc=? ORDER BY created', (to,)).fetchall()

    def delete(self, a, b):
        with self.lock:
            c = self.db.execute('DELETE FROM friends WHERE (owner=? AND friend=?) OR (owner=? AND friend=?)', (a, b, b, a)).rowcount
            self.db.commit()
            return c > 0

    def is_friend(self, a, b):
        with self.lock:
            return self.db.execute('SELECT 1 FROM friends WHERE owner=? AND friend=?', (a, b)).fetchone() is not None

    def post(self, to_acc, from_name, text):
        with self.lock:
            self.db.execute('INSERT INTO messages (to_acc, from_name, text, created) VALUES (?,?,?,?)', (to_acc, from_name, text, time.time()))
            self.db.commit()

    def take_messages(self, acc):
        with self.lock:
            rows = self.db.execute('SELECT id, from_name, text FROM messages WHERE to_acc=? AND delivered IS NULL ORDER BY id', (acc,)).fetchall()
            for r in rows:
                self.db.execute('UPDATE messages SET delivered=? WHERE id=?', (time.time(), r[0]))
            self.db.commit()
            return rows


def load_players(path):
    out = {}
    for line in open(path, encoding='utf-8', errors='replace'):
        if line.startswith('#') or line.count(',') < 2:
            continue
        f = line.rstrip('\n').split(',')
        out[f[1].strip()] = hashlib.md5(f[2].strip().encode()).hexdigest()
    return out


def clean(s, n):
    return re.sub(r'[^\x20-\x7e]', '?', s)[:n]


class Service:
    def __init__(self, store, lsb, players, log=None):
        self.store, self.lsb, self.players, self.logf = store, lsb, players, log

    def _fresh_players(self):
        """release: re-read players.txt when it changes (new profiles work without a restart)"""
        p = getattr(self, 'players_path', None)
        try:
            m = os.path.getmtime(p) if p else None
        except OSError:
            m = None
        if m and m != getattr(self, '_players_mtime', None):
            self._players_mtime = m
            self.players = load_players(p)
        return self.players

    def log(self, msg):
        if self.logf:
            with open(self.logf, 'a') as f:
                f.write('%s %s\n' % (time.strftime('%H:%M:%S'), msg))

    def my_char(self, acc):
        r = self.lsb.q('SELECT charid FROM accounts_sessions WHERE accid=? LIMIT 1', (acc,))
        return int(r[0][0]) if r else 0

    def handle(self, lines):
        """lines: the request lines (without '\n'); returns the reply lines (without '\n')."""
        out = []
        if not lines or not lines[0].startswith('HELLO '):
            return ['N Friend service: bad request.', 'END']
        p = lines[0].split()
        if len(p) != 3 or self._fresh_players().get(p[1]) != p[2].lower():
            self.log('auth failed for %r' % (p[1] if len(p) > 1 else ''))
            return ['N Friend service: login refused.', 'END']
        acct = p[1]
        me = self.lsb.account_id(acct)
        if me is None:
            return ['N Friend service: unknown account.', 'END']
        my_cid = self.my_char(me)
        me_name = self.lsb.presence(me, my_cid)[2]
        for line in lines[1:]:
            cmd, _, arg = line.partition(' ')
            arg = arg.strip()
            if cmd == 'ADD':
                c = self.lsb.char_by_name(arg)
                if not c:
                    out.append('N No character named %s.' % clean(arg, 16))
                elif c[1] == me:
                    out.append('N %s is one of your own characters.' % c[2])
                elif self.store.is_friend(me, c[1]):
                    out.append('N %s is already on your friend list.' % c[2])
                elif self.store.pending_from(c[1], me) is not None:      # they already asked us: adding back = accepting
                    out += self.accept(me, my_cid, me_name, c)
                elif len(self.store.friends(me)) >= MAX_FRIENDS:
                    out.append('N Your friend list is full.')
                elif self.store.request(me, my_cid, c[1]):
                    out.append('N Friend request sent to %s. They must accept it (/faccept %s).' % (c[2], me_name))
                    self.store.post(c[1], 'Friend service', '%s sent you a friend request: /faccept %s or /fdecline %s' % (me_name, me_name, me_name))
                    self.log('%s requested %s' % (acct, c[2]))
                else:
                    out.append('N You already sent %s a friend request.' % c[2])
            elif cmd in ('ACCEPT', 'DECLINE'):
                c = self.lsb.char_by_name(arg)
                if not c or self.store.pending_from(c[1], me) is None:
                    out.append('N No friend request from %s.' % (c[2] if c else clean(arg, 16)))
                elif cmd == 'ACCEPT':
                    out += self.accept(me, my_cid, me_name, c)
                else:
                    self.store.drop_request(c[1], me)
                    out.append('N You declined the friend request from %s.' % c[2])
                    self.store.post(c[1], 'Friend service', '%s declined your friend request.' % me_name)
                    self.log('%s declined %s' % (acct, c[2]))
            elif cmd == 'DEL':
                c = self.lsb.char_by_name(arg)
                if c and self.store.drop_request(me, c[1]) and not self.store.is_friend(me, c[1]):
                    out.append('N Friend request to/from %s cancelled.' % c[2])
                elif c and self.store.delete(me, c[1]):
                    out.append('N %s was removed from your friend list.' % c[2])
                    self.log('%s removed %s' % (acct, c[2]))
                else:
                    out.append('N %s is not on your friend list.' % clean(arg, 16))
            elif cmd == 'MSG':
                name, _, text = arg.partition(' ')
                c = self.lsb.char_by_name(name)
                if not c:
                    out.append('N No character named %s.' % clean(name, 16))
                elif not self.store.is_friend(me, c[1]):
                    out.append('N %s is not on your friend list.' % c[2])
                elif not text.strip():
                    out.append('N Usage: /fmsg <name> <message>')
                elif is_muted(me_name):
                    out.append('N You are muted by the server; the message was not sent.')
                else:
                    self.store.post(c[1], me_name, clean(text.strip(), 100))
                    out.append('N Message for %s saved.' % c[2])
            elif cmd == 'LIST':
                fl = self.store.friends(me)
                out.append('N Friends (%d):' % len(fl))
                for acc, fc in self.store.requests_to(me):
                    out.append('N  %s - wants to be your friend (/faccept or /fdecline)' % self.lsb.presence(acc, fc)[2])
                for acc, fc in fl:
                    on, cid, name, z, zn, mj, ml, sj, sl = self.lsb.presence(acc, fc)
                    if on:
                        job = '%s%d' % (JOBS[mj] if mj < len(JOBS) else '?', ml) + ('/%s%d' % (JOBS[sj] if sj < len(JOBS) else '?', sl) if sj else '')
                        out.append('N  %s - online - %s - %s' % (name, zn or ('zone %d' % z), job))
                    else:
                        out.append('N  %s - offline' % name)
            elif cmd == 'SYNC':
                for acc, fc in self.store.friends(me):
                    on, cid, name, z, zn, mj, ml, sj, sl = self.lsb.presence(acc, fc)
                    out.append('F %d %d %d %s %d %d %d %d %d' % (acc, 1 if on else 0, cid, clean(name, 15).replace(' ', '_'), z, mj, ml, sj, sl))
                for _, frm, text in self.store.take_messages(me):
                    out.append('N [Friend] %s: %s' % (clean(frm, 15), text) if frm != 'Friend service' else 'N [Friend] %s' % text)
        out.append('END')
        return out

    def accept(self, me, my_cid, me_name, c):
        frm_char = self.store.pending_from(c[1], me)
        if len(self.store.friends(me)) >= MAX_FRIENDS:
            return ['N Your friend list is full.']
        self.store.drop_request(c[1], me)
        self.store.add(me, my_cid, c[1], frm_char or c[0])
        self.store.post(c[1], 'Friend service', '%s accepted your friend request.' % me_name)
        self.log('%s accepted %s' % (me_name, c[2]))
        return ['N %s is now on your friend list.' % c[2]]


def serve(svc, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', port))
    s.listen(16)
    svc.log('listening on %d' % port)

    def one(c, a):
        try:
            c.settimeout(10)
            buf = b''
            while b'SYNC\n' not in buf and b'END\n' not in buf and len(buf) < 4096:
                d = c.recv(1024)
                if not d:
                    break
                buf += d
            lines = [l.decode('latin-1').rstrip('\r') for l in buf.split(b'\n') if l.strip()]
            reply = svc.handle(lines)
            c.sendall(('\n'.join(reply) + '\n').encode('latin-1', 'replace'))
        except Exception as e:                       # noqa: BLE001
            svc.log('%s: error %s' % (a[0], e))
        finally:
            c.close()
    while True:
        c, a = s.accept()
        threading.Thread(target=one, args=(c, a), daemon=True).start()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=54460)
    ap.add_argument('--db', default=os.path.join(HERE, 'social.db'))
    ap.add_argument('--players', default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'players.txt'))
    ap.add_argument('--log', default=os.path.join(HERE, 'soc_service.log'))
    a = ap.parse_args()
    svc = Service(Store(a.db), Lsb(), load_players(a.players), a.log)
    svc.players_path = a.players
    serve(svc, a.port)


if __name__ == '__main__':
    main()
