#!/usr/bin/env python3
"""FFXI 2016 Release - roles for in-game "!" GM commands (Fan Project by Habex).

A role is a name ("Head Admin", "Moderator") and the list of in-game commands it may use. Promoting a character gives
it a role; demoting removes it. Only role members can use GM commands in the game, and only their role's commands
(the lan_roles module in Server/lsb/modules checks every "!" command). Commands any player may use (permission 0)
stay open. Roles live in Server/data/roles.json; the map server reads Server/lsb/app_roles.lua (re-read every few
seconds, so changes apply without a restart). The world-chat commands in the Server App are always allowed for the
person at the app.
"""
import glob, json, os, re

import server_control as sc

ROLES_JSON = os.path.join(sc.DATA, 'roles.json')
LUA_FILE = os.path.join(sc.DATA, 'app_roles.lua')

# groups for the checkbox list (commands not listed here go to "Other")
GROUPS = [
    ('Moving players', ['zone', 'goto', 'gotoid', 'gotoname', 'bring', 'tp', 'pos', 'posfix', 'homepoint', 'return', 'send', 'up',
                        'down', 'gmhome', 'where', 'pettp']),
    ('Moderation', ['kick', 'logoff', 'ban', 'pardon', 'jail', 'release', 'yell', 'afkcheck', 'promote', 'togglegm']),
    ('Items and gil', ['additem', 'giveitem', 'item', 'addtempitem', 'delitem', 'delallinventory', 'delcontaineritems', 'hasitem',
                       'gil', 'givegil', 'setgil', 'takegil', 'addkeyitem', 'delkeyitem', 'haskeyitem', 'addcurrency', 'delcurrency',
                       'givels', 'givemagianitem', 'givebonanzapearl', 'ah', 'setbag', 'addtreasure']),
    ('Level, job and skills', ['level', 'setplayerlevel', 'changejob', 'changesjob', 'masterjob', 'givexp', 'takexp', 'setmerits',
                               'setjobpoints', 'setcapacitypoints', 'capskill', 'capallskills', 'setskill', 'getskill', 'setcraftrank',
                               'addspell', 'delspell', 'addallspells', 'addallweaponskills', 'delallweaponskills',
                               'addweaponskillpoints', 'getwspoints', 'cp']),
    ('Health and combat', ['hp', 'mp', 'raise', 'kill', 'godmode', 'immortal', 'petgodmode', 'stun', 'sleep', 'provokeall', 'addeffect',
                           'deleffect', 'geteffects', 'reset']),
    ('Invisible, speed and looks', ['invisible', 'hide', 'speed', 'wallhack', 'cansee', 'costume', 'costume2', 'setplayermodel',
                                    'mount', 'animation', 'racechange', 'rename', 'entityvisual', 'inwater', 'chocobo']),
    ('Monsters and world', ['spawnmob', 'despawnmob', 'mobhere', 'npchere', 'setmoblevel', 'setmobflags', 'setmobmod', 'mobskill',
                            'mobsub', 'setweather', 'time', 'addtime', 'setmusic', 'spawn', 'garrison', 'updateconquest',
                            'animatenpc', 'animatesubnpc', 'posemannequin', 'lanboss', 'instance', 'checkinstance',
                            'setbattlefieldtime', 'minigame', 'addlights', 'resetlights']),
    ('Quests, missions and titles', ['addquest', 'completequest', 'delquest', 'quest', 'checkquest', 'getquestvar', 'setquestvar',
                                     'addmission', 'completemission', 'delmission', 'mission', 'checkmission', 'checkmissionstatus',
                                     'setmissionstatus', 'setprogress', 'setstage', 'completerecord', 'addtitle', 'hastitle', 'setrank',
                                     'setfamelevel', 'getfame', 'cnation', 'setplayernation', 'setallegiance', 'addallmaps',
                                     'addallwarps', 'addalltrusts', 'addallattachments', 'addallatma', 'addallmonstrosity',
                                     'addallmounts', 'addabytime', 'adddynatime', 'setmentor', 'monstrosity', 'addfish', 'getfishers']),
    ('Server (dangerous)', ['reload', 'reloadglobal', 'reloadquest', 'reloadrecipes', 'reloadbattlefield', 'reloadinteraction',
                            'reloaddefaultactions', 'reloadmagians', 'reloadnavmesh', 'rebuildnavmesh', 'crash', 'exec', 'inject',
                            'injectaction', 'save', 'gc_full', 'gc_step', 'fafnir', 'naga', 'checkinteraction', 'test']),
]


def all_commands():
    """{name: (permission, description)} of every in-game "!" command (permission 0 ones are open to everyone)."""
    out = {}
    files = glob.glob(os.path.join(sc.LSB, 'scripts', 'commands', '*.lua')) + glob.glob(os.path.join(sc.LSB, 'modules', '*', 'commands', '*.lua'))
    for f in files:
        try:
            t = open(f, encoding='utf-8', errors='replace').read(4000)
        except OSError:
            continue
        m = re.search(r'permission\s*=\s*(\d+)', t)
        if not m:
            continue
        d = re.search(r'--\s*desc:\s*(.+)', t)
        out[os.path.splitext(os.path.basename(f))[0]] = (int(m.group(1)), (d.group(1).strip() if d else '')[:90])
    return out


def grouped():
    """[(group, [(name, permission, description)])] of the commands a role can be given (permission > 0)."""
    cmds = {k: v for k, v in all_commands().items() if v[0] > 0}
    seen, out = set(), [('Server App', [('chatrules', 1, 'Manage chat rules (gets the chat rule notices in the game)')])]
    for g, names in GROUPS:
        items = [(n, cmds[n][0], cmds[n][1]) for n in names if n in cmds]
        seen.update(n for n, _, _ in items)
        if items:
            out.append((g, items))
    rest = sorted((n, p, d) for n, (p, d) in cmds.items() if n not in seen)
    if rest:
        out.append(('Other', rest))
    return out


def load():
    try:
        with open(ROLES_JSON, encoding='utf-8') as f:
            d = json.load(f)
        return {'roles': dict(d.get('roles') or {}), 'members': dict(d.get('members') or {})}
    except (OSError, ValueError):
        return {'roles': {}, 'members': {}}


def _lua_str(s):
    return '"' + ''.join(c if c.isalnum() or c in ' -_' else '\\%03d' % b for b in str(s).encode('utf-8') for c in [chr(b)]) + '"'


def save(d):
    os.makedirs(sc.DATA, exist_ok=True)
    tmp = ROLES_JSON + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(d, f, indent=1)
    os.replace(tmp, ROLES_JSON)
    write_lua(d)


def write_lua(d=None):
    """The file the map server reads (Server/lsb/app_roles.lua)."""
    d = d or load()
    lines = ['-- written by the FFXI 2016 Server App (Roles); do not edit by hand', 'return {', '    roles = {']
    for role, cmds in sorted(d['roles'].items()):
        lines.append('        [%s] = { %s },' % (_lua_str(role), ', '.join('[%s] = true' % _lua_str(c) for c in sorted(cmds))))
    lines += ['    },', '    members = {']
    for char, role in sorted(d['members'].items()):
        if role in d['roles']:
            lines.append('        [%s] = %s,' % (_lua_str(char.lower()), _lua_str(role)))
    lines += ['    },', '}', '']
    for path in {LUA_FILE, os.path.join(sc.map_files_dir(), 'app_roles.lua')}:   # + where a running map server reads it
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        os.replace(tmp, path)


def level_for(role, d=None):
    """The GM level a role needs: the highest permission among its commands (at least 1)."""
    d = d or load()
    perms = all_commands()
    return max([1] + [perms[c][0] for c in d['roles'].get(role, []) if c in perms])


def _apply_level(char, level, role):
    """Set the character's GM level now (in game if online, else in the database)."""
    import server_admin as sa
    r = sa.q('SELECT c.charid, (s.charid IS NOT NULL) FROM chars c LEFT JOIN accounts_sessions s ON s.charid = c.charid '
             'WHERE c.charname = ?', (char,))
    if not r:
        return
    if r[0][1] == '1' and sc.is_running('xi_map'):
        ok, text = sa.call('setrole', char, level, role or '')
        if ok:
            return
    sa.q('UPDATE chars SET gmlevel = ? WHERE charname = ?', (level, char))


def role_of(char, d=None):
    d = d or load()
    for c, r in d['members'].items():
        if c.lower() == char.lower():
            return r
    return None


def save_role(name, commands, old_name=None):
    name = (name or '').strip()
    if not re.fullmatch(r"[A-Za-z0-9 _\-']{2,30}", name):
        raise sc.ServerError('A role name needs 2 to 30 letters or numbers.')
    d = load()
    if old_name and old_name != name:
        if name in d['roles']:
            raise sc.ServerError('There is already a role called "%s".' % name)
        d['roles'].pop(old_name, None)
        for c, r in list(d['members'].items()):
            if r == old_name:
                d['members'][c] = name
    elif not old_name and name in d['roles']:
        raise sc.ServerError('There is already a role called "%s".' % name)
    d['roles'][name] = sorted(set(commands))
    save(d)
    lvl = level_for(name, d)
    for c, r in d['members'].items():
        if r == name:
            _apply_level(c, lvl, name)
    sc.log_line('role saved: %s (%d commands)' % (name, len(commands)))


def delete_role(name):
    d = load()
    d['roles'].pop(name, None)
    gone = [c for c, r in d['members'].items() if r == name]
    for c in gone:
        d['members'].pop(c)
    save(d)
    for c in gone:
        _apply_level(c, 0, None)
    sc.log_line('role deleted: %s' % name)
    return gone


def promote(char, role):
    import server_admin as sa
    r = sa.q('SELECT charname FROM chars WHERE LOWER(charname) = LOWER(?)', (char.lstrip('@'),))
    if not r:
        raise sc.ServerError('No player called %s.' % char)
    char = r[0][0]
    d = load()
    if role not in d['roles']:
        raise sc.ServerError('There is no role called "%s".' % role)
    for c in [c for c in d['members'] if c.lower() == char.lower()]:
        d['members'].pop(c)
    d['members'][char] = role
    save(d)
    _apply_level(char, level_for(role, d), role)
    sc.log_line('promoted %s to %s' % (char, role))
    return char


def demote(char):
    d = load()
    hit = [c for c in d['members'] if c.lower() == char.lower().lstrip('@')]
    for c in hit:
        d['members'].pop(c)
    save(d)
    _apply_level(hit[0] if hit else char.lstrip('@'), 0, None)
    sc.log_line('demoted %s' % char)
    return bool(hit)
