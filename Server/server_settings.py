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


# ---------------------------------------------------------------- rates (settings/map.lua); they apply after the next server start
RATES = [('EXP_RATE', 'Experience'), ('MOB_GIL_MULTIPLIER', 'Gil from monsters'), ('DROP_RATE_MULTIPLIER', 'Item drops'), ('SKILLUP_CHANCE_MULTIPLIER', 'Skill-ups')]
RATE_MIN, RATE_MAX = 0.1, 10.0


def get_rates():
    """{KEY: value}, 1.0 for anything not set in settings/map.lua."""
    try:
        txt = open(MAP_LUA, encoding='utf-8').read()
    except OSError:
        txt = ''
    out = {}
    for key, _ in RATES:
        m = re.search(r'^\s*%s\s*=\s*([0-9.]+)' % key, txt, re.M)
        out[key] = float(m.group(1)) if m else 1.0
    return out


def save_rates(values):
    """values: {KEY: number or text}. Returns True when something changed."""
    cur = get_rates()
    new = {}
    for key, label in RATES:
        v = values.get(key, cur[key])
        try:
            v = round(float(v), 2)
        except (TypeError, ValueError):
            raise sc.ServerError('%s must be a number like 1 or 2.5.' % label)
        if not RATE_MIN <= v <= RATE_MAX:
            raise sc.ServerError('%s must be between %g and %g.' % (label, RATE_MIN, RATE_MAX))
        new[key] = v
    if new == cur:
        return False
    txt = open(MAP_LUA, encoding='utf-8').read()
    for key, v in new.items():
        line = '    %s = %g,' % (key, v)
        if re.search(r'^\s*%s\s*=' % key, txt, re.M):
            txt = re.sub(r'^\s*%s\s*=.*$' % key, lambda m: line, txt, count=1, flags=re.M)
        else:
            txt, n = re.subn(r'(xi\.settings\.map\s*=\s*\n\{\n)', lambda m: m.group(1) + line + '\n', txt, count=1)
            if not n:
                raise sc.ServerError('Could not find the place for the rates in settings/map.lua.')
    tmp = MAP_LUA + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(txt)
    os.replace(tmp, MAP_LUA)
    return True
