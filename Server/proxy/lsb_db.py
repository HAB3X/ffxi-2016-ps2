#!/usr/bin/env python3
"""Tiny helper for the release server's database (Python standard library only).

The database login is read from Server/data/server_config.json (written by server_control.py at first start, owner-only)
and handed to the mariadb command-line client in a private temporary option file that is deleted straight after each
call. Passwords are never printed or logged.
"""
import json, os, subprocess, tempfile

SERVER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get('FFXI_DATA_DIR') or os.path.join(SERVER, 'data')
CONFIG = os.path.join(DATA, 'server_config.json')


def _cfg():
    with open(CONFIG, encoding='utf-8') as f:
        return json.load(f)


def _creds():
    c = _cfg()
    return {'host': '127.0.0.1', 'port': str(c['db_port']), 'database': c.get('db_name', 'xidb'),
            'user': c.get('db_user', 'xiadmin'), 'password': c['db_password']}


def _client():
    c = _cfg()
    name = 'mariadb.exe' if os.name == 'nt' else 'mariadb'
    d = c.get('mariadb_bin_dir')
    if d and os.path.exists(os.path.join(d, name)):
        return os.path.join(d, name)
    if d and os.path.exists(os.path.join(d, 'mysql.exe' if os.name == 'nt' else 'mysql')):
        return os.path.join(d, 'mysql.exe' if os.name == 'nt' else 'mysql')
    return name


class _OptionFile:
    def __enter__(self):
        c = _creds()
        fd, self.path = tempfile.mkstemp(prefix='ffxi-db-', suffix='.cnf')
        with os.fdopen(fd, 'w') as f:
            f.write('[client]\nhost=%s\nport=%s\nuser=%s\npassword="%s"\nprotocol=TCP\n'
                    % (c['host'], c['port'], c['user'], c['password']))
        self.database = c['database']
        return self

    def __exit__(self, *a):
        try:
            os.remove(self.path)
        except OSError:
            pass


def database_name():
    return _creds()['database']


def literal(v):
    """SQL literal for a Python value (numbers as they are, text quoted and escaped)."""
    if v is None:
        return 'NULL'
    if isinstance(v, bool):
        return '1' if v else '0'
    if isinstance(v, (int, float)):
        return repr(v)
    s = str(v).replace('\\', '\\\\').replace("'", "\\'").replace('\0', '\\0').replace('\n', '\\n').replace('\r', '\\r')
    return "'" + s + "'"


def bind(sql, args=()):
    """Replace each ? in sql with the next value of args (as an SQL literal)."""
    if not args:
        return sql
    parts = sql.split('?')
    if len(parts) - 1 != len(args):
        raise ValueError('placeholder count does not match the arguments')
    out = parts[0]
    for a, p in zip(args, parts[1:]):
        out += literal(a) + p
    return out


def query(sql, args=()):
    """Run statements; returns the rows (lists of str, NULL -> None) of the last one."""
    flags = 0x08000000 if os.name == 'nt' else 0          # CREATE_NO_WINDOW
    with _OptionFile() as o:
        r = subprocess.run([_client(), '--defaults-extra-file=' + o.path, '-N', '-B', '--raw', o.database],
                           input=bind(sql, args).encode('utf-8'), capture_output=True, creationflags=flags)
    if r.returncode != 0:
        raise RuntimeError('database query failed: ' + r.stderr.decode('utf-8', 'replace').strip())
    rows = []
    for line in r.stdout.decode('utf-8', 'replace').splitlines():
        rows.append([None if v == 'NULL' else v for v in line.split('\t')])
    return rows
