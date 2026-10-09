"""ffxi_updater.py: checks GitHub for newer scripts of this release and downloads them (Fan Project by Habex).

Only the small program and script files are updated (the Server App, the server scripts, the setup scripts, the disc tools and the read me).
The game server programs, the database, your players and settings, and the discs are never touched. A change that needs a new
disc or patch is not applied here: get that from the Releases page.

Server/VERSION.txt holds the commit this copy was built from. A check asks GitHub which files changed since then.
"""
import json, os, urllib.request

REPO = 'HAB3X/ffxi-2016-ps2'
BRANCH = 'main'
API = 'https://api.github.com/repos/%s' % REPO
RAW = 'https://raw.githubusercontent.com/%s' % REPO

FOLDERS = ('Server App/', 'Server/setup/', 'Server/proxy/', 'Server/admin/', 'Server/lsb/modules/', 'Game/Disc Builder/', 'Disc/Hard Drive/')
FILES = ('READ ME.txt', 'KNOWN BUGS.txt', 'Server/READ ME Server.txt')
KINDS = ('.py', '.bat', '.sh', '.command', '.txt', '.lua', '.md', '.template', '.json', '.desktop', '.png')
MAX_BYTES = 8 * 1024 * 1024


def wanted(path):
    """True for a file this updater may replace."""
    if '..' in path.split('/') or path.startswith('/'):
        return False
    ext = os.path.splitext(path)[1].lower()
    if ext not in KINDS or (ext == '.png' and not path.startswith('Server App/app/art/')):        # pictures only for the app's own art folder
        return False
    if path in FILES:
        return True
    if path.startswith('Server/') and path.count('/') == 1 and path.endswith('.py'):
        return True
    return path.startswith(FOLDERS)


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={'User-Agent': 'ffxi-2016-server-app', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(MAX_BYTES + 1)


def local_version(release_dir):
    try:
        with open(os.path.join(release_dir, 'Server', 'VERSION.txt'), encoding='utf-8') as f:
            return f.read().split()[0].strip()
    except (OSError, IndexError):
        return ''


def check(release_dir):
    """None when up to date (or it cannot be told); otherwise {'head': sha, 'files': [paths]}."""
    base = local_version(release_dir)
    if not base:
        return None
    head = json.loads(_get('%s/commits/%s' % (API, BRANCH)))['sha']
    if head.startswith(base) or base.startswith(head):
        return None
    cmp = json.loads(_get('%s/compare/%s...%s' % (API, base, head)))
    if cmp.get('status') in ('identical', 'behind'):
        return None
    files = sorted({f['filename'] for f in cmp.get('files', []) if f.get('status') != 'removed' and wanted(f['filename'])})
    if not files:
        _write_version(release_dir, head)           # nothing here changed: only note that this copy is current
        return None
    return {'head': head, 'files': files}


def _write_version(release_dir, sha):
    with open(os.path.join(release_dir, 'Server', 'VERSION.txt'), 'w', encoding='utf-8') as f:
        f.write(sha + '\n')


def apply(release_dir, info, progress=None):
    """Download every file of `info` first, then put them in place. Returns the number of files updated."""
    got = {}
    for i, path in enumerate(info['files']):
        if progress:
            progress(i, len(info['files']))
        data = _get('%s/%s/%s' % (RAW, info['head'], urllib.request.quote(path)), timeout=60)
        if len(data) > MAX_BYTES:
            raise ValueError('%s is larger than expected' % path)
        got[path] = data
    for path, data in got.items():
        dest = os.path.join(release_dir, *path.split('/'))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        tmp = dest + '.update'
        with open(tmp, 'wb') as f:
            f.write(data)
        try:
            os.chmod(tmp, os.stat(dest).st_mode if os.path.exists(dest) else (0o755 if path.endswith(('.sh', '.command')) else 0o644))
        except OSError:
            pass
        os.replace(tmp, dest)
    _write_version(release_dir, info['head'])
    return len(got)
