#!/usr/bin/env python3
"""ps2proxy_chatrules (FFXI 2016 Server App, Fan Project by Habex) - chat rules for every player, in the PS2 login part.

Group "chat-rules" (off unless --translate chat-rules; put it after mp-tell-out and soc-mute):
  c2s 0x0B5 (say/shout/party/linkshell/yell) and 0x0B6 (tell) are checked before LandSandBoat gets them:
    - word filter: word lists from Server/data/chat_rules.json (case-insensitive; catches repeated letters, dots/spaces
      between letters and digit-for-letter swaps). Per list: replace with XXXX, warn (custom text), kick, kick then ban
      after N strikes, jail, notify the online moderators; several can be combined.
    - spam limit: at most N messages in M seconds and at most R identical messages in a row; penalty drop + warn,
      mute for X minutes, or kick.
  Every line is kept in the chat archive (Server/data/chat.db, table archive) and every rule hit in the hit log
  (table hits); old archive lines are removed after "archive_days" days.
  Scheduled messages (Server/data/scheduled.json) are sent by a small background thread while the proxy runs, and timed
  mutes (Server/data/mute_until.json) end on time.
  Actions inside the game (warn, kick, jail, messages) go through the map server's lan_appbridge queue file.
"""
import json, os, re, sqlite3, struct, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
DATA = os.environ.get('FFXI_DATA_DIR') or os.path.join(SERVER, 'data')
LSB = os.path.join(SERVER, 'lsb')
RULES_FILE = os.path.join(DATA, 'chat_rules.json')
SCHEDULE_FILE = os.path.join(DATA, 'scheduled.json')
MUTE_UNTIL = os.path.join(DATA, 'mute_until.json')
ROLES_FILE = os.path.join(DATA, 'roles.json')
DB_FILE = os.path.join(DATA, 'chat.db')
QUEUE = os.path.join(os.environ.get('FFXI_BRIDGE_DIR') or DATA, 'app_bridge.queue')   # where the map server reads app messages
ADMIN_LUA = os.path.join(SERVER, 'admin', 'ffxi_app_admin.lua')
MUTE_FILE = os.environ.get('PS2PROXY_MUTE_FILE') or os.path.join(DATA, 'muted.txt')

KINDS = {0: 'say', 1: 'shout', 4: 'party', 5: 'linkshell', 26: 'yell', 27: 'linkshell2', 3: 'tell'}
LEET = str.maketrans({'0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's', '7': 't', '8': 'b', '9': 'g', '@': 'a', '$': 's',
                      '!': 'i', '|': 'i', '+': 't', '€': 'e'})
_lock = threading.RLock()
_db = None
_rules = {'mtime': None, 'data': None, 'checked': 0.0}
_recent = {}            # player -> [(time, text)]


# ---------------------------------------------------------------- storage
def db():
    global _db
    with _lock:
        if _db is None:
            os.makedirs(DATA, exist_ok=True)
            _db = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=5)
            _db.executescript('''
              CREATE TABLE IF NOT EXISTS archive (id INTEGER PRIMARY KEY, ts REAL, player TEXT, channel TEXT, zone INTEGER, target TEXT, text TEXT);
              CREATE INDEX IF NOT EXISTS archive_player ON archive(player COLLATE NOCASE, ts);
              CREATE TABLE IF NOT EXISTS hits (id INTEGER PRIMARY KEY, ts REAL, player TEXT, channel TEXT, rule TEXT, text TEXT, actions TEXT);
              CREATE TABLE IF NOT EXISTS strikes (player TEXT, rule TEXT, count INTEGER, PRIMARY KEY (player, rule));
            ''')
            _db.commit()
        return _db


def _exec(sql, args=()):
    with _lock:
        c = db()
        cur = c.execute(sql, args)
        c.commit()
        return cur


def rules():
    now = time.time()
    if now - _rules['checked'] >= 2.0 or _rules['data'] is None:
        _rules['checked'] = now
        try:
            mt = os.path.getmtime(RULES_FILE)
        except OSError:
            mt = None
        if mt != _rules['mtime'] or _rules['data'] is None:
            data = {}
            if mt is not None:
                try:
                    with open(RULES_FILE, encoding='utf-8') as f:
                        data = json.load(f)
                except (OSError, ValueError):
                    data = _rules['data'] or {}
            _rules['mtime'], _rules['data'] = mt, data
    return _rules['data'] or {}


# ---------------------------------------------------------------- matching
def _canon(s):
    """lower case, digit/symbol swaps undone, letters only, repeated letters collapsed ("fuuu.ck" -> "fuck")."""
    s = s.lower().translate(LEET)
    s = re.sub(r'[^a-z]', '', s)
    return re.sub(r'(.)\1+', r'\1', s)


def find_words(text, words):
    """[(start, end)] spans of the original text that hold a listed word (with simple evasions)."""
    tokens = [(m.start(), m.end(), m.group()) for m in re.finditer(r'\S+', text)]
    canon_words = [(_canon(w), len(_canon(w))) for w in words if _canon(w)]
    spans = []
    for s, e, tok in tokens:
        c = _canon(tok)
        if not c:
            continue
        stem = re.sub(r'(ings?|ers?|ed|in|s|y|ish|head|face)$', '', c)
        for w, n in canon_words:
            # whole word, or a long word at the start / end of a longer one ("fucking", "motherfucker"), not in the
            # middle of an unrelated word ("Scunthorpe", "class")
            if c == w or stem == w or (n >= 4 and (c.startswith(w) or stem.endswith(w))):
                spans.append((s, e))
                break
    # letters split by spaces or dots: "f u c k", "f.u.c.k" (runs of one-letter tokens)
    run = []
    for s, e, tok in tokens + [(0, 0, '..')]:
        if len(_canon(tok)) == 1 and len(tok) <= 3:
            run.append((s, e, tok))
            continue
        if len(run) >= 3:
            joined = _canon(''.join(t for _, _, t in run))
            if any(w in joined for w, n in canon_words if n >= 3):
                spans.append((run[0][0], run[-1][1]))
        run = []
    return spans


def _mask(text, spans):
    out = list(text)
    for s, e in spans:
        for i in range(s, e):
            if not out[i].isspace():
                out[i] = 'X'
    return ''.join(out)


# ---------------------------------------------------------------- actions in the game (through the bridge)
def _lua_str(s):
    return '"' + ''.join(chr(b) if (chr(b).isascii() and chr(b).isalnum()) else '\\%03d' % b for b in str(s).encode('utf-8')) + '"'


def bridge(action, *args):
    vals = []
    for a in args:
        vals.append(str(a) if isinstance(a, int) and not isinstance(a, bool) else _lua_str(a))
    chunk = '(function() dofile(%s); return FFXIAPP.run(%s) end)()' % (
        _lua_str(ADMIN_LUA), ', '.join([_lua_str('cr%x' % int(time.time() * 1000 % 0xFFFFFF)), _lua_str(action)] + vals))
    try:
        with open(QUEUE, 'a', encoding='utf-8') as f:
            f.write(chunk + '\n')
    except OSError:
        pass


def moderators():
    """Characters whose role may manage chat rules (they get the notices)."""
    try:
        with open(ROLES_FILE, encoding='utf-8') as f:
            d = json.load(f)
    except (OSError, ValueError):
        return []
    roles = d.get('roles') or {}
    return [c for c, r in (d.get('members') or {}).items() if 'chatrules' in roles.get(r, [])]


def _mute(player, minutes):
    try:
        names = [l.split('#', 1)[0].strip() for l in open(MUTE_FILE, encoding='utf-8', errors='replace')] if os.path.exists(MUTE_FILE) else []
    except OSError:
        names = []
    names = [n for n in names if n]
    if player.lower() not in [n.lower() for n in names]:
        with open(MUTE_FILE, 'a', encoding='utf-8') as f:
            f.write(player + '\n')
    try:
        d = json.load(open(MUTE_UNTIL, encoding='utf-8')) if os.path.exists(MUTE_UNTIL) else {}
    except (OSError, ValueError):
        d = {}
    d[player] = time.time() + minutes * 60
    with open(MUTE_UNTIL, 'w', encoding='utf-8') as f:
        json.dump(d, f)


def _ban(player):
    try:
        import sys
        sys.path.insert(0, HERE)
        import lsb_db
        lsb_db.query('UPDATE accounts SET status = 2 WHERE id = (SELECT accid FROM chars WHERE charname = ?)', (player,))
    except Exception:                                        # noqa: BLE001
        pass


def act(ctx, player, channel, rule_name, text, actions, warn_text, strikes_needed):
    """Run the chosen actions; returns the list of what was done (for the hit log)."""
    done = []
    if 'warn' in actions:
        bridge('tell', player, (warn_text or 'Please keep the chat friendly.')[:200])
        done.append('warned')
    if 'kick_ban' in actions:
        with _lock:
            r = db().execute('SELECT count FROM strikes WHERE player = ? AND rule = ?', (player.lower(), rule_name)).fetchone()
            n = (r[0] if r else 0) + 1
            _exec('REPLACE INTO strikes (player, rule, count) VALUES (?, ?, ?)', (player.lower(), rule_name, n))
        if n >= max(1, int(strikes_needed or 3)):
            _ban(player)
            done.append('banned (strike %d)' % n)
        else:
            done.append('kicked (strike %d of %d)' % (n, int(strikes_needed or 3)))
        bridge('kick', player)
    elif 'kick' in actions:
        bridge('kick', player)
        done.append('kicked')
    if 'jail' in actions:
        bridge('jail', player, 1)
        done.append('jailed')
    if 'mute' in actions:
        _mute(player, int(actions_mute_minutes(rule_name)))
        done.append('muted')
    if 'notify' in actions:
        note = '[Chat rules] %s (%s): %s' % (player, channel, text[:120])
        for m in moderators():
            if m.lower() != player.lower():
                bridge('tell', m, note)
        done.append('mods notified')
    return done


def actions_mute_minutes(rule_name):
    sp = rules().get('spam') or {}
    return sp.get('mute_minutes', 5)


# ---------------------------------------------------------------- the hook
def _resize(pkt, n):
    n = (n + 3) & ~3
    p = bytearray(pkt[:n].ljust(n, b'\0'))
    struct.pack_into('<H', p, 0, (struct.unpack_from('<H', p, 0)[0] & 0x1FF) | ((n // 4) << 9))
    return bytes(p)


def _parse(pid, pkt):
    """(channel, target, text offset) for a chat packet."""
    if pid == 0x0B5:
        return KINDS.get(pkt[4], 'chat %d' % pkt[4]), '', 6
    if len(pkt) >= 0x16 and pkt[4] == 3 and pkt[5] == 0:     # LSB layout (after mp-tell-out)
        return 'tell', pkt[6:0x15].split(b'\0', 1)[0].decode('latin-1'), 0x15
    return 'tell', pkt[5:0x14].split(b'\0', 1)[0].decode('latin-1'), 0x14


def c2s_chat(ctx, pkt):
    player = getattr(getattr(ctx, 'ticket', None), 'name', None)
    if not player or len(pkt) < 7:
        return None
    pid = struct.unpack_from('<H', pkt, 0)[0] & 0x1FF
    try:
        channel, target, at = _parse(pid, pkt)
    except Exception:                                        # noqa: BLE001
        return None
    raw = pkt[at:].split(b'\0', 1)[0]
    text = raw.decode('latin-1')
    if not text:
        return None
    cfg = rules()
    now = time.time()
    try:
        _exec('INSERT INTO archive (ts, player, channel, zone, target, text) VALUES (?, ?, ?, ?, ?, ?)',
              (now, player, channel, getattr(ctx, '_cr_zone', None), target, text))
    except Exception:                                        # noqa: BLE001
        pass
    if text.startswith('!') or cfg.get('enabled') is False:
        return None
    # spam limit
    sp = cfg.get('spam') or {}
    if sp.get('on'):
        hist = [h for h in _recent.get(player, []) if now - h[0] < max(60, sp.get('per_seconds', 10))]
        hist.append((now, text))
        _recent[player] = hist
        n_recent = sum(1 for h in hist if now - h[0] <= sp.get('per_seconds', 10))
        same = 0
        for h in reversed(hist):
            if h[1].strip().lower() == text.strip().lower():
                same += 1
            else:
                break
        why = None
        if n_recent > int(sp.get('max_messages', 5)):
            why = 'too many messages (%d in %ds)' % (n_recent, sp.get('per_seconds', 10))
        elif same > int(sp.get('max_repeats', 3)):
            why = 'same message %d times' % same
        if why:
            acts = list(sp.get('actions') or ['drop', 'warn'])
            done = act(ctx, player, channel, 'Spam', text, acts, sp.get('warn_text') or 'Slow down please - you are sending messages too fast.', 0)
            _exec('INSERT INTO hits (ts, player, channel, rule, text, actions) VALUES (?, ?, ?, ?, ?, ?)',
                  (now, player, channel, 'Spam: ' + why, text, ', '.join((['dropped'] if 'drop' in acts or 'mute' in acts else []) + done)))
            ctx.log(ctx.tag, 'chat-rules: %s spam (%s)' % (player, why))
            if 'drop' in acts or 'mute' in acts or 'kick' in acts:
                return b''
    # word lists
    new_text = text
    for lst in cfg.get('lists') or []:
        if not lst.get('on', True):
            continue
        spans = find_words(new_text, lst.get('words') or [])
        if not spans:
            continue
        acts = list(lst.get('actions') or [])
        done = []
        if 'replace' in acts:
            new_text = _mask(new_text, spans)
            done.append('replaced')
        done += act(ctx, player, channel, lst.get('name', 'Words'), text, acts, lst.get('warn_text'), lst.get('strikes', 3))
        _exec('INSERT INTO hits (ts, player, channel, rule, text, actions) VALUES (?, ?, ?, ?, ?, ?)',
              (now, player, channel, lst.get('name', 'Words'), text, ', '.join(done) or 'logged'))
        ctx.log(ctx.tag, 'chat-rules: %s hit list "%s" (%s)' % (player, lst.get('name'), ', '.join(done)))
    if new_text != text:
        body = pkt[:at] + new_text.encode('latin-1', 'replace') + b'\0'
        return _resize(body, len(body))
    return None


def s2c_zone_in(ctx, pkt):
    """s2c 0x00A: remember the zone for the chat archive."""
    if len(pkt) >= 0x32:
        ctx._cr_zone = struct.unpack_from('<H', pkt, 0x30)[0]
    return None


# ---------------------------------------------------------------- scheduled messages, timed mutes, archive clean-up
def _housekeeping():
    last_clean = 0
    while True:
        try:
            now = time.time()
            # scheduled messages
            try:
                items = json.load(open(SCHEDULE_FILE, encoding='utf-8')) if os.path.exists(SCHEDULE_FILE) else []
            except (OSError, ValueError):
                items = None
            if items:
                changed = False
                for it in items:
                    if it.get('on', True) and it.get('next') and it['next'] <= now:
                        bridge('announce', ('*** %s ***' % it.get('text', ''))[:240])
                        it['last_sent'] = now
                        rep = float(it.get('repeat_minutes') or 0)
                        if rep > 0:
                            nxt = it['next']
                            while nxt <= now:
                                nxt += rep * 60
                            it['next'] = nxt
                        else:
                            it['on'] = False
                        changed = True
                if changed:
                    tmp = SCHEDULE_FILE + '.tmp'
                    with open(tmp, 'w', encoding='utf-8') as f:
                        json.dump(items, f, indent=1)
                    os.replace(tmp, SCHEDULE_FILE)
            # timed mutes
            try:
                d = json.load(open(MUTE_UNTIL, encoding='utf-8')) if os.path.exists(MUTE_UNTIL) else {}
            except (OSError, ValueError):
                d = {}
            over = [n for n, t in d.items() if t <= now]
            if over:
                names = [l.split('#', 1)[0].strip() for l in open(MUTE_FILE, encoding='utf-8', errors='replace')] if os.path.exists(MUTE_FILE) else []
                keep = [n for n in names if n and n.lower() not in [o.lower() for o in over]]
                with open(MUTE_FILE, 'w', encoding='utf-8') as f:
                    f.write('# Muted characters (FFXI Server App). One name per line.\n' + ''.join(n + '\n' for n in keep))
                for n in over:
                    d.pop(n, None)
                with open(MUTE_UNTIL, 'w', encoding='utf-8') as f:
                    json.dump(d, f)
            # archive clean-up once an hour
            if now - last_clean > 3600:
                days = float(rules().get('archive_days', 90) or 90)
                _exec('DELETE FROM archive WHERE ts < ?', (now - days * 86400,))
                _exec('DELETE FROM hits WHERE ts < ?', (now - 365 * 86400,))
                last_clean = now
        except Exception:                                    # noqa: BLE001
            pass
        time.sleep(10)


_started = False


def start_housekeeping():
    global _started
    if not _started:
        _started = True
        threading.Thread(target=_housekeeping, daemon=True, name='chat-rules').start()


GROUPS = {
    'chat-rules': ('word filter, spam limit, chat archive, scheduled messages (Server App > Chat rules)', [
        ('c2s', 0x0B5, c2s_chat), ('c2s', 0x0B6, c2s_chat), ('s2c', 0x00A, s2c_zone_in),
    ]),
}


def register(px):
    for name, (desc, items) in GROUPS.items():
        if name in px.OPTIONAL_HOOKS:
            continue
        for direction, pid, fn in items:
            (px.c2s_hook if direction == 'c2s' else px.s2c_hook)(pid, optional=name, desc=desc)(fn)
    start_housekeeping()
