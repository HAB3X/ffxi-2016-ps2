#!/usr/bin/env python3
"""FFXI 2016 Release - server control (Fan Project by Habex).

Starts and stops everything the game needs, in this order:
    1. the database      (a private MariaDB that keeps its files in Server/data/database, port 3316)
    2. the game servers  (LandSandBoat: login, search, world, map)
    3. the PS2 login proxy (the part the PS2 game connects to, port 54001) in 2016 mode
    4. the friend-list service for the 2016 game (port 54460)

Python standard library only. Works on Mac, Windows and Linux. The Server App uses this file; it also works on its own:
    python3 server_control.py start | stop | status | check
    python3 server_control.py create-profile NAME          (asks for the password)
    python3 server_control.py name [NAME] | welcome [TEXT] | address [HOSTNAME-OR-IP]
    python3 server_control.py backup | backups | restore FILE

Nothing here prints a password. Data made while the server runs (database files, profiles, logs) goes to Server/data.
"""
import glob, gzip, json, os, re, secrets, shutil, signal, socket, string, subprocess, sys, time

SERVER = os.path.dirname(os.path.abspath(__file__))
RELEASE = os.path.dirname(SERVER)
LSB = os.path.join(SERVER, 'lsb')
PROXY_DIR = os.path.join(SERVER, 'proxy')
DATA = os.environ.get('FFXI_DATA_DIR') or os.path.join(SERVER, 'data')
LOGS = os.path.join(DATA, 'logs')
DB_DIR = os.path.join(DATA, 'database')
CONFIG = os.path.join(DATA, 'server_config.json')
STATE = os.path.join(DATA, 'running.json')
PLAYERS = os.path.join(DATA, 'players.txt')
MUTED = os.path.join(DATA, 'muted.txt')
WORLD_SQL = os.path.join(SERVER, 'database', 'ffxi_world.sql.gz')
NETWORK_TEMPLATE = os.path.join(LSB, 'settings', 'network.lua.template')
NETWORK_LUA = os.path.join(LSB, 'settings', 'network.lua')

WINDOWS = os.name == 'nt'
MAC = sys.platform == 'darwin'
OS_NAME = 'windows' if WINDOWS else 'mac' if MAC else 'linux'
EXE = '.exe' if WINDOWS else ''
NO_WINDOW = 0x08000000 if WINDOWS else 0                   # CREATE_NO_WINDOW
NEW_GROUP = 0x00000200 if WINDOWS else 0                   # CREATE_NEW_PROCESS_GROUP

# Ports. FFXI_PORT_OFFSET is only for testing next to another server on the same computer; players never need it.
OFFSET = int(os.environ.get('FFXI_PORT_OFFSET') or 0)
PORTS = {k: v + OFFSET for k, v in dict(
    lobby=54001,         # PS2 game -> login proxy (the "ServerPort" players type)
    relay=54240,         # PS2 game -> proxy, game world traffic (UDP)
    search=54242,        # PS2 game -> proxy, search
    social=54460,        # 2016 game -> friend-list service
    data=54230,          # LandSandBoat login data (TCP) and map server (UDP)
    auth=54231,          # LandSandBoat login
    view=54011,          # LandSandBoat character list
    lsb_search=54002,    # LandSandBoat search
    zmq=54003,           # LandSandBoat world <-> map (this computer only)
    db=3316,             # the private database
).items()}
SERVER_PORT_FOR_PLAYERS = PORTS['lobby']

PROGRAMS = ['xi_connect', 'xi_search', 'xi_world', 'xi_map']
NICE = {'database': 'Database', 'xi_connect': 'Login server', 'xi_search': 'Search server', 'xi_world': 'World server',
        'xi_map': 'Map server (the game world)', 'proxy': 'PS2 login part (2016 game)', 'social': 'Friend list service'}
ORDER = ['database'] + PROGRAMS + ['proxy', 'social']


class ServerError(Exception):
    """A problem explained in plain words (shown to the player as it is)."""


def log_line(msg):
    os.makedirs(LOGS, exist_ok=True)
    with open(os.path.join(LOGS, 'server_control.log'), 'a', encoding='utf-8') as f:
        f.write(time.strftime('%Y-%m-%d %H:%M:%S ') + msg + '\n')


def _private_write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(text)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


# ---------------------------------------------------------------- settings kept in Server/data/server_config.json
def load_config():
    try:
        with open(CONFIG, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    _private_write(CONFIG, json.dumps(cfg, indent=1))


def ensure_config():
    cfg = load_config()
    changed = False
    if not cfg.get('db_password'):
        cfg['db_password'] = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24))
        changed = True
    for k, v in (('db_user', 'xiadmin'), ('db_name', 'xidb')):
        if cfg.get(k) != v:
            cfg[k] = v
            changed = True
    if cfg.get('db_port') != PORTS['db']:
        cfg['db_port'] = PORTS['db']
        changed = True
    if changed:
        save_config(cfg)
    return cfg


# ---------------------------------------------------------------- finding the programs on this computer
MAC_MIN = (13, 3)            # the included Mac programs run on macOS 13.3 (Ventura) or newer


def _machine_arch():
    """'arm64' or 'x86_64': the processor of this computer itself. On an Apple M-series Mac this says arm64 even when
    this Python runs translated by Rosetta (then platform.machine() would wrongly say x86_64)."""
    import platform
    m = (platform.machine() or '').lower()
    if MAC:
        try:
            r = subprocess.run(['/usr/sbin/sysctl', '-n', 'hw.optional.arm64'], capture_output=True, text=True, timeout=10)
            if r.stdout.strip() == '1':
                return 'arm64'
        except (OSError, subprocess.SubprocessError):
            pass
        return 'arm64' if m == 'arm64' else 'x86_64'
    if WINDOWS:
        m = (os.environ.get('PROCESSOR_ARCHITEW6432') or os.environ.get('PROCESSOR_ARCHITECTURE') or m).lower()
    return {'amd64': 'x86_64', 'x64': 'x86_64', 'x86-64': 'x86_64', 'aarch64': 'arm64'}.get(m, m)


ARCH = _machine_arch()


def _mac_version():
    try:
        r = subprocess.run(['/usr/bin/sw_vers', '-productVersion'], capture_output=True, text=True, timeout=10)
        return tuple(int(x) for x in r.stdout.strip().split('.')[:2])
    except (OSError, ValueError, subprocess.SubprocessError):
        return (99, 0)


def platform_dirs():
    """The folders in Server/programs with programs that run on this computer, best first."""
    if MAC:
        if _mac_version() < MAC_MIN:
            return []
        return ['mac-arm64', 'mac-intel'] if ARCH == 'arm64' else ['mac-intel']
    if WINDOWS:
        return ['windows']                  # 64-bit Windows 10 / 11 (Windows 11 on ARM runs them too)
    return ['linux'] if ARCH == 'x86_64' else []


def _included(*parts):
    return [os.path.join(SERVER, 'programs', d, *parts) for d in platform_dirs()]


def _first(paths):
    for p in paths:
        if p and os.path.isfile(p):
            return p
    return None


def _linux_has(lib):
    try:
        import ctypes
        ctypes.CDLL(lib)
        return True
    except OSError:
        return False


def _mariadb_in(base, bin_dirs):
    def look(names):
        return _first([os.path.join(d, n + EXE) for n in names for d in bin_dirs])
    srv = look(['mariadbd', 'mysqld'])
    inst = look(['mariadb-install-db', 'mysql_install_db'])
    cli = look(['mariadb', 'mysql'])
    if not (srv and inst and cli):
        return None
    env = None
    if base and not WINDOWS and not MAC:
        # Linux: two small stand-ins come with the included database, used only if this Linux lacks the real ones
        extra = [os.path.join(base, 'lib', 'fallback', sub) for lib, sub in (('libcrypt.so.1', 'libcrypt'), ('libsystemd.so.0', 'libsystemd'))
                 if os.path.isdir(os.path.join(base, 'lib', 'fallback', sub)) and not _linux_has(lib)]
        if extra:
            env = dict(os.environ)
            env['LD_LIBRARY_PATH'] = os.pathsep.join(extra + ([env['LD_LIBRARY_PATH']] if env.get('LD_LIBRARY_PATH') else []))
    return dict(server=srv, install=inst, client=cli, bin_dir=os.path.dirname(cli), base=base, env=env)


def find_mariadb():
    """dict(server=, install=, client=, bin_dir=, base=, env=) or None. The database that comes with the release
    (Server/programs/<this computer>/mariadb) first, then an installed MariaDB in the usual places of each OS."""
    for base in _included('mariadb'):
        m = _mariadb_in(base, [os.path.join(base, 'bin')])
        if m:
            return m
    dirs = []
    if WINDOWS:
        dirs.append(os.path.join(SERVER, 'tools', 'mariadb', 'bin'))
        for base in (os.environ.get('ProgramFiles', r'C:\Program Files'), os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'),
                     os.environ.get('ProgramW6432', r'C:\Program Files')):
            dirs += sorted(glob.glob(os.path.join(base, 'MariaDB*', 'bin')), reverse=True)
    elif MAC:
        dirs += ['/opt/homebrew/opt/mariadb/bin', '/usr/local/opt/mariadb/bin', '/opt/homebrew/bin', '/usr/local/bin',
                 '/usr/local/mariadb/bin', '/usr/local/mysql/bin']
    else:
        dirs += ['/usr/sbin', '/usr/bin', '/usr/local/sbin', '/usr/local/bin', '/usr/libexec']
    for name in ('mariadbd', 'mysqld', 'mariadb'):
        w = shutil.which(name)
        if w:
            dirs.append(os.path.dirname(os.path.realpath(w)))
            dirs.append(os.path.dirname(w))
    seen, uniq = set(), []
    for d in dirs:
        if d and d not in seen:
            seen.add(d)
            uniq.append(d)
    return _mariadb_in(None, uniq)


def program_path(name):
    """The LandSandBoat program for this computer: the included one (Server/programs/<this computer>/) first,
    then Server/lsb/ (where Setup's build lands)."""
    return _first(_included(name + EXE) + [os.path.join(LSB, name + EXE)])


def python_exe():
    """The Python that runs the proxy and the friend service (the same one that runs this file; never pythonw)."""
    exe = sys.executable or 'python3'
    if WINDOWS and os.path.basename(exe).lower() == 'pythonw.exe':
        cand = os.path.join(os.path.dirname(exe), 'python.exe')
        if os.path.exists(cand):
            exe = cand
    return exe


def mac_missing_libraries():
    """Mac: the Homebrew libraries that server programs built by Setup need. The included programs need none."""
    if not MAC:
        return []
    exe = program_path('xi_map')
    if not exe or not exe.startswith(os.path.join(LSB, '')):
        return []
    brew = '/opt/homebrew/opt/' if ARCH == 'arm64' else '/usr/local/opt/'
    need = ['mariadb/lib/libmariadb.3.dylib', 'zeromq/lib/libzmq.5.dylib', 'luajit/lib/libluajit-5.1.2.dylib',
            'openssl@3/lib/libssl.3.dylib', 'brotli/lib/libbrotlidec.1.dylib', 'zstd/lib/libzstd.1.dylib']
    return [n.split('/')[0] for n in need if not os.path.exists(brew + n)]


def check_setup():
    """List of (ok, text) lines about what this computer has. Everything ok = the server can start."""
    out = []
    if sys.version_info < (3, 8):
        out.append((False, 'Python 3.8 or newer is needed (this is %d.%d).' % sys.version_info[:2]))
    m = find_mariadb()
    out.append((bool(m), 'Database program (MariaDB) found' if m else 'Database program (MariaDB) is not installed yet'))
    missing = [p for p in PROGRAMS if not program_path(p)]
    if not missing:
        out.append((True, 'Game server programs for this computer found'))
    elif MAC and _mac_version() < MAC_MIN:
        out.append((False, 'The included server programs need macOS 13.3 or newer (this Mac has %d.%d). Setup builds new ones'
                    % _mac_version()))
    elif not WINDOWS and not MAC and ARCH != 'x86_64':
        out.append((False, 'The included server programs are for 64-bit Intel/AMD processors (this computer is %s). Setup builds new ones' % ARCH))
    else:
        out.append((False, 'Game server programs for %s are missing (Server/programs)' % {'mac': 'Mac', 'windows': 'Windows', 'linux': 'Linux'}[OS_NAME]))
    if MAC and not missing:
        libs = mac_missing_libraries()
        if libs:
            out.append((False, 'Mac libraries missing: ' + ', '.join(libs)))
    out.append((os.path.exists(WORLD_SQL) or world_ready(), 'World database file found' if os.path.exists(WORLD_SQL) else 'World database file is missing (Server/database/ffxi_world.sql.gz)'))
    out.append((os.path.exists(os.path.join(PROXY_DIR, 'ps2proxy.py')), 'PS2 login part found'))
    return out


def setup_ok():
    return all(ok for ok, _ in check_setup())


# ---------------------------------------------------------------- processes we started (Server/data/running.json)
def _load_state():
    try:
        with open(STATE, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_state(st):
    os.makedirs(DATA, exist_ok=True)
    with open(STATE, 'w', encoding='utf-8') as f:
        json.dump(st, f, indent=1)


def _pid_alive(pid, exe_hint=None):
    if not pid:
        return False
    if WINDOWS:
        r = subprocess.run(['tasklist', '/FI', 'PID eq %d' % pid, '/FO', 'CSV', '/NH'], capture_output=True, text=True,
                           creationflags=NO_WINDOW)
        line = r.stdout.strip()
        if not line.startswith('"'):
            return False
        image = line.split('","')[0].strip('"').lower()
        return not exe_hint or image[:20] == os.path.basename(exe_hint).lower()[:20]
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:                                                     # a zombie (our own finished child) is not alive
        r = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)], capture_output=True, text=True)
        if r.stdout.strip().startswith('Z'):
            try:
                os.waitpid(pid, os.WNOHANG)
            except OSError:
                pass
            return False
    except OSError:
        pass
    if exe_hint:
        r = subprocess.run(['ps', '-ww', '-o', 'command=', '-p', str(pid)], capture_output=True, text=True)
        cmd = r.stdout.strip()
        return bool(cmd) and os.path.basename(exe_hint) in cmd
    return True


def _hint(info):
    return (info.get('image') if WINDOWS else info.get('match')) if info else None


def is_running(part):
    st = _load_state().get(part)
    return bool(st) and _pid_alive(st.get('pid'), _hint(st))


def _spawn(part, argv, cwd, log_name, env=None, match=None):
    os.makedirs(LOGS, exist_ok=True)
    logf = open(os.path.join(LOGS, log_name), 'ab')
    kw = dict(cwd=cwd, stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env)
    if WINDOWS:
        kw['creationflags'] = NO_WINDOW | NEW_GROUP
    else:
        kw['start_new_session'] = True
    p = subprocess.Popen(argv, **kw)
    logf.close()
    st = _load_state()
    st[part] = dict(pid=p.pid, match=match or argv[0], image=os.path.basename(argv[0]), started=time.time())
    _save_state(st)
    log_line('started %s (pid %d)' % (part, p.pid))
    return p


def _kill(pid, force=False):
    if WINDOWS:
        subprocess.run(['taskkill', '/PID', str(pid)] + (['/F', '/T'] if force else []), capture_output=True, creationflags=NO_WINDOW)
    else:
        try:
            os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
        except OSError:
            pass


def _stop_part(part, wait=30):
    st = _load_state()
    info = st.get(part)
    if info and _pid_alive(info.get('pid'), _hint(info)):
        pid = info['pid']
        _kill(pid, force=WINDOWS and part != 'database')     # Windows: hidden console programs ignore a polite close
        for _ in range(wait * 4):
            if not _pid_alive(pid, _hint(info)):
                break
            time.sleep(0.25)
        if _pid_alive(pid, _hint(info)):
            _kill(pid, force=True)
            time.sleep(0.5)
        log_line('stopped %s' % part)
    st = _load_state()
    st.pop(part, None)
    _save_state(st)


# ---------------------------------------------------------------- ports
def port_free(port, udp=False):
    """TCP: nothing is listening on it. UDP: it can be taken."""
    if not udp:
        return not port_answers(port)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind(('0.0.0.0', port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def port_answers(port, host='127.0.0.1'):
    try:
        socket.create_connection((host, port), timeout=0.5).close()
        return True
    except OSError:
        return False


def busy_ports(parts):
    """Ports that something else (not us) already uses, for the parts we are about to start."""
    need = {'database': [('db', False)], 'xi_connect': [('data', False), ('auth', False), ('view', False)],
            'xi_search': [('lsb_search', False)], 'xi_world': [('zmq', False)], 'xi_map': [('data', True)],
            'proxy': [('lobby', False), ('relay', True), ('search', False)], 'social': [('social', False)]}
    out = []
    for part in parts:
        for key, udp in need[part]:
            if not port_free(PORTS[key], udp):
                out.append('%d%s' % (PORTS[key], ' (UDP)' if udp else ''))
    return out


# ---------------------------------------------------------------- this computer's address on the home network
def lan_address():
    """The address other computers/PS2s on the same network use to reach this one ('' if not connected)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('192.0.2.1', 9))               # no packet is sent; this only picks the outgoing network card
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith('127.') and not ip.startswith('0.'):
            return ip
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith('127.'):
                return ip
    except OSError:
        pass
    return ''


# ---------------------------------------------------------------- the database
def _client_cmd(m, cfg, database=True):
    """mariadb client command with a private option file (password never on the command line). Returns (argv, cleanup)."""
    import tempfile
    fd, path = tempfile.mkstemp(prefix='ffxi-db-', suffix='.cnf')
    with os.fdopen(fd, 'w') as f:
        f.write('[client]\nhost=127.0.0.1\nport=%d\nuser=%s\npassword="%s"\nprotocol=TCP\ndefault-character-set=utf8mb4\nmax_allowed_packet=256M\n'
                % (cfg['db_port'], cfg['db_user'], cfg['db_password']))
    argv = [m['client'], '--defaults-extra-file=' + path]
    if database:
        argv.append(cfg['db_name'])

    def cleanup():
        try:
            os.remove(path)
        except OSError:
            pass
    return argv, cleanup


def sql(q, args=(), cfg=None, m=None, database=True, stdin_bytes=None):
    """Run SQL with the release database login; returns rows (lists of str, NULL -> None)."""
    sys.path.insert(0, PROXY_DIR)
    from lsb_db import bind                                  # same quoting rules as the proxy's helper
    cfg = cfg or load_config()
    m = m or find_mariadb()
    if not m:
        raise ServerError('The database program (MariaDB) is not installed. Run Setup first.')
    argv, cleanup = _client_cmd(m, cfg, database)
    try:
        data = stdin_bytes if stdin_bytes is not None else bind(q, args).encode('utf-8')
        r = subprocess.run(argv + ['-N', '-B', '--raw'], input=data, capture_output=True, creationflags=NO_WINDOW, env=m.get('env'))
    finally:
        cleanup()
    if r.returncode != 0:
        err = r.stderr.decode('utf-8', 'replace').strip()
        try:
            with open(os.path.join(LOGS, 'database_setup.log'), 'a', encoding='utf-8') as f:
                f.write(err[-4000:] + '\n')
        except OSError:
            pass
        raise ServerError('Database error: ' + err[:400])
    return [[None if v == 'NULL' else v for v in line.split('\t')] for line in r.stdout.decode('utf-8', 'replace').splitlines()]


def db_ready(cfg=None, m=None):
    if not port_answers(PORTS['db']):
        return False
    try:
        sql('SELECT 1', cfg=cfg, m=m)
        return True
    except ServerError:
        return False


def world_ready(cfg=None, m=None):
    try:
        r = sql("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name IN ('zone_settings','accounts','item_basic')",
                cfg=cfg, m=m)
        return int(r[0][0]) == 3
    except Exception:
        return False


def _init_database_files(m, say):
    """First start: make the empty database folder (Server/data/database)."""
    if os.path.isdir(os.path.join(DB_DIR, 'mysql')):
        return
    say('Making the database (first start only)...')
    os.makedirs(DB_DIR, exist_ok=True)
    tries = [[m['install'], '--datadir=' + DB_DIR]] if WINDOWS else [
        [m['install'], '--no-defaults', '--datadir=' + DB_DIR, '--basedir=' + m['base'], '--auth-root-authentication-method=normal',
         '--skip-test-db', '--skip-name-resolve']] if m.get('base') else [
        [m['install'], '--no-defaults', '--datadir=' + DB_DIR, '--auth-root-authentication-method=normal', '--skip-test-db'],
        [m['install'], '--no-defaults', '--datadir=' + DB_DIR, '--auth-root-authentication-method=normal'],
        [m['install'], '--no-defaults', '--datadir=' + DB_DIR, '--basedir=' + os.path.dirname(os.path.dirname(m['server']))],
        [m['install'], '--no-defaults', '--datadir=' + DB_DIR]]
    last = ''
    for argv in tries:
        r = subprocess.run(argv, capture_output=True, text=True, creationflags=NO_WINDOW, env=m.get('env'))
        if os.path.isdir(os.path.join(DB_DIR, 'mysql')):
            log_line('database folder made with: ' + os.path.basename(argv[0]))
            return
        last = (r.stdout + r.stderr)[-600:]
    with open(os.path.join(LOGS, 'database_setup.log'), 'a', encoding='utf-8') as f:
        f.write(last + '\n')
    raise ServerError('Could not make the database. Details are in Server/data/logs/database_setup.log.')


def start_database(say=print):
    cfg = ensure_config()
    m = find_mariadb()
    if not m:
        raise ServerError('The database program (MariaDB) is not installed. Run Setup first (Server/setup).')
    cfg['mariadb_bin_dir'] = m['bin_dir']
    save_config(cfg)
    if is_running('database') and db_ready(cfg, m):
        return cfg, m
    busy = busy_ports(['database'])
    if busy and not is_running('database'):
        raise ServerError('Another program is already using port %s (the database port). Another server is already running '
                          'on this computer - close it first.' % busy[0])
    _init_database_files(m, say)
    # every start makes sure the server's own login exists with the password from server_config.json
    init = os.path.join(DATA, 'db_init.sql')
    pw = cfg['db_password']
    _private_write(init, (
        "CREATE DATABASE IF NOT EXISTS `xidb` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;\n"
        "CREATE USER IF NOT EXISTS 'xiadmin'@'127.0.0.1' IDENTIFIED BY '%s';\n"
        "CREATE USER IF NOT EXISTS 'xiadmin'@'localhost' IDENTIFIED BY '%s';\n"
        "ALTER USER 'xiadmin'@'127.0.0.1' IDENTIFIED BY '%s';\n"
        "ALTER USER 'xiadmin'@'localhost' IDENTIFIED BY '%s';\n"
        "GRANT ALL PRIVILEGES ON `xidb`.* TO 'xiadmin'@'127.0.0.1';\n"
        "GRANT ALL PRIVILEGES ON `xidb`.* TO 'xiadmin'@'localhost';\n"
        "GRANT SHUTDOWN, PROCESS ON *.* TO 'xiadmin'@'127.0.0.1';\n"
        "GRANT SHUTDOWN, PROCESS ON *.* TO 'xiadmin'@'localhost';\n"
        "FLUSH PRIVILEGES;\n") % (pw, pw, pw, pw))
    say('Starting the database...')
    argv = [m['server'], '--no-defaults', '--datadir=' + DB_DIR, '--port=%d' % PORTS['db'], '--bind-address=127.0.0.1',
            '--init-file=' + init, '--log-error=' + os.path.join(LOGS, 'database.err'), '--skip-name-resolve',
            '--character-set-server=utf8mb4', '--collation-server=utf8mb4_general_ci', '--max-connections=300', '--max-allowed-packet=256M',
            '--innodb-buffer-pool-size=256M', '--pid-file=' + os.path.join(DB_DIR, 'ffxi.pid')]
    if m.get('base'):                                        # the database that comes with the release
        argv += ['--basedir=' + m['base'], '--lc-messages-dir=' + os.path.join(m['base'], 'share'),
                 '--plugin-dir=' + os.path.join(m['base'], 'lib', 'plugin')]
    if not WINDOWS:
        import tempfile
        argv.append('--socket=' + os.path.join(tempfile.gettempdir(), 'ffxi-db-%d.sock' % PORTS['db']))
    _spawn('database', argv, DB_DIR, 'database.log', env=m.get('env'), match=m['server'])
    for _ in range(120):
        time.sleep(0.5)
        if db_ready(cfg, m):
            break
        if not is_running('database'):
            break
    try:
        os.remove(init)
    except OSError:
        pass
    if not db_ready(cfg, m):
        _stop_part('database', wait=5)
        raise ServerError('The database did not start. Details are in Server/data/logs/database.err.')
    if not world_ready(cfg, m):
        if not os.path.exists(WORLD_SQL):
            raise ServerError('The world database file is missing (Server/database/ffxi_world.sql.gz).')
        say('Loading the game world into the database (first start only, about a minute)...')
        with gzip.open(WORLD_SQL, 'rb') as f:
            data = f.read()
        sql('', cfg=cfg, m=m, stdin_bytes=data)
        if not world_ready(cfg, m):
            raise ServerError('Loading the game world did not work. Details are in Server/data/logs/database_setup.log and database.err.')
        log_line('world database loaded')
    return cfg, m


def stop_database():
    info = _load_state().get('database')
    if not info or not _pid_alive(info.get('pid'), _hint(info)):
        _stop_part('database')
        return
    try:
        sql('SHUTDOWN')                                      # clean stop (all platforms)
    except Exception:
        pass
    for _ in range(120):
        if not _pid_alive(info['pid'], _hint(info)):
            break
        time.sleep(0.25)
    _stop_part('database', wait=30)


# ---------------------------------------------------------------- LandSandBoat settings for this computer
def write_network_settings(cfg):
    src = NETWORK_TEMPLATE if os.path.exists(NETWORK_TEMPLATE) else NETWORK_LUA
    t = open(src, encoding='utf-8').read()

    def put(key, value):
        nonlocal t
        lit = "'%s'" % value if isinstance(value, str) else str(value)
        t, n = re.subn(r"(\b%s\s*=\s*)('[^']*'|\d+)" % key, lambda mm: mm.group(1) + lit, t, count=1)
        if not n:
            raise ServerError('Server/lsb/settings/network.lua.template is damaged (no %s).' % key)
    put('SQL_HOST', '127.0.0.1')
    put('SQL_PORT', cfg['db_port'])
    put('SQL_LOGIN', cfg['db_user'])
    put('SQL_PASSWORD', cfg['db_password'])
    put('SQL_DATABASE', cfg['db_name'])
    put('LOGIN_DATA_PORT', PORTS['data'])
    put('LOGIN_VIEW_PORT', PORTS['view'])
    put('LOGIN_AUTH_PORT', PORTS['auth'])
    put('MAP_PORT', PORTS['data'])
    put('SEARCH_PORT', PORTS['lsb_search'])
    put('ZMQ_PORT', PORTS['zmq'])
    _private_write(NETWORK_LUA, t)
    # the zone list in the database says where the map server listens
    sql('UPDATE zone_settings SET zoneip=?, zoneport=? WHERE zoneport<>0', ('127.0.0.1', PORTS['data']), cfg=cfg)


def _log_has(log_name, start_at, words):
    p = os.path.join(LOGS, log_name)
    try:
        with open(p, 'rb') as f:
            f.seek(start_at)
            t = f.read().decode('utf-8', 'replace')
    except OSError:
        return False
    return any(w in t for w in words)


def _log_size(log_name):
    try:
        return os.path.getsize(os.path.join(LOGS, log_name))
    except OSError:
        return 0


def start_program(name, say=print, wait=300):
    if is_running(name):
        return
    exe = program_path(name)
    if not exe:
        raise ServerError('The %s program is missing for this computer. Run Setup first.' % NICE[name])
    at = _log_size(name + '.log')
    say('Starting the %s...' % NICE[name].lower())
    env = dict(os.environ)
    env['FFXI_DATA_DIR'] = os.path.abspath(DATA)            # the map server's app files (message queue, roles) live in DATA
    if WINDOWS:
        env['PATH'] = os.path.dirname(exe) + os.pathsep + LSB + os.pathsep + env.get('PATH', '')
    _spawn(name, [exe], LSB, name + '.log', env=env, match=exe)
    if name == 'xi_map':
        st = _load_state()
        st['xi_map']['files_dir'] = os.path.abspath(DATA)
        _save_state(st)
    for _ in range(wait * 2):
        time.sleep(0.5)
        if _log_has(name + '.log', at, ('ready to work', 'Ready to work')):
            return
        if not is_running(name):
            break
    if is_running(name):
        log_line('%s is running but did not say "ready to work" within %d s' % (name, wait))
        return
    raise ServerError('The %s stopped while starting. Details are in Server/data/logs/%s.log.' % (NICE[name].lower(), name))


def map_files_dir():
    """Where the running map server reads the app's message queue and roles file: the data folder (servers started by
    this version), or Server/lsb (a map server started by an earlier version of the app)."""
    info = _load_state().get('xi_map') or {}
    return info.get('files_dir') or (os.path.abspath(DATA) if not is_running('xi_map') else LSB)


def ensure_players_file():
    if not os.path.exists(PLAYERS):
        _private_write(PLAYERS, '# Profiles made with the Server App: name, account, password. Keep this file private.\n')
    if not os.path.exists(MUTED):
        with open(MUTED, 'w', encoding='utf-8') as f:
            f.write('# character names whose chat is not passed on (one per line)\n')


def start_proxy(say=print):
    if is_running('proxy'):
        return
    ensure_players_file()
    say('Starting the PS2 login part (2016 game)...')
    logname = 'ps2proxy.log'
    at = _log_size(logname)
    env = {k: v for k, v in os.environ.items() if not k.startswith('PS2PROXY_')}
    env['PS2PROXY_EXCODE_2012'] = '0x0FFF'                                   # the 2016 game: every expansion lit
    env['PS2PROXY_NPC_MAP'] = os.path.join(PROXY_DIR, 'maps', 'npc_id_map_2016b.json')
    env['PS2PROXY_MUTE_FILE'] = MUTED
    env['FFXI_DATA_DIR'] = os.path.abspath(DATA)
    env['FFXI_BRIDGE_DIR'] = map_files_dir()
    env['PYTHONIOENCODING'] = 'utf-8'
    argv = [python_exe(), os.path.join(PROXY_DIR, 'ps2proxy.py'), '--players', PLAYERS,
            '--log', os.path.join(LOGS, logname), '--quiet', '--client', '2012', '--no-default-translations',
            '--translate', 'mp-tell-out', '--translate', 'servmes-empty', '--translate', 'soc-2016',
            '--translate', 'npc-ids', '--translate', 'text-2016', '--translate', 'soc-mute', '--translate', 'chat-rules',
            '--internet-ip-file', os.path.join(DATA, 'internet_ip.txt'),
            '--lsb-dir', LSB, '--lobby-port', str(PORTS['lobby']), '--udp-port', str(PORTS['relay']),
            '--search-port', str(PORTS['search']), '--auth-port', str(PORTS['auth']), '--data-port', str(PORTS['data']),
            '--view-port', str(PORTS['view']), '--map-port', str(PORTS['data']), '--lsb-search-port', str(PORTS['lsb_search'])]
    _spawn('proxy', argv, PROXY_DIR, 'ps2proxy.console.log', env=env, match='ps2proxy.py')
    for _ in range(60):
        time.sleep(0.5)
        if _log_has(logname, at, ('lobby listening on',)):
            return
        if not is_running('proxy'):
            break
    raise ServerError('The PS2 login part did not start. Details are in Server/data/logs/ps2proxy.console.log.')


def start_social(say=print):
    if is_running('social'):
        return
    say('Starting the friend list service...')
    env = dict(os.environ, FFXI_DATA_DIR=DATA, PYTHONIOENCODING='utf-8')
    argv = [python_exe(), os.path.join(PROXY_DIR, 'soc_service.py'), '--port', str(PORTS['social']),
            '--db', os.path.join(DATA, 'social.db'), '--players', PLAYERS, '--log', os.path.join(LOGS, 'soc_service.log')]
    _spawn('social', argv, PROXY_DIR, 'soc_service.console.log', env=env, match='soc_service.py')
    for _ in range(20):
        time.sleep(0.5)
        if port_answers(PORTS['social']):
            return
        if not is_running('social'):
            break
    log_line('friend list service did not answer (the game still works without it)')


# ---------------------------------------------------------------- keep the computer awake while the server is on
def start_keep_awake():
    if WINDOWS or is_running('awake'):
        return                                             # Windows: the Server App keeps the PC awake while it is open
    mp = (_load_state().get('xi_map') or {}).get('pid')
    if not mp:
        return
    if MAC and shutil.which('caffeinate'):
        _spawn('awake', ['caffeinate', '-ims', '-w', str(mp)], DATA, 'keep_awake.log', match='caffeinate')
    elif shutil.which('systemd-inhibit'):
        _spawn('awake', ['systemd-inhibit', '--what=sleep:idle', '--who=FFXI Server', '--why=FFXI server is on',
                         'tail', '--pid=%d' % mp, '-f', os.devnull], DATA, 'keep_awake.log', match='systemd-inhibit')


# ---------------------------------------------------------------- the whole server
def status():
    """dict(part -> True/False), plus 'on' (everything needed is running)."""
    st = {p: is_running(p) for p in ORDER}
    st['on'] = all(st[p] for p in ['database'] + PROGRAMS + ['proxy'])
    st['any'] = any(st[p] for p in ORDER)
    return st


def other_server_running():
    """True if something that is not ours holds the game's main port (e.g. another FFXI server on this computer)."""
    return not is_running('proxy') and not port_free(PORTS['lobby'])


def start(say=print):
    """Start everything in order. Raises ServerError with a plain message if something is wrong."""
    if not setup_ok():
        bad = [t for ok, t in check_setup() if not ok]
        raise ServerError('This computer is not set up yet: ' + '; '.join(bad) + '. Run Setup first.')
    todo = [p for p in ORDER if not is_running(p)]
    busy = busy_ports(todo)
    if busy:
        raise ServerError('Another server is already running on this computer. Close it first.\n'
                          '(These ports are in use: %s)' % ', '.join(busy))
    os.makedirs(LOGS, exist_ok=True)
    try:
        os.remove(os.path.join(DATA, 'stopped_on_purpose'))
    except OSError:
        pass
    log_line('start')
    cfg, m = start_database(say)
    write_network_settings(cfg)
    try:                                                     # roles for in-game GM commands (read by the lan_roles module)
        import server_roles
        server_roles.write_lua()
        import server_chat                                   # chat rules file (made with the defaults the first time)
        server_chat.load_rules()
    except Exception as e:                                   # noqa: BLE001
        log_line('roles file not written: %s' % e)
    for p in PROGRAMS:
        start_program(p, say)
    try:                                                     # the internet address for players outside the house
        import server_net
        server_net.public_address()
    except Exception as e:                                   # noqa: BLE001
        log_line('internet address not found: %s' % e)
    start_proxy(say)
    start_social(say)
    start_keep_awake()
    say('Server is ON')
    log_line('server is on')


def stop(say=print):
    log_line('stop')
    with open(os.path.join(DATA, 'stopped_on_purpose'), 'w') as f:
        f.write('yes\n')
    say('Stopping the PS2 login part...')
    _stop_part('proxy', wait=10)
    _stop_part('social', wait=5)
    for p in reversed(PROGRAMS):
        say('Stopping the %s...' % NICE[p].lower())
        _stop_part(p, wait=40 if p == 'xi_map' else 15)
    _stop_part('awake', wait=2)
    say('Stopping the database...')
    stop_database()
    say('Server is OFF')
    log_line('server is off')


def restart_map_if_down(say=print):
    """Map server watcher (the Server App calls it every few seconds): brings the map server back if it crashed."""
    if os.path.exists(os.path.join(DATA, 'stopped_on_purpose')):
        return False
    st = status()
    if st['database'] and st['xi_world'] and st['proxy'] and not st['xi_map']:
        log_line('map server was down: starting it again')
        start_program('xi_map', say)
        _stop_part('awake', wait=2)
        start_keep_awake()
        return True
    return False


# ---------------------------------------------------------------- profiles (game accounts)
NAME_RULE = re.compile(r'^[A-Za-z0-9]{3,15}$')
PASS_RULE = re.compile(r'^[A-Za-z0-9]{6,15}$')


def check_profile(name, password):
    if not NAME_RULE.match(name or ''):
        return 'The name must be 3 to 15 letters or numbers (no spaces or symbols).'
    if not PASS_RULE.match(password or ''):
        return 'The password must be 6 to 15 letters or numbers (no spaces or symbols).'
    return None


def list_profiles():
    if not db_ready():
        return None
    return [r[0] for r in sql('SELECT login FROM accounts ORDER BY id')]


def create_profile(name, password, say=print):
    """Make a game account. The database stores the password scrambled; players.txt keeps it for the PS2 login part."""
    why = check_profile(name, password)
    if why:
        raise ServerError(why)
    if not db_ready():
        start_database(say)
    if sql('SELECT 1 FROM accounts WHERE LOWER(login)=LOWER(?)', (name,)):
        raise ServerError('The name "%s" is taken already. Pick another one.' % name)
    accid = max(1000, int(sql('SELECT IFNULL(MAX(id),0) FROM accounts')[0][0] or 0) + 1)
    # PASSWORD() is the database's own scrambling; LandSandBoat accepts it and upgrades it at the first login
    sql('INSERT INTO accounts (id, login, password, timecreate, timelastmodify, status, priv) '
        'VALUES (?, ?, PASSWORD(?), NOW(), NOW(), 1, 1)', (accid, name, password))
    ensure_players_file()
    lines = open(PLAYERS, encoding='utf-8', errors='replace').read().splitlines()
    keep = [l for l in lines if not (l.strip() and not l.strip().startswith('#') and len(re.split(r'\s*,\s*', l.strip())) >= 2
                                     and re.split(r'\s*,\s*', l.strip())[1].lower() == name.lower())]
    keep.append('%s, %s, %s' % (name, name, password))
    _private_write(PLAYERS, '\n'.join(keep) + '\n')
    log_line('profile made: %s' % name)
    return accid


def set_profile_enabled(name, enabled):
    """Ban (enabled=False) or unban a profile. Nothing is deleted."""
    if not sql('SELECT 1 FROM accounts WHERE login=?', (name,)):
        raise ServerError('There is no profile called "%s".' % name)
    sql('UPDATE accounts SET status=? WHERE login=?', (1 if enabled else 2, name))
    log_line('profile %s: %s' % (name, 'unbanned' if enabled else 'banned'))


def change_password(name, password):
    if not PASS_RULE.match(password or ''):
        raise ServerError('The password must be 6 to 15 letters or numbers (no spaces or symbols).')
    if not sql('SELECT 1 FROM accounts WHERE login=?', (name,)):
        raise ServerError('There is no profile called "%s".' % name)
    sql('UPDATE accounts SET password=PASSWORD(?) WHERE login=?', (password, name))
    ensure_players_file()
    lines = open(PLAYERS, encoding='utf-8', errors='replace').read().splitlines()
    keep = [l for l in lines if not (l.strip() and not l.strip().startswith('#') and len(re.split(r'\s*,\s*', l.strip())) >= 2
                                     and re.split(r'\s*,\s*', l.strip())[1].lower() == name.lower())]
    keep.append('%s, %s, %s' % (name, name, password))
    _private_write(PLAYERS, '\n'.join(keep) + '\n')
    log_line('password changed for profile %s' % name)


# ---------------------------------------------------------------- command line
def main(argv):
    cmd = argv[1] if len(argv) > 1 else 'status'
    try:
        if cmd == 'start':
            start()
        elif cmd == 'stop':
            stop()
        elif cmd == 'status':
            st = status()
            print('Server is ON' if st['on'] else 'Server is OFF' + (' (partly on)' if st['any'] else ''))
            for p in ORDER:
                print('  %-28s %s' % (NICE[p], 'on' if st[p] else 'off'))
            print('  ServerIP   %s' % (lan_address() or '(not connected to a network)'))
            try:
                import server_net as sn, server_settings as ss
                print('  Server name %s' % ss.get()['name'])
                print('  Internet    %s' % (sn.public_address()[0] or 'not found'))
            except Exception:                                    # noqa: BLE001
                pass
            print('  ServerPort %d' % SERVER_PORT_FOR_PLAYERS)
            if other_server_running():
                print('  Note: another server is already using port %d on this computer.' % PORTS['lobby'])
        elif cmd == 'name':
            import server_settings as ss
            if len(argv) > 2:
                restart = ss.save(name=' '.join(argv[2:]))
                print('Server name saved: %s%s' % (ss.get()['name'], '. Restart the server to use it.' if restart and status()['any'] else '.'))
            else:
                print(ss.get()['name'])
        elif cmd == 'welcome':
            import server_settings as ss
            if len(argv) > 2:
                ss.save(welcome=' '.join(argv[2:]) if argv[2] != '-' else '')
                print('Welcome message saved. Players see it when they log in.')
            else:
                print(ss.get()['welcome'] or '(none)')
        elif cmd == 'address':
            import server_net as sn
            if len(argv) > 2:
                sn.set_manual_public_address('' if argv[2] == '-' else argv[2])
            ip, how = sn.public_address(refresh=True)
            print('%s (%s)' % (ip or 'not found', how))
        elif cmd == 'backup':
            import server_backup as sb
            print('Backup written: %s' % sb.create())
        elif cmd == 'backups':
            import server_backup as sb
            for p, size, t in sb.listing():
                print('%s  %7.1f KB  %s' % (time.strftime('%Y-%m-%d %H:%M', time.localtime(t)), size / 1024, os.path.basename(p)))
        elif cmd == 'restore':
            import server_backup as sb
            if len(argv) < 3:
                print('usage: server_control.py restore <backup file>')
                return 2
            print('Restored. The data from just before was saved as %s' % sb.restore(argv[2]))
        elif cmd == 'check':
            for ok, text in check_setup():
                print(('  OK   ' if ok else '  NO   ') + text)
        elif cmd == 'create-profile':
            import getpass
            name = argv[2] if len(argv) > 2 else input('Profile name (POL-ID): ').strip()
            pw = os.environ.get('FFXI_PW') or getpass.getpass('Password (you will not see it as you type): ')
            create_profile(name, pw)
            print('Profile "%s" made. In the game type  POL-ID: %s   Password: (the one you picked)   ServerIP: %s   ServerPort: %d'
                  % (name, name, lan_address() or '?', SERVER_PORT_FOR_PLAYERS))
        else:
            print(__doc__)
            return 2
    except ServerError as e:
        print(str(e))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
