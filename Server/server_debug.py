"""Readable view of the PS2 login part's log (FFXI 2016 Server, Fan Project by Habex).

The log (Server/data/logs/ps2proxy.log) has one line per thing that happened: "12:00:01.123 [tag] word text". The word after the
tag says what kind of line it is: diag, event, zone, data, ... Only the end of the file is read, so this stays light.
"""
import os
import re

import server_control as sc

LOG = os.path.join(sc.LOGS, 'ps2proxy.log')
FILTERS = [('all', 'All'), ('diag', 'Diagnostics'), ('event', 'Events'), ('zone', 'Zone changes'), ('error', 'Errors')]
LINES = 300
_LINE = re.compile(r'^\S+ \[[^\]]*\] (\S+)')
_BAD = re.compile(r'error|warning|failed|not found|timeout|timed out|dropping|closed by', re.I)


def tail(path=None, n=LINES, chunk=64 * 1024):
    """The last n lines of a text file (reads only the end)."""
    path = path or LOG
    try:
        size = os.path.getsize(path)
        with open(path, 'rb') as f:
            data = b''
            pos = size
            while pos > 0 and data.count(b'\n') <= n:
                step = min(chunk, pos)
                pos -= step
                f.seek(pos)
                data = f.read(step) + data
    except OSError:
        return []
    lines = data.decode('utf-8', 'replace').splitlines()
    return lines[-n:]


def keyword(line):
    m = _LINE.match(line)
    return m.group(1).lower() if m else ''


def matches(line, mode):
    if mode == 'all':
        return True
    if not line or line[0] in ' \t':                      # the hex lines under a packet belong to the line above; only shown with "All"
        return False
    word = keyword(line)
    if mode == 'error':
        return word.startswith('error') or bool(_BAD.search(line))
    return word == mode


def view(mode='all', n=LINES, path=None):
    """Lines to show: the last n lines of the log that fit the filter, as one text."""
    lines = tail(path, n * 4 if mode != 'all' else n)    # a filter needs a longer stretch to find enough lines
    shown = [l for l in lines if matches(l, mode)][-n:]
    return '\n'.join(shown)


def exists(path=None):
    return os.path.exists(path or LOG)
