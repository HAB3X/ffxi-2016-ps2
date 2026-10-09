"""Server name and the welcome message sent to each player who logs in (FFXI 2016 Server, Fan Project by Habex).

The name is LandSandBoat's SERVER_NAME (the world name the PS2 shows); it is written into lsb/settings/main.lua and needs a server
restart. The welcome message is written to data/app_server.lua, which the lan_welcome module re-reads at every login, so it
changes without a restart."""
import os
import re

import server_control as sc

MAIN_LUA = os.path.join(sc.SERVER, 'lsb', 'settings', 'main.lua')
MAP_LUA = os.path.join(sc.SERVER, 'lsb', 'settings', 'map.lua')
APP_FILE = os.path.join(sc.DATA, 'app_server.lua')
NAME_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9 _-]{0,14}')
DEFAULT_NAME = 'Nameless'
MAX_WELCOME = 200


def _lua_str(s):
    return "'" + s.replace('\\', '\\\\').replace("'", "\\'").replace('\n', ' ').replace('\r', ' ') + "'"


def current_name():
    try:
        m = re.search(r"^\s*SERVER_NAME\s*=\s*'([^']*)'", open(MAIN_LUA, encoding='utf-8').read(), re.M)
        return m.group(1) if m else DEFAULT_NAME
    except OSError:
        return DEFAULT_NAME


def get():
    """{'name': ..., 'welcome': ...}"""
    return {'name': current_name(), 'welcome': sc.load_config().get('welcome', '')}


def check_name(name):
    name = (name or '').strip()
    if not NAME_RE.fullmatch(name):
        raise sc.ServerError('The server name can have letters, numbers, spaces, dashes and underscores, up to 15 characters, and must start with a letter or number.')
    return name


def check_welcome(text):
    text = ' '.join((text or '').split())
    if len(text) > MAX_WELCOME:
        raise sc.ServerError('The welcome message is too long (%d characters at most).' % MAX_WELCOME)
    if any(ord(c) < 32 or ord(c) > 126 for c in text):
        raise sc.ServerError('The welcome message can only use plain letters, numbers and punctuation (the game cannot show other characters).')
    return text


def _write_app_file(name, welcome):
    os.makedirs(sc.DATA, exist_ok=True)
    body = '-- written by the FFXI 2016 Server App; do not edit by hand\nreturn {\n    name = %s,\n    welcome = %s,\n}\n' % (_lua_str(name), _lua_str(welcome))
    sc._private_write(APP_FILE, body) if hasattr(sc, '_private_write') else open(APP_FILE, 'w').write(body)


def save(name=None, welcome=None):
    """Save either or both. Returns True when the name changed (the server needs a restart for that)."""
    cur = get()
    name = cur['name'] if name is None else check_name(name)
    welcome = cur['welcome'] if welcome is None else check_welcome(welcome)
    changed = name != cur['name']
    if changed:
        txt = open(MAIN_LUA, encoding='utf-8').read()
        line = "    SERVER_NAME = %s," % _lua_str(name)
        if re.search(r"^\s*SERVER_NAME\s*=", txt, re.M):
            txt = re.sub(r"^\s*SERVER_NAME\s*=.*$", lambda m: line, txt, count=1, flags=re.M)
        else:
            txt = re.sub(r"(xi\.settings\.main\s*=\s*\n\{\n)", lambda m: m.group(1) + line + '\n', txt, count=1)
            if 'SERVER_NAME' not in txt:
                raise sc.ServerError('Could not find the place to put the server name in settings/main.lua.')
        tmp = MAIN_LUA + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(txt)
        os.replace(tmp, MAIN_LUA)
    cfg = sc.load_config()
    cfg['welcome'] = welcome
    sc.save_config(cfg)
    _write_app_file(name, welcome)
    return changed


# ---------------------------------------------------------------- rates, monsters and rules
# The server watches its settings folder: a changed value applies within a few seconds, no restart. Only the values that differ from
# LandSandBoat's own defaults are written (settings/main.lua and settings/map.lua are overrides; settings/default/ is never touched).
import json
import time
from collections import namedtuple

Setting = namedtuple('Setting', 'file key label kind lo hi')
FILES = {'main': MAIN_LUA, 'map': MAP_LUA}
DEFAULT_DIR = os.path.join(sc.SERVER, 'lsb', 'settings', 'default')


def _mult(key, label, lo=0.1, hi=10.0):
    return Setting('map', key, label, 'mult', lo, hi)


GROUPS = {
    'rates': [_mult('EXP_RATE', 'Experience'), _mult('MOB_GIL_MULTIPLIER', 'Gil from monsters'), _mult('DROP_RATE_MULTIPLIER', 'Item drops'),
              _mult('SKILLUP_CHANCE_MULTIPLIER', 'Skill-ups'), _mult('CRAFT_CHANCE_MULTIPLIER', 'Crafting skill-ups'),
              _mult('CAPACITY_RATE', 'Capacity points'), _mult('EXP_LOSS_RATE', 'Experience lost on death', 0.0)],
    'monsters': [_mult('MOB_HP_MULTIPLIER', 'Monster health'), _mult('NM_HP_MULTIPLIER', 'Notorious monster health'),
                 _mult('MOB_STAT_MULTIPLIER', 'Monster strength'), _mult('MOB_MP_MULTIPLIER', 'Monster magic points')],
    'rules': [Setting('main', 'INITIAL_LEVEL_CAP', 'Starting level cap', 'int', 1, 99), Setting('main', 'MAX_LEVEL', 'Highest level', 'int', 1, 99)] + [
        Setting('main', k, label, 'flag', 0, 1) for k, label in (
            ('ENABLE_ROTZ', 'Rise of the Zilart'), ('ENABLE_COP', 'Chains of Promathia'), ('ENABLE_TOAU', 'Treasures of Aht Urhgan'),
            ('ENABLE_WOTG', 'Wings of the Goddess'), ('ENABLE_ACP', 'A Crystalline Prophecy'), ('ENABLE_AMK', 'A Moogle Kupo d\'Etat'),
            ('ENABLE_ASA', 'A Shantotto Ascension'), ('ENABLE_ABYSSEA', 'Abyssea'), ('ENABLE_SOA', 'Seekers of Adoulin'))],       # what the PS2 game has
}
ALL = {st.key: st for g in GROUPS.values() for st in g}


def _table_text(file):
    try:
        return open(FILES[file], encoding='utf-8').read()
    except OSError:
        return ''


def _matches(txt, file, key):
    """Every place a key is set: a line of the settings table, or an "xi.settings.<file>.KEY = value" line after it (the last one wins)."""
    return list(re.finditer(r'^[ \t]*(?:xi\.settings\.%s\.)?%s[ \t]*=[ \t]*([^,\s][^,\s]*)' % (file, re.escape(key)), txt, re.M))


def _find(txt, file, key):
    ms = _matches(txt, file, key)
    return ms[-1].group(1) if ms else None


def _num(raw, st):
    if raw is None:
        return None
    if raw in ('true', 'false'):
        return 1 if raw == 'true' else 0
    try:
        v = float(raw)
    except ValueError:
        return None
    return int(v) if st.kind in ('int', 'flag') else v


def current(st):
    """The value the server uses now: the override if there is one, else LandSandBoat's default."""
    v = _num(_find(_table_text(st.file), st.file, st.key), st)
    if v is None:
        try:
            v = _num(_find(open(os.path.join(DEFAULT_DIR, st.file + '.lua'), encoding='utf-8').read(), st.file, st.key), st)
        except OSError:
            v = None
    return v if v is not None else (1.0 if st.kind == 'mult' else 0)


def _write_keys(file, literals):
    """literals: {KEY: lua text}. Changes the value where the key is set (the last place, as that one wins), or adds it to the table."""
    txt = _table_text(file)
    for key, lit in literals.items():
        ms = _matches(txt, file, key)
        if ms:
            m = ms[-1]
            txt = txt[:m.start(1)] + lit + txt[m.end(1):]
            continue
        txt, n = re.subn(r'(xi\.settings\.%s\s*=\s*\n\{\n)' % file, lambda m: m.group(1) + '    %s = %s,\n' % (key, lit), txt, count=1)
        if not n:
            raise sc.ServerError('Could not find the place for the settings in settings/%s.lua.' % file)
    tmp = FILES[file] + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(txt)
    os.replace(tmp, FILES[file])


def _literal(st, v):
    return ('%d' % v) if st.kind in ('int', 'flag') else ('%g' % v)


def _store(values):
    """Write {key: number} to the settings files (one write per file)."""
    per = {}
    for key, v in values.items():
        st = ALL[key]
        per.setdefault(st.file, {})[key] = _literal(st, v)
    for file, lits in per.items():
        _write_keys(file, lits)


# ---- scheduled events: rate changes that switch on and off by the clock while the Server App is open
EVENTS_FILE = os.path.join(sc.DATA, 'events.json')
STATE_FILE = os.path.join(sc.DATA, 'event_state.json')
DAY_NAMES = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')


def _json_load(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _json_save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1)
    os.replace(path + '.tmp', path)


def list_events():
    return [e for e in _json_load(EVENTS_FILE, []) if isinstance(e, dict) and e.get('id')]


def _hm(text):
    h, m = text.split(':')
    return int(h) * 60 + int(m)


def check_event(ev):
    """Validates and tidies an event dict from the form; returns it or raises ServerError."""
    name = re.sub(r'\s+', ' ', str(ev.get('name', '')).strip())[:30]
    if not name:
        raise sc.ServerError('Give the event a name.')
    days = sorted({int(d) for d in ev.get('days', []) if 0 <= int(d) <= 6})
    if not days:
        raise sc.ServerError('Pick at least one day.')
    try:
        a, b = _hm(ev['start']), _hm(ev['end'])
    except (KeyError, ValueError):
        raise sc.ServerError('Times look like 18:00.')
    if not (0 <= a < 1440 and 0 <= b < 1440) or a == b:
        raise sc.ServerError('Start and end must be different times between 00:00 and 23:59.')
    mult = {}
    for k, v in (ev.get('mult') or {}).items():
        st = ALL.get(k)
        if st is None or st.kind != 'mult':
            continue
        try:
            v = round(float(v), 2)
        except (TypeError, ValueError):
            raise sc.ServerError('%s must be a number like 2.' % st.label)
        if not 0.1 <= v <= 10:
            raise sc.ServerError('%s must be between 0.1 and 10.' % st.label)
        if v != 1.0:
            mult[k] = v
    if not mult:
        raise sc.ServerError('Set at least one rate to something other than 1.')
    return {'id': ev.get('id') or 'e%d' % int(time.time() * 1000), 'name': name, 'days': days, 'start': ev['start'], 'end': ev['end'],
            'mult': mult, 'on': bool(ev.get('on', True))}


def save_events(events):
    _json_save(EVENTS_FILE, [check_event(e) for e in events])


def event_text(ev):
    days = ', '.join(DAY_NAMES[d] for d in ev['days']) if len(ev['days']) < 7 else 'Every day'
    what = ', '.join('%s x%g' % (ALL[k].label.lower(), v) for k, v in ev['mult'].items() if k in ALL)
    return '%s  %s-%s  %s' % (days, ev['start'], ev['end'], what)


def event_active(ev, now):
    """True while `now` (a time.struct_time) is inside the event. An event that runs past midnight stays on after midnight."""
    t = now.tm_hour * 60 + now.tm_min
    a, b = _hm(ev['start']), _hm(ev['end'])
    day = now.tm_wday
    if a < b:
        return day in ev['days'] and a <= t < b
    return (day in ev['days'] and t >= a) or ((day - 1) % 7 in ev['days'] and t < b)


def _state():
    return _json_load(STATE_FILE, {'active': None, 'base': {}})


def get_values(group):
    """{KEY: value} for the form: while an event changes a rate, the normal (base) value is shown, not the event's."""
    base = _state().get('base', {})
    return {st.key: (base[st.key] if st.key in base else current(st)) for st in GROUPS[group]}


def _validate(st, v):
    try:
        v = float(v) if st.kind == 'mult' else int(float(v))
    except (TypeError, ValueError):
        raise sc.ServerError('%s must be a number%s.' % (st.label, ' like 1 or 2.5' if st.kind == 'mult' else ''))
    if st.kind == 'mult':
        v = round(v, 2)
    if not st.lo <= v <= st.hi:
        raise sc.ServerError('%s must be between %g and %g.' % (st.label, st.lo, st.hi))
    return v


def save_values(group, values):
    """Save the values of one group ({KEY: number, text or True/False}). Returns True when something changed."""
    cur = get_values(group)
    new = {}
    for st in GROUPS[group]:
        if st.key not in values:
            continue
        v = values[st.key]
        new[st.key] = (1 if v else 0) if st.kind == 'flag' else _validate(st, v)
    if group == 'rules' and new.get('INITIAL_LEVEL_CAP', cur['INITIAL_LEVEL_CAP']) > new.get('MAX_LEVEL', cur['MAX_LEVEL']):
        raise sc.ServerError('The starting level cap cannot be above the highest level.')
    changed = {k: v for k, v in new.items() if v != cur[k]}
    if not changed:
        return False
    state = _state()
    write = {}
    for k, v in changed.items():
        if k in state.get('base', {}):                              # an event is changing this rate right now: keep the event's effect
            state['base'][k] = v
            ev = next((e for e in list_events() if e['id'] == state.get('active')), None)
            write[k] = _clamp(ALL[k], v * (ev['mult'].get(k, 1.0) if ev else 1.0))
        else:
            write[k] = v
    if state.get('base'):
        _json_save(STATE_FILE, state)
    _store(write)
    return True


def _clamp(st, v):
    return round(min(st.hi, max(st.lo, v)), 2)


def tick_events(now=None):
    """Call every half minute: switches the scheduled event on or off. Returns a message when something changed, else None."""
    now = now or time.localtime()
    state = _state()
    due = next((e for e in list_events() if e.get('on', True) and event_active(e, now)), None)
    want = due['id'] if due else None
    if want == state.get('active'):
        return None
    msg = []
    if state.get('active'):                                          # an event ended (or was removed or switched off): back to the normal values
        _store(state.get('base', {}))
        msg.append('The event ended: rates are back to normal.')
        state = {'active': None, 'base': {}}
        _json_save(STATE_FILE, state)
    if due:
        base = {k: current(ALL[k]) for k in due['mult'] if k in ALL}
        _store({k: _clamp(ALL[k], base[k] * m) for k, m in due['mult'].items() if k in base})
        _json_save(STATE_FILE, {'active': due['id'], 'base': base})
        msg.append('Event "%s" is on: %s.' % (due['name'], event_text(due).split('  ', 2)[2]))
    return ' '.join(msg)


# the older names, kept for the code that still uses them
RATES = [(st.key, st.label) for st in GROUPS['rates'][:4]]


def get_rates():
    return get_values('rates')


def save_rates(values):
    return save_values('rates', values)


# ---------------------------------------------------------------- era presets: which expansions are open and the level cap
ERA_KEYS = ('ENABLE_ROTZ', 'ENABLE_COP', 'ENABLE_TOAU', 'ENABLE_WOTG', 'ENABLE_ACP', 'ENABLE_AMK', 'ENABLE_ASA', 'ENABLE_ABYSSEA', 'ENABLE_SOA')
ERAS = [
    ('era75', 'Level 75 era', 'The game as it was before Abyssea: levels up to 75.',
     dict(zip(ERA_KEYS, (1, 1, 1, 1, 0, 0, 0, 0, 0)), MAX_LEVEL=75, INITIAL_LEVEL_CAP=50)),
    ('eraabyssea', 'Abyssea era', 'Adds the Crystalline Prophecy, Moogle, Shantotto and Abyssea content, with level 99.',
     dict(zip(ERA_KEYS, (1, 1, 1, 1, 1, 1, 1, 1, 0)), MAX_LEVEL=99, INITIAL_LEVEL_CAP=50)),
    ('eraadoulin', 'Adoulin era', 'Everything the 2016 PS2 disc has, including Seekers of Adoulin, with level 99.',
     dict(zip(ERA_KEYS, (1, 1, 1, 1, 1, 1, 1, 1, 1)), MAX_LEVEL=99, INITIAL_LEVEL_CAP=50)),
]


def era_values(key):
    """The settings of one preset ({KEY: value}), or None."""
    for k, _, _, vals in ERAS:
        if k == key:
            return dict(vals)
    return None


def detect_era():
    """The key of the preset the server matches now, or None when it is a mix."""
    cur = get_values('rules')
    for k, _, _, vals in ERAS:
        if all(int(cur.get(key, -1)) == int(v) for key, v in vals.items()):
            return k
    return None


# ---------------------------------------------------------------- announcing events in the game
def announce_events_on():
    return bool(sc.load_config().get('announce_events', True))


def set_announce_events(on):
    cfg = sc.load_config()
    cfg['announce_events'] = bool(on)
    sc.save_config(cfg)
