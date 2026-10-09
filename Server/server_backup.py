"""Backups of the player data: accounts, characters, mail, chat logs and the other tables listed in database/emptied_tables.txt.
A backup is a gzip file in data/backups. Restoring replaces the player data with the backup's; the world data is not touched."""
import gzip
import os
import re
import subprocess
import time

import server_control as sc

BACKUPS = os.path.join(sc.DATA, 'backups')
TABLES_FILE = os.path.join(sc.SERVER, 'database', 'emptied_tables.txt')


def tables():
    out = []
    for line in open(TABLES_FILE, encoding='utf-8'):
        line = line.strip()
        if re.fullmatch(r'[a-z0-9_]+', line):
            out.append(line)
    return out


def _tool(m):
    for name in ('mariadb-dump', 'mysqldump'):
        p = os.path.join(m['bin_dir'], name + sc.EXE)
        if os.path.exists(p):
            return p
    raise sc.ServerError('The database dump program was not found. Run Setup again.')


class _Database:
    """Makes sure the database is running for the length of a block, and stops it again if it had to be started."""
    def __enter__(self):
        self.started = False
        if not sc.db_ready():
            sc.start_database(say=lambda *a, **k: None)
            self.started = True
        return self

    def __exit__(self, *exc):
        if self.started:
            sc.stop_database()


def create(label=''):
    """Write a new backup and return its path."""
    m = sc.find_mariadb()
    if not m:
        raise sc.ServerError('The database program is not installed. Run Setup first.')
    os.makedirs(BACKUPS, exist_ok=True)
    name = 'ffxi-%s%s.sql.gz' % (time.strftime('%Y%m%d-%H%M%S'), ('-' + re.sub(r'[^A-Za-z0-9_-]', '', label)) if label else '')
    path = os.path.join(BACKUPS, name)
    cfg = sc.load_config()
    with _Database():
        argv, cleanup = sc._client_cmd(m, cfg, database=False)
        try:
            cmd = [_tool(m), argv[1], '--no-create-info', '--skip-triggers', '--replace', '--single-transaction', '--hex-blob', cfg['db_name']] + tables()
            r = subprocess.run(cmd, capture_output=True, creationflags=sc.NO_WINDOW, env=m.get('env'))
        finally:
            cleanup()
    if r.returncode != 0:
        raise sc.ServerError('The backup failed: ' + r.stderr.decode('utf-8', 'replace').strip()[:300])
    with gzip.open(path + '.part', 'wb') as f:
        f.write(r.stdout)
    os.replace(path + '.part', path)
    return path


def listing():
    """[(path, size in bytes, modified time)], newest first."""
    if not os.path.isdir(BACKUPS):
        return []
    out = []
    for n in os.listdir(BACKUPS):
        if n.endswith('.sql.gz'):
            p = os.path.join(BACKUPS, n)
            out.append((p, os.path.getsize(p), os.path.getmtime(p)))
    return sorted(out, key=lambda x: -x[2])


def restore(path):
    """Replace the player data with the backup's. A backup of the current data is made first. The game servers must be off."""
    if sc.status()['any'] and sc.status()['xi_map']:
        raise sc.ServerError('Stop the server first, then restore.')
    try:
        data = gzip.open(path, 'rb').read()
    except OSError:
        raise sc.ServerError('That file is not a backup this app made.')
    if b'REPLACE INTO' not in data and b'INSERT INTO' not in data and len(data) > 2000:
        raise sc.ServerError('That file does not look like a player data backup.')
    safety = create('before-restore')
    script = ('SET FOREIGN_KEY_CHECKS=0;\n' + ''.join('DELETE FROM `%s`;\n' % t for t in tables())).encode() + data + b'\nSET FOREIGN_KEY_CHECKS=1;\n'
    with _Database():
        sc.sql('SELECT 1', stdin_bytes=b'SELECT 1;')                        # fail early if the login does not work
        sc.sql('', stdin_bytes=script)
    return safety


# ---------------------------------------------------------------- automatic daily backups
AUTO_LABEL = 'auto'
DAY = 24 * 3600


def auto_settings():
    cfg = sc.load_config()
    return bool(cfg.get('auto_backup', False)), max(1, min(60, int(cfg.get('backup_keep', 7) or 7)))


def save_auto_settings(on, keep):
    keep = max(1, min(60, int(keep)))
    cfg = sc.load_config()
    cfg['auto_backup'], cfg['backup_keep'] = bool(on), keep
    sc.save_config(cfg)


def auto_due(now=None):
    """True when automatic backups are on and the newest backup (of any kind) is more than a day old."""
    on, _ = auto_settings()
    if not on:
        return False
    items = listing()
    return not items or (now or time.time()) - items[0][2] > DAY


def prune(keep):
    """Delete the oldest automatic backups beyond `keep`. Backups made by hand are never deleted."""
    autos = [x for x in listing() if x[0].endswith('-%s.sql.gz' % AUTO_LABEL)]
    for path, _, _ in autos[keep:]:
        try:
            os.remove(path)
        except OSError:
            pass


def auto_backup():
    """Make one automatic backup and tidy the old ones. Returns the path."""
    path = create(AUTO_LABEL)
    prune(auto_settings()[1])
    return path
