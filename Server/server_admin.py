#!/usr/bin/env python3
"""FFXI 2016 Release - live server info and admin actions for the Server App (Fan Project by Habex).

  - who is online (name, zone, job/level), every profile with its characters
  - world chat: new lines from the database's chat log (settings/map.lua AUDIT_CHAT is on)
  - messages and moderation: the app adds a Lua line to Server/lsb/app_bridge.queue; the map server's lan_appbridge
    module runs it (Server/admin/ffxi_app_admin.lua) and prints the answer into Server/data/logs/xi_map.log.
Python standard library only; works the same on Mac, Windows and Linux.
"""
import os, re, secrets, threading, time

import server_control as sc

ADMIN_LUA = os.path.join(sc.SERVER, 'admin', 'ffxi_app_admin.lua')
def _bridge(name):
    return os.path.join(sc.map_files_dir(), name)
ADMIN_LOG = os.path.join(sc.LOGS, 'admin_actions.log')

JOBS = ['---', 'WAR', 'MNK', 'WHM', 'BLM', 'RDM', 'THF', 'PLD', 'DRK', 'BST', 'BRD', 'RNG', 'SAM', 'NIN', 'DRG', 'SMN',
        'BLU', 'COR', 'PUP', 'DNC', 'SCH', 'GEO', 'RUN']
CHAT_TYPES = {'SAY': 'Say', 'SHOUT': 'Shout', 'YELL': 'Yell', 'TELL': 'Tell', 'PARTY': 'Party', 'LINKSHELL': 'LS',
              'UNITY': 'Unity', 'ASSISTE': 'Assist', 'ASSISTJ': 'Assist'}


def nice_zone(name):
    if not name:
        return '?'
    return name.replace('_', ' ').replace(' dOria', " d'Oria").replace('Ru Lude', "Ru'Lude").replace('Rulude', "Ru'Lude")


def _int(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def job_text(mj, ml, sj, sl):
    mj, sj = _int(mj), _int(sj)
    t = '%s%s' % (JOBS[mj] if 0 <= mj < len(JOBS) else '?', _int(ml) or '')
    if 0 < sj < len(JOBS):
        t += '/%s%s' % (JOBS[sj], _int(sl) or '')
    return t


def q(sql, args=()):
    return sc.sql(sql, args)


# ---------------------------------------------------------------- reading
def online_players():
    """[{'name','account','zone','job','state','gm'}] of everyone in the game now."""
    rows = q('SELECT c.charname, a.login, z.name, st.mjob, st.mlvl, st.sjob, st.slvl, st.zoning, c.settings, c.gmlevel '
             'FROM accounts_sessions ses JOIN chars c ON c.charid = ses.charid JOIN accounts a ON a.id = ses.accid '
             'LEFT JOIN char_stats st ON st.charid = c.charid LEFT JOIN zone_settings z ON z.zoneid = c.pos_zone '
             'ORDER BY c.charname')
    out = []
    for name, acc, zname, mj, ml, sj, sl, zoning, settings, gm in rows:
        state = 'Zoning' if _int(zoning) else ('AFK' if _int(settings) & 2 else 'Online')
        out.append(dict(name=name, account=acc, zone=nice_zone(zname), job=job_text(mj, ml, sj, sl), state=state, gm=_int(gm)))
    return out


def profiles():
    """[{'login','banned','online','created','chars':[{'name','job','zone','online','gm'}]}]"""
    accs = {}
    for aid, login, status, created in q('SELECT id, login, status, timecreate FROM accounts ORDER BY login'):
        st = _int(status)
        accs[_int(aid)] = dict(login=login, banned=not (st & 1) or bool(st & 2), online=False, created=str(created or '')[:10], chars=[])
    for accid, name, mj, ml, sj, sl, zname, gm, online in q(
            'SELECT c.accid, c.charname, st.mjob, st.mlvl, st.sjob, st.slvl, z.name, c.gmlevel, (ses.charid IS NOT NULL) '
            'FROM chars c LEFT JOIN char_stats st ON st.charid = c.charid LEFT JOIN zone_settings z ON z.zoneid = c.pos_zone '
            'LEFT JOIN accounts_sessions ses ON ses.charid = c.charid ORDER BY c.charname'):
        a = accs.get(_int(accid))
        if a is None:
            continue
        on = bool(_int(online))
        a['chars'].append(dict(name=name, job=job_text(mj, ml, sj, sl), zone=nice_zone(zname), online=on, gm=_int(gm)))
        a['online'] = a['online'] or on
    return list(accs.values())


class ChatReader:
    """New in-game chat lines from the audit_chat table. The first call only remembers where 'now' is."""

    def __init__(self):
        self.last = None

    def new_lines(self):
        if self.last is None:
            r = q('SELECT IFNULL(MAX(lineID), 0) FROM audit_chat')
            self.last = _int(r[0][0]) if r else 0
            back = max(0, self.last - 30)                     # show the last few lines when the app opens
            rows = q('SELECT lineID, speaker, type, lsName, recipient, REPLACE(REPLACE(REPLACE(CAST(message AS CHAR CHARACTER SET latin1), CHAR(9), CHAR(32)), CHAR(10), CHAR(32)), CHAR(13), CHAR(32)) FROM audit_chat WHERE lineID > ? ORDER BY lineID', (back,))
        else:
            rows = q('SELECT lineID, speaker, type, lsName, recipient, REPLACE(REPLACE(REPLACE(CAST(message AS CHAR CHARACTER SET latin1), CHAR(9), CHAR(32)), CHAR(10), CHAR(32)), CHAR(13), CHAR(32)) FROM audit_chat WHERE lineID > ? ORDER BY lineID LIMIT 200',
                     (self.last,))
        out = []
        for lid, spk, typ, ls, rcp, msg in rows:
            self.last = max(self.last, _int(lid))
            msg = ''.join(ch for ch in str(msg or '') if ch >= ' ' or ch == '\t')
            extra = ('to %s' % rcp) if rcp else (ls or '')
            out.append((CHAT_TYPES.get(str(typ).upper(), str(typ).title()), str(spk), msg, extra))
        return out


# ---------------------------------------------------------------- talking to the map server
def lua_str(s):
    """A Lua string literal with every byte that is not a letter or digit written as a decimal escape."""
    return '"' + ''.join(chr(b) if (chr(b).isascii() and chr(b).isalnum()) else '\\%03d' % b for b in str(s).encode('utf-8')) + '"'


def lua_val(v):
    if v is None:
        return 'nil'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(round(v, 3))
    return lua_str(v)


_lock = threading.Lock()


def bridge_ok():
    """The map server's message link answered in the last 90 seconds."""
    try:
        return sc.is_running('xi_map') and time.time() - os.path.getmtime(_bridge('app_bridge.alive')) < 90
    except OSError:
        return False


def call(action, *args, timeout=15):
    """Run one admin action inside the map server. Returns (ok, text)."""
    if not sc.is_running('xi_map'):
        return False, 'the server is off'
    tag = secrets.token_hex(4)
    logp = os.path.join(sc.LOGS, 'xi_map.log')
    chunk = '(function() dofile(%s); return FFXIAPP.run(%s) end)()' % (
        lua_str(ADMIN_LUA), ', '.join([lua_str(tag), lua_str(action)] + [lua_val(a) for a in args]))
    with _lock:
        start = os.path.getsize(logp) if os.path.exists(logp) else 0
        with open(_bridge('app_bridge.queue'), 'a', encoding='utf-8') as f:
            f.write(chunk + '\n')
        needle = ('[FFXIAPP %s] ' % tag).encode()
        end = time.time() + timeout
        while time.time() < end:
            time.sleep(0.2)
            try:
                with open(logp, 'rb') as f:
                    f.seek(start)
                    data = f.read()
            except OSError:
                continue
            i = data.find(needle)
            if i >= 0:
                rest = data[i + len(needle):].split(b'\n', 1)[0].decode('utf-8', 'replace')
                rest = re.sub(r'\s*\(lua_print:\d+\)\s*$', '', rest).strip()
                st, _, text = rest.partition(' ')
                return st == 'ok', text.strip()
    return False, 'no answer from the map server yet (it checks for messages every few seconds; try again)'


def audit(line, result):
    try:
        os.makedirs(sc.LOGS, exist_ok=True)
        with open(ADMIN_LOG, 'a', encoding='utf-8') as f:
            f.write('%s  %s  ->  %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), ' '.join(line.split()), ' '.join(str(result).split())[:500]))
    except OSError:
        pass


class AdminError(Exception):
    pass


def _char(name):
    r = q('SELECT c.charid, c.charname, c.gmlevel, (s.charid IS NOT NULL) FROM chars c LEFT JOIN accounts_sessions s '
          'ON s.charid = c.charid WHERE LOWER(c.charname) = LOWER(?)', (name,))
    if not r:
        raise AdminError('There is no character called "%s".' % name)
    cid, cname, gm, online = r[0]
    return _int(cid), cname, _int(gm), bool(_int(online))


def _lua(action, *args):
    ok, text = call(action, *args)
    if not ok and text == 'offline':
        raise AdminError('That player is not in the game right now.')
    if not ok:
        raise AdminError(text)
    return text


def find_item(text):
    t = text.strip().strip('"\'')
    if re.fullmatch(r'\d+', t):
        r = q('SELECT itemid, name FROM item_basic WHERE itemid = ?', (int(t),))
        if not r:
            raise AdminError('There is no item number %s.' % t)
        return _int(r[0][0]), r[0][1]
    key = re.sub(r'\s+', '_', t.lower())
    r = q('SELECT itemid, name FROM item_basic WHERE LOWER(name) = ? OR LOWER(sortname) = ?', (key, key))
    if len(r) >= 1:
        return _int(r[0][0]), r[0][1]
    like = key.replace('\\', '').replace('%', '') + '%'
    r = q('SELECT itemid, name FROM item_basic WHERE LOWER(name) LIKE ? ORDER BY LENGTH(name) LIMIT 8', (like,))
    if len(r) == 1:
        return _int(r[0][0]), r[0][1]
    if r:
        raise AdminError('"%s" could mean: %s. Type the exact name or the number.' % (t, ', '.join('%s (%s)' % (x[1].replace('_', ' '), x[0]) for x in r)))
    raise AdminError('No item called "%s".' % t)


def find_zone(text):
    t = text.strip()
    rows = q('SELECT zoneid, name FROM zone_settings')
    if re.fullmatch(r'\d+', t):
        hit = [r for r in rows if _int(r[0]) == int(t)]
    else:
        key = re.sub(r"[\s'_-]+", '', t.lower())
        hit = [r for r in rows if re.sub(r"[\s'_-]+", '', str(r[1]).lower()) == key] or \
              [r for r in rows if key and key in re.sub(r"[\s'_-]+", '', str(r[1]).lower())]
        if len(hit) > 1 and not [r for r in hit if re.sub(r"[\s'_-]+", '', str(r[1]).lower()) == key]:
            raise AdminError('"%s" could mean: %s.' % (t, ', '.join(nice_zone(r[1]) for r in hit[:8])))
    if not hit:
        raise AdminError('No zone called "%s".' % t)
    return _int(hit[0][0]), hit[0][1]


def muted():
    try:
        return [l.split('#', 1)[0].strip() for l in open(sc.MUTED, encoding='utf-8', errors='replace') if l.split('#', 1)[0].strip()]
    except OSError:
        return []


def _write_muted(names):
    tmp = sc.MUTED + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write('# Muted characters (FFXI Server App): their chat is not passed on. One name per line.\n')
        f.write(''.join(n + '\n' for n in names))
    os.replace(tmp, sc.MUTED)


# ---------------------------------------------------------------- chat box commands
# name -> (arguments for autocomplete, what it does). Argument kinds: player, dest (zone or player), item, job, num, text
COMMANDS = {
    'help':     ([], 'list the commands'),
    'announce': (['text'], 'a highlighted message to everyone'),
    'who':      ([], 'who is in the game'),
    'tell':     (['player', 'text'], 'a private message from Server'),
    'kick':     (['player'], 'log a player out'),
    'ban':      (['player', 'text'], 'ban the profile (and log out), optional reason'),
    'unban':    (['player'], 'let a banned profile sign in again'),
    'mute':     (['player', 'num'], 'hide their chat, optional minutes'),
    'unmute':   (['player'], 'let them chat again'),
    'muted':    ([], 'who is muted'),
    'jail':     (['player'], 'send to the GM jail (Mordion Gaol)'),
    'unjail':   (['player'], 'out of jail, to their home point'),
    'tp':       (['player', 'dest'], 'move a player to a zone or to another player'),
    'summon':   (['player', 'player'], 'bring a player next to another player'),
    'home':     (['player'], 'send to their home point'),
    'give':     (['player', 'item', 'num'], 'give an item, optional amount'),
    'gil':      (['player', 'num'], 'give gil'),
    'level':    (['player', 'num'], 'set their level (1-99)'),
    'job':      (['player', 'job', 'num'], 'change job, optional level'),
    'heal':     (['player'], 'full HP and MP'),
    'hp':       (['player'], 'full HP and MP (same as /heal)'),
    'kill':     (['player'], 'knock them out'),
    'revive':   (['player'], 'offer a raise to a KO player'),
    'release':  (['player'], 'free from a stuck cutscene'),
    'promote':  (['player', 'role'], 'give a player a role (Roles decide their in-game commands)'),
    'demote':   (['player'], 'take their role away'),
    'clear':    ([], 'clear the chat box'),
}
JOB_NAMES = {'WAR': 'Warrior', 'MNK': 'Monk', 'WHM': 'White Mage', 'BLM': 'Black Mage', 'RDM': 'Red Mage', 'THF': 'Thief',
             'PLD': 'Paladin', 'DRK': 'Dark Knight', 'BST': 'Beastmaster', 'BRD': 'Bard', 'RNG': 'Ranger', 'SAM': 'Samurai',
             'NIN': 'Ninja', 'DRG': 'Dragoon', 'SMN': 'Summoner', 'BLU': 'Blue Mage', 'COR': 'Corsair', 'PUP': 'Puppetmaster',
             'DNC': 'Dancer', 'SCH': 'Scholar', 'GEO': 'Geomancer', 'RUN': 'Rune Fencer'}
USAGE = {'announce': '<text>', 'tell': '<player> <text>', 'ban': '<player> [reason]', 'mute': '<player> [minutes]',
         'tp': '<player> <zone or player>', 'summon': '<player> <to player>', 'give': '<player> <item> [amount]',
         'gil': '<player> <amount>', 'level': '<player> <1-99>', 'job': '<player> <job> [level]', 'promote': '<player> <role>'}
for _k, _v in COMMANDS.items():
    USAGE.setdefault(_k, '<player>' if _v[0] and _v[0][0] == 'player' else '')
MIN_ARGS = {'tell': 2, 'tp': 2, 'summon': 2, 'give': 2, 'gil': 2, 'level': 2, 'job': 2, 'promote': 2}
HELP = 'Commands (player names are not case-sensitive; @Name works too):\n' + '\n'.join(
    '  /%-9s %-26s %s' % (k, USAGE[k], v[1]) for k, v in COMMANDS.items()) + '\nA line without "/" is a message to everyone.'


def _norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


_zones = None


def zones():
    """[(zoneid, readable name)] of every zone, e.g. "Lower Jeuno", "Southern San d'Oria [S]"."""
    global _zones
    if _zones is None:
        _zones = [(_int(z), nice_zone(n).replace(' [', ' [')) for z, n in q('SELECT zoneid, name FROM zone_settings WHERE zoneid > 0 ORDER BY name')
                  if n and n != 'unknown']
    return _zones


def match_zones(text, limit=10):
    """Zones whose readable name fits what was typed (case and spaces/apostrophes ignored; every word may be a prefix)."""
    k = _norm(text)
    words = [_norm(w) for w in text.split() if _norm(w)]
    exact, start, inside = [], [], []
    for zid, name in zones():
        n = _norm(name)
        if n == k:
            exact.append((zid, name))
        elif n.startswith(k):
            start.append((zid, name))
        elif k and (k in n or all(any(p.startswith(w) for p in re.findall(r'[a-z0-9]+', name.lower().replace("'", ''))) for w in words)):
            inside.append((zid, name))
    return (exact + sorted(start, key=lambda z: len(z[1])) + sorted(inside, key=lambda z: len(z[1])))[:limit]


_entrances = None


def zone_entrance(zid, name):
    """(x, y, z, rot) where a player arrives in the zone (a zone line leading into it), or None."""
    global _entrances
    if _entrances is None:
        _entrances = {}
        base = os.path.join(sc.LSB, 'data', 'zones')
        try:
            folders = os.listdir(base)
        except OSError:
            folders = []
        for d in folders:
            try:
                txt = open(os.path.join(base, d, 'zone.yaml'), encoding='utf-8').read()
            except OSError:
                continue
            for to, at in re.findall(r'to:\s*(\S+)\s*\n\s*at:\s*\[([^\]]+)\]', txt):
                try:
                    v = [float(x) for x in at.split(',')]
                except ValueError:
                    continue
                if len(v) >= 3 and _norm(to) not in _entrances:
                    rot = int((v[3] if len(v) > 3 else 0) / (2 * 3.14159265) * 256) % 256
                    _entrances[_norm(to)] = (v[0], v[1], v[2], rot)
    return _entrances.get(_norm(name.replace("'", '')))


def match_items(text, limit=12):
    """[(itemid, readable name)] for item autocomplete."""
    t = text.strip().lower()
    if len(t) < 2:
        return []
    key = re.sub(r'[\s\-]+', '_', t).replace("'", '').replace('\\', '').replace('%', '')
    rows = q("SELECT itemid, name FROM item_basic WHERE LOWER(name) LIKE ? OR LOWER(sortname) LIKE ? ORDER BY (LOWER(name) LIKE ?) DESC, "
             "LENGTH(name) LIMIT %d" % limit, (key + '%', '%' + key + '%', key + '%'))
    return [(_int(i), n.replace('_', ' ')) for i, n in rows]


def char_names():
    """(online names, all character names)."""
    on = [r[0] for r in q('SELECT c.charname FROM accounts_sessions s JOIN chars c ON c.charid = s.charid ORDER BY c.charname')]
    allc = [r[0] for r in q('SELECT charname FROM chars ORDER BY charname')]
    return on, allc


MUTE_UNTIL = os.path.join(sc.DATA, 'mute_until.json')


def _mute_times():
    try:
        import json
        with open(MUTE_UNTIL, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_mute_times(d):
    import json
    with open(MUTE_UNTIL, 'w', encoding='utf-8') as f:
        json.dump(d, f)


def expire_mutes():
    """Unmute players whose mute time is over. Returns their names."""
    d = _mute_times()
    now = time.time()
    done = [n for n, until in d.items() if until <= now]
    if done:
        _write_muted([m for m in muted() if m.lower() not in [x.lower() for x in done]])
        for n in done:
            d.pop(n, None)
            audit('(mute time over) ' + n, 'unmuted')
        _save_mute_times(d)
    return done


def command(line, sender='Server'):
    """Turn a line typed in the chat box into an action. Returns (ok, plain text)."""
    line = line.strip()
    if not line:
        return True, ''
    try:
        res = _command(line, sender)
        if line.lower() not in ('/help', '/who', '/muted'):
            audit(line, res)
        return True, res
    except AdminError as e:
        audit(line, 'error: %s' % e)
        return False, str(e)
    except Exception as e:                                    # noqa: BLE001
        audit(line, 'error: %s' % e)
        return False, 'That did not work: %s' % e


def _player(word):
    word = word.lstrip('@')
    r = q('SELECT c.charid, c.charname, c.gmlevel, (s.charid IS NOT NULL) FROM chars c LEFT JOIN accounts_sessions s '
          'ON s.charid = c.charid WHERE LOWER(c.charname) = LOWER(?)', (word,))
    if not r:
        raise AdminError('No player called %s.' % word)
    cid, cname, gm, online = r[0]
    return _int(cid), cname, _int(gm), bool(_int(online))


def _need_online(cname, online):
    if not online:
        raise AdminError('%s is not in the game right now.' % cname)


def _do(action, *args):
    ok, text = call(action, *args)
    if not ok and text == 'offline':
        raise AdminError('That player is not in the game right now (or is changing zones, try again).')
    if not ok:
        raise AdminError(text[:1].upper() + text[1:] + ('' if text.endswith('.') else '.'))
    return text


def _command(line, sender):
    if not line.startswith('/'):
        if not sc.is_running('xi_map'):
            raise AdminError('The server is off, so the message was not sent.')
        if not online_players():
            raise AdminError('Nobody is online, so the message was not sent.')
        _do('broadcast', ('%s: %s' % (sender, line))[:240])
        return 'Sent to everyone online.'
    cmd, _, rest = line[1:].partition(' ')
    cmd = cmd.lower()
    rest = rest.strip()
    args = rest.split()
    if cmd not in COMMANDS:
        raise AdminError('There is no command /%s. Type / to see the list.' % cmd)
    if cmd == 'help':
        return HELP
    if cmd == 'who':
        p = online_players()
        return 'In the game (%d): %s' % (len(p), ', '.join('%s (%s, %s)' % (x['name'], x['zone'], x['job']) for x in p) or 'nobody')
    if cmd == 'muted':
        times = _mute_times()
        m = muted()
        return 'Muted: ' + (', '.join(n + (' (%d min left)' % max(1, int((times[n] - time.time()) / 60)) if n in times else '') for n in m) or 'nobody')
    if cmd == 'announce':
        if not rest:
            raise AdminError('Type the message after /announce.')
        _do('announce', ('*** %s ***' % rest)[:240])
        return 'Announcement sent: %s' % rest
    need = MIN_ARGS.get(cmd, 1 if USAGE[cmd].startswith('<player>') else 0)
    if len(args) < need:
        raise AdminError('Not enough words. Use: /%s %s' % (cmd, USAGE[cmd]))
    if cmd in ('ban', 'unban'):
        word = args[0].lstrip('@')
        r = q('SELECT a.login FROM chars c JOIN accounts a ON a.id = c.accid WHERE LOWER(c.charname) = LOWER(?)', (word,)) or \
            q('SELECT login FROM accounts WHERE LOWER(login) = LOWER(?)', (word,))
        if not r:
            raise AdminError('No player or profile called %s.' % word)
        login = r[0][0]
        sc.set_profile_enabled(login, cmd == 'unban')
        if cmd == 'unban':
            return 'Unbanned %s. They can sign in again.' % login
        kicked = []
        for (cname,) in q('SELECT c.charname FROM accounts_sessions s JOIN chars c ON c.charid = s.charid JOIN accounts a '
                          'ON a.id = s.accid WHERE a.login = ?', (login,)):
            try:
                _do('kick', cname)
                kicked.append(cname)
            except AdminError:
                pass
        reason = rest.split(None, 1)[1] if len(args) > 1 else ''
        return 'Banned %s%s%s.' % (login, ' (logged out %s)' % ', '.join(kicked) if kicked else '', ', reason: ' + reason if reason else '')
    cid, cname, gm, online = _player(args[0])
    if cmd == 'tell':
        _need_online(cname, online)
        s = re.sub(r'[^A-Za-z0-9]', '', sender)[:15] or 'Server'
        _do('whisper', cname, rest.split(None, 1)[1][:200], s)
        return 'Told %s: %s' % (cname, rest.split(None, 1)[1])
    if cmd == 'kick':
        _need_online(cname, online)
        _do('kick', cname)
        return 'Logged out %s.' % cname
    if cmd == 'mute':
        mins = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0
        if cname.lower() not in [n.lower() for n in muted()]:
            _write_muted(muted() + [cname])
        d = _mute_times()
        d.pop(cname, None)
        if mins:
            d[cname] = time.time() + mins * 60
        _save_mute_times(d)
        if online:
            try:
                _do('mutenote', cname, True)
            except AdminError:
                pass
        return 'Muted %s%s.' % (cname, ' for %d minute%s' % (mins, '' if mins == 1 else 's') if mins else '')
    if cmd == 'unmute':
        _write_muted([n for n in muted() if n.lower() != cname.lower()])
        d = _mute_times()
        d.pop(cname, None)
        _save_mute_times(d)
        if online:
            try:
                _do('mutenote', cname, False)
            except AdminError:
                pass
        return 'Unmuted %s.' % cname
    if cmd == 'jail':
        if gm:
            raise AdminError('%s is a GM. Set /gm %s 0 first.' % (cname, cname))
        _do('jail', cname, 1)
        return 'Sent %s to jail%s.' % (cname, '' if online else ' (they start there next time)')
    if cmd == 'unjail':
        if online:
            _do('unjail', cname)
        else:
            q("DELETE FROM char_vars WHERE charid = ? AND varname = 'inJail'", (cid,))
            q('UPDATE chars SET pos_prevzone = pos_zone, pos_zone = home_zone, pos_x = home_x, pos_y = home_y, pos_z = home_z, '
              'pos_rot = home_rot, moghouse = 0 WHERE charid = ? AND pos_zone = 131', (cid,))
        return 'Let %s out of jail.' % cname
    if cmd in ('tp', 'summon'):
        dest = rest.split(None, 1)[1].strip().lstrip('@')
        hit = q('SELECT charname FROM chars WHERE LOWER(charname) = LOWER(?)', (dest,))
        if hit or cmd == 'summon':
            if not hit:
                raise AdminError('No player called %s.' % dest)
            _, tname, _, t_on = _player(hit[0][0])
            _need_online(cname, online)
            _need_online(tname, t_on)
            _do('bring', cname, tname)
            return 'Moved %s to %s.' % (cname, tname)
        z = match_zones(dest, 2)
        if not z:
            raise AdminError('No zone called %s.' % dest)
        if len(z) > 1 and _norm(z[0][1]) != _norm(dest):
            more = match_zones(dest, 6)
            if len(more) > 1:
                raise AdminError('"%s" could be: %s. Type more of the name.' % (dest, ', '.join(m[1] for m in more)))
        zid, zname = z[0]
        pos = zone_entrance(zid, zname) or (0.0, 0.0, 0.0, 0)
        if online:
            _do('zone', cname, zid, float(pos[0]), float(pos[1]), float(pos[2]), int(pos[3]))
            return 'Moved %s to %s.' % (cname, zname)
        q('UPDATE chars SET pos_prevzone = pos_zone, pos_zone = ?, pos_x = ?, pos_y = ?, pos_z = ?, pos_rot = ?, moghouse = 0 '
          'WHERE charid = ?', (zid, pos[0], pos[1], pos[2], pos[3], cid))
        return '%s is offline. They will start in %s next time.' % (cname, zname)
    if cmd == 'home':
        if online:
            _do('home', cname)
            return 'Sent %s to their home point.' % cname
        q('UPDATE chars SET pos_prevzone = pos_zone, pos_zone = home_zone, pos_x = home_x, pos_y = home_y, pos_z = home_z, '
          'pos_rot = home_rot, moghouse = 0 WHERE charid = ?', (cid,))
        return '%s is offline. They will start at their home point next time.' % cname
    if cmd == 'give':
        words, qty = rest.split(None, 1)[1].split(), 1
        if len(words) > 1 and re.fullmatch(r'x?\d+', words[-1].lower()):
            qty, words = int(words[-1].lower().lstrip('x')), words[:-1]
        qty = max(1, min(qty, 99))
        iid, iname = find_item(' '.join(words))
        nice = iname.replace('_', ' ')
        res = _do('give' if online else 'deliver', cname, iid, qty)
        where = ' (inventory full, it is in their delivery box)' if 'delivery' in res and online else \
                ' (offline, it is in their delivery box)' if not online else ''
        return 'Gave %s %s x%d%s.' % (cname, nice, qty, where)
    if cmd == 'gil':
        _need_online(cname, online)
        if not re.fullmatch(r'\d{1,9}', args[1]):
            raise AdminError('The amount must be a number, e.g. /gil %s 5000' % cname)
        res = _do('gil', cname, int(args[1]))
        return 'Gave %s %s gil (%s).' % (cname, args[1], res.split(' now has ')[-1] + ' total' if ' now has ' in res else res)
    if cmd == 'level':
        _need_online(cname, online)
        if not re.fullmatch(r'\d{1,2}', args[1]) or not 1 <= int(args[1]) <= 99:
            raise AdminError('The level must be 1 to 99.')
        _do('level', cname, int(args[1]))
        return 'Set %s to level %s.' % (cname, args[1])
    if cmd == 'job':
        _need_online(cname, online)
        j = args[1].upper()
        if j not in JOB_NAMES:
            hit = [k for k, v in JOB_NAMES.items() if _norm(v).startswith(_norm(args[1]))]
            if len(hit) != 1:
                raise AdminError('No job called %s. Use WAR, MNK, WHM, BLM, RDM, THF, PLD, DRK, BST, BRD, RNG, SAM, NIN, DRG, SMN, BLU, COR, PUP, DNC, SCH, GEO or RUN.' % args[1])
            j = hit[0]
        lvl = int(args[2]) if len(args) > 2 and args[2].isdigit() and 1 <= int(args[2]) <= 99 else None
        _do('job', cname, JOBS.index(j), lvl)
        return 'Changed %s to %s%s.' % (cname, JOB_NAMES[j], ' level %d' % lvl if lvl else '')
    if cmd in ('heal', 'hp'):
        _need_online(cname, online)
        res = _do('heal', cname)
        return 'Offered %s a raise (they were KO).' % cname if 'raise' in res else 'Healed %s.' % cname
    if cmd == 'kill':
        _need_online(cname, online)
        _do('kill', cname)
        return 'Knocked out %s.' % cname
    if cmd == 'revive':
        _need_online(cname, online)
        _do('revive', cname)
        return 'Offered %s a raise.' % cname
    if cmd == 'release':
        _need_online(cname, online)
        _do('release', cname)
        return 'Freed %s from the cutscene.' % cname
    if cmd in ('promote', 'demote'):
        import server_roles as sr
        if cmd == 'demote':
            had = sr.demote(cname)
            return ('Took the role away from %s.' % cname) if had else '%s had no role.' % cname
        want = rest.split(None, 1)[1].strip()
        roles = list(sr.load()['roles'])
        hit = [r for r in roles if r.lower() == want.lower()] or [r for r in roles if r.lower().startswith(want.lower())]
        if len(hit) != 1:
            raise AdminError('No role called "%s". Roles: %s.' % (want, ', '.join(roles) or 'none yet (make one with the Roles button)'))
        sr.promote(cname, hit[0])
        return 'Promoted %s to %s.' % (cname, hit[0])
    if cmd == 'clear':
        return ''
    raise AdminError('There is no command /%s.' % cmd)
