"""Hardcore mode (FFXI 2016 Server, Fan Project by Habex): a character that falls cannot come back, unless you restore it here.

The lsb/modules/hardcore_mode module does the work in the game and reads Server/data/hardcore.lua. Switching the mode on or off, or
changing the number of lives, applies at once. Fallen characters are only marked, never deleted."""
import os
import re

import server_control as sc

CONFIG_FILE = os.path.join(sc.DATA, 'hardcore.lua')
MAX_LIVES = 9


def get():
    """{'on': bool, 'lives': int}"""
    cfg = sc.load_config()
    return {'on': bool(cfg.get('hardcore_on', False)), 'lives': max(1, min(MAX_LIVES, int(cfg.get('hardcore_lives', 1) or 1)))}


def save(on, lives):
    try:
        lives = int(lives)
    except (TypeError, ValueError):
        raise sc.ServerError('Lives must be a number from 1 to %d.' % MAX_LIVES)
    if not 1 <= lives <= MAX_LIVES:
        raise sc.ServerError('Lives must be a number from 1 to %d.' % MAX_LIVES)
    cfg = sc.load_config()
    cfg['hardcore_on'], cfg['hardcore_lives'] = bool(on), lives
    sc.save_config(cfg)
    os.makedirs(sc.DATA, exist_ok=True)
    body = '-- written by the FFXI 2016 Server App; do not edit by hand\nreturn { on = %s, lives = %d }\n' % ('true' if on else 'false', lives)
    tmp = CONFIG_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(body)
    os.replace(tmp, CONFIG_FILE)


def fallen():
    """[(charid, name)] of the characters that fell."""
    rows = sc.sql("SELECT c.charid, c.charname FROM char_vars v JOIN chars c ON c.charid = v.charid WHERE v.varname = 'HC_fallen' AND v.value = 1 "
                  "ORDER BY c.charname")
    return [(int(r[0]), r[1]) for r in rows]


def restore(charid):
    """Let a fallen character play again (it also gets its lives back)."""
    charid = int(charid)
    sc.sql("DELETE FROM char_vars WHERE charid = ? AND varname IN ('HC_fallen', 'HC_deaths')", (charid,))
