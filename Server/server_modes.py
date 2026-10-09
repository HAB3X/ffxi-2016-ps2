"""Gameplay modes (FFXI 2016 Server, Fan Project by Habex): small plain on/off switches.

Each mode is a copy of a module by LoxleyXI (https://github.com/LoxleyXI/Modules, GPL-3.0) under Server/lsb/modules/<name>/.
LandSandBoat reads modules/init.txt ONCE, when the map server starts, so every switch applies after the server is restarted.
Two kinds:
  'init' modes are a line in modules/init.txt (inside a block this file keeps tidy).
  'exp'  mode changes the experience table (exp_base) in the running database and keeps the old numbers so it can put them back.
Nothing is switched on unless the player turns it on.
"""
import json
import os
import re

import server_control as sc

MODULES = os.path.join(sc.LSB, 'modules')
INIT_TXT = os.path.join(MODULES, 'init.txt')
STATE_FILE = os.path.join(sc.DATA, 'modes.json')
TAG = '# FFXI 2016 Server App (World > Modes): '

MODES = [
    ('reasonable_exp', 'exp', 'Gentler experience curve',
     'Levels 53 to 76 need a flat 200 more experience per level instead of the steep climb after the level 55 cap break. Reaching level 75 '
     'takes about 40% less. Good for playing alone. To switch it on or off the server must be running (it changes the experience list).'),
    ('helm_claim', 'init', 'Fair gathering points',
     'The first player to dig, chop, mine or harvest at a point keeps it for 10 seconds, so friends do not steal each other\'s turns.'),
    ('oztroja_escape', 'init', 'Castle Oztroja escape hole',
     'Adds a hole on the top floor of Castle Oztroja so players can leave without a Judgment Key. We could not test it with the PS2 game: '
     'if you find no hole near the edge of the top floor, switch it off again.'),
]
KEYS = [m[0] for m in MODES]
KIND = {m[0]: m[1] for m in MODES}
LABEL = {m[0]: m[2] for m in MODES}
EXP_SQL = os.path.join(MODULES, 'reasonable_exp', 'reasonable_exp.sql')
APPLY_NOTE = 'Applies the next time the server starts.'


def _state():
    try:
        with open(STATE_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_state(st):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(st, f, indent=1)
    os.replace(STATE_FILE + '.tmp', STATE_FILE)


# ---- init.txt
def _read_init():
    try:
        with open(INIT_TXT, encoding='utf-8') as f:
            return f.read().splitlines()
    except OSError:
        return None


def _entry(line):
    return line.strip().rstrip('/')


def init_has(key):
    lines = _read_init() or []
    return any(_entry(l) == key for l in lines if not l.strip().startswith('#'))


def _write_init(lines):
    os.makedirs(MODULES, exist_ok=True)
    tmp = INIT_TXT + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines).rstrip('\n') + '\n')
    os.replace(tmp, INIT_TXT)


def _set_init(key, on):
    lines = _read_init()
    if lines is None:
        lines = ['# This file marks which modules to load (one per line, "#" starts a comment).']
    has = any(_entry(l) == key for l in lines if not l.strip().startswith('#'))
    if on and not has:
        lines += ['', TAG + LABEL[key], key]
    elif not on and has:
        out = []
        for i, l in enumerate(lines):
            if not l.strip().startswith('#') and _entry(l) == key:
                if out and out[-1].startswith(TAG):                    # our own comment line goes with it
                    out.pop()
                    if out and out[-1] == '':
                        out.pop()
                continue
            out.append(l)
        lines = out
    else:
        return
    _write_init(lines)


# ---- the experience mode
def _exp_changes():
    """[(level, new exp, old exp)] from the module's SQL file."""
    out = []
    with open(EXP_SQL, encoding='utf-8') as f:
        for line in f:
            m = re.match(r'UPDATE `exp_base` SET exp =\s*(\d+) WHERE level = (\d+);\s*--\s*(\d+)', line)
            if m:
                out.append((int(m.group(2)), int(m.group(1)), int(m.group(3))))
    return out


def _exp_set(on):
    if not sc.db_ready():
        raise sc.ServerError('Start the server first: this switch changes the experience list in the database, which has to be on.')
    st = _state()
    changes = _exp_changes()
    if not changes:
        raise sc.ServerError('The experience module files are missing (Server/lsb/modules/reasonable_exp).')
    levels = ','.join(str(l) for l, _, _ in changes)
    if on:
        if 'exp_original' not in st:                                            # remember what was there, once
            st['exp_original'] = {str(int(r[0])): int(r[1]) for r in sc.sql('SELECT level, exp FROM exp_base WHERE level IN (%s)' % levels)}
        stmts = ['UPDATE exp_base SET exp = %d WHERE level = %d' % (new, lvl) for lvl, new, _ in changes]
    else:
        orig = st.get('exp_original') or {str(l): old for l, _, old in changes}
        stmts = ['UPDATE exp_base SET exp = %d WHERE level = %d' % (int(v), int(l)) for l, v in orig.items()]
    sc.sql('', stdin_bytes=(';\n'.join(stmts) + ';\n').encode('ascii'))
    if on:
        st['exp'] = True
    else:
        st.pop('exp', None)
        st.pop('exp_original', None)
    _save_state(st)


# ---- public
def enabled(key):
    return bool(_state().get('exp')) if KIND[key] == 'exp' else init_has(key)


def states():
    return {k: enabled(k) for k in KEYS}


def set_enabled(key, on):
    """Switch one mode. Returns a short plain sentence for the player. Raises ServerError when it cannot be done."""
    if key not in KIND:
        raise sc.ServerError('Unknown mode.')
    on = bool(on)
    if KIND[key] == 'exp':
        _exp_set(on)
    else:
        if on and not os.path.isdir(os.path.join(MODULES, key)):
            raise sc.ServerError('The module files are missing (Server/lsb/modules/%s). Copy the release folder again.' % key)
        _set_init(key, on)
    return '%s is %s. %s' % (LABEL[key], 'on' if on else 'off', APPLY_NOTE)
