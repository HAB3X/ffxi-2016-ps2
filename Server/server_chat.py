#!/usr/bin/env python3
"""FFXI 2016 Release - chat rules, scheduled messages and the chat archive, for the Server App (Fan Project by Habex).

The rules themselves run in the PS2 login part (Server/proxy/ps2proxy_chatrules.py) so they apply to every player.
This file only reads and writes the settings (Server/data/chat_rules.json, scheduled.json) and reads the archive and
the hit log (Server/data/chat.db). Python standard library only.
"""
import json, os, sqlite3, time, uuid

import server_control as sc

RULES_FILE = os.path.join(sc.DATA, 'chat_rules.json')
SCHEDULE_FILE = os.path.join(sc.DATA, 'scheduled.json')
DB_FILE = os.path.join(sc.DATA, 'chat.db')

ACTIONS = [('replace', 'Replace with XXXX'), ('warn', 'Warn the player'), ('notify', 'Tell online moderators'),
           ('kick', 'Kick'), ('kick_ban', 'Kick, then ban after strikes'), ('jail', 'Jail')]
SPAM_ACTIONS = [('drop', 'Drop the message'), ('warn', 'Warn the player'), ('mute', 'Mute for some minutes'), ('kick', 'Kick'),
                ('notify', 'Tell online moderators')]

DEFAULT_RULES = {
    'enabled': True,
    'archive_days': 90,
    'lists': [
        {'name': 'Strong swears', 'on': True, 'actions': ['replace'], 'warn_text': 'Please watch your language.', 'strikes': 3,
         'words': ['fuck', 'fucker', 'motherfucker', 'shit', 'bullshit', 'cunt', 'bitch', 'bastard', 'asshole', 'dickhead',
                   'twat', 'wanker', 'prick', 'pussy', 'cock', 'whore', 'slut']},
        {'name': 'Slurs', 'on': True, 'actions': ['replace', 'warn', 'notify', 'kick_ban'], 'strikes': 3,
         'warn_text': 'Slurs are not allowed on this server. Next time you will be kicked.',
         'words': ['nigger', 'nigga', 'faggot', 'fag', 'retard', 'tranny', 'chink', 'spic', 'kike', 'gook', 'wetback',
                   'raghead', 'paki', 'coon', 'dyke']},
    ],
    'spam': {'on': True, 'max_messages': 5, 'per_seconds': 10, 'max_repeats': 3, 'actions': ['drop', 'warn'],
             'mute_minutes': 5, 'warn_text': 'Slow down please, you are sending messages too fast.'},
}


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


def load_rules():
    try:
        with open(RULES_FILE, encoding='utf-8') as f:
            d = json.load(f)
        for k, v in DEFAULT_RULES.items():
            d.setdefault(k, json.loads(json.dumps(v)))
        return d
    except (OSError, ValueError):
        d = json.loads(json.dumps(DEFAULT_RULES))
        save_rules(d)
        return d


def save_rules(d):
    _write_json(RULES_FILE, d)
    sc.log_line('chat rules saved')


# ---------------------------------------------------------------- scheduled messages
def load_schedule():
    try:
        with open(SCHEDULE_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def save_schedule(items):
    _write_json(SCHEDULE_FILE, items)


def put_scheduled(text, when, repeat_minutes=0, item_id=None):
    """Add or change a scheduled message. when = epoch seconds of the first (next) sending."""
    text = (text or '').strip()
    if not text:
        raise sc.ServerError('Type the message first.')
    items = load_schedule()
    it = next((i for i in items if i.get('id') == item_id), None) if item_id else None
    if it is None:
        it = {'id': uuid.uuid4().hex[:8]}
        items.append(it)
    it.update(text=text[:200], next=float(when), repeat_minutes=float(repeat_minutes or 0), on=True)
    save_schedule(items)
    return it['id']


def delete_scheduled(item_id):
    save_schedule([i for i in load_schedule() if i.get('id') != item_id])


# ---------------------------------------------------------------- archive and hit log
def _db():
    if not os.path.exists(DB_FILE):
        return None
    c = sqlite3.connect(DB_FILE, timeout=5)
    return c


def history(player=None, text=None, limit=500):
    """[(time, player, channel, zone, target, text)] newest last."""
    c = _db()
    if not c:
        return []
    where, args = [], []
    if player:
        where.append('player = ? COLLATE NOCASE')
        args.append(player)
    if text:
        where.append('text LIKE ?')
        args.append('%' + text.replace('%', '') + '%')
    sql = 'SELECT ts, player, channel, zone, target, text FROM archive%s ORDER BY id DESC LIMIT %d' % (
        (' WHERE ' + ' AND '.join(where)) if where else '', int(limit))
    try:
        rows = c.execute(sql, args).fetchall()
    finally:
        c.close()
    return list(reversed(rows))


def hits(text=None, since_id=0, limit=500):
    """[(id, time, player, channel, rule, text, actions)] newest last."""
    c = _db()
    if not c:
        return []
    where, args = ['id > ?'], [since_id]
    if text:
        where.append('(player LIKE ? OR text LIKE ? OR rule LIKE ?)')
        args += ['%' + text + '%'] * 3
    try:
        rows = c.execute('SELECT id, ts, player, channel, rule, text, actions FROM hits WHERE %s ORDER BY id DESC LIMIT %d'
                         % (' AND '.join(where), int(limit)), args).fetchall()
    except sqlite3.Error:
        rows = []
    finally:
        c.close()
    return list(reversed(rows))


def last_hit_id():
    c = _db()
    if not c:
        return 0
    try:
        r = c.execute('SELECT IFNULL(MAX(id), 0) FROM hits').fetchone()
        return r[0] if r else 0
    except sqlite3.Error:
        return 0
    finally:
        c.close()


def zone_names():
    try:
        import server_admin as sa
        return {z: n for z, n in sa.zones()}
    except Exception:                                        # noqa: BLE001
        return {}


def export_history(path, player=None, text=None):
    zones = zone_names()
    rows = history(player, text, limit=1000000)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('FFXI 2016 Server chat history%s%s\n\n' % (' of ' + player if player else '', ' containing "%s"' % text if text else ''))
        for ts, p, ch, z, tg, tx in rows:
            f.write('%s  %-15s %-9s %-24s %s%s\n' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts)), p, ch,
                                                     zones.get(z, '') if z else '', ('to %s: ' % tg) if tg else '', tx))
    return len(rows)
