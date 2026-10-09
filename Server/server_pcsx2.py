"""Start PCSX2 with the patched disc (FFXI 2016 Server, Fan Project by Habex).

PCSX2 (version 2 and newer) is started with:   PCSX2 -batch -- "<disc file>"
  -batch   opens the game straight away and closes PCSX2 when the game is closed (no game list window)
  --       everything after it is the disc file, even if its name starts with a dash
The hard drive is not part of the command: it is chosen once in PCSX2's own settings (the Game disc page explains it).
"""
import glob
import os
import shutil
import subprocess
import sys

import server_control as sc

ISO_NAME = 'FFXI 2016 (Patched).iso'
ISO = os.path.join(sc.RELEASE, 'Disc', 'Patched ISO', ISO_NAME)
FLATPAK_ID = 'net.pcsx2.PCSX2'


def _bundle_exe(path):
    """A macOS .app folder -> the program inside it."""
    if path.lower().endswith('.app') and os.path.isdir(path):
        macos = os.path.join(path, 'Contents', 'MacOS')
        for name in ('PCSX2', 'pcsx2-qt'):
            if os.path.isfile(os.path.join(macos, name)):
                return os.path.join(macos, name)
        try:
            files = [f for f in sorted(os.listdir(macos)) if os.access(os.path.join(macos, f), os.X_OK)]
        except OSError:
            files = []
        return os.path.join(macos, files[0]) if files else None
    return path


def _usable(path):
    path = _bundle_exe(path) if path else None
    return path if path and os.path.isfile(path) and os.access(path, os.X_OK) else None


def candidates():
    """Places PCSX2 usually lives, most likely first."""
    out = []
    home = os.path.expanduser('~')
    if sc.MAC:
        for base in ('/Applications', os.path.join(home, 'Applications')):
            out += sorted(glob.glob(os.path.join(base, 'PCSX2*.app')), reverse=True)
    elif sc.WINDOWS:
        roots = [os.environ.get(k) for k in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA', 'USERPROFILE')]
        for root in filter(None, roots):
            for sub in ('PCSX2', os.path.join('Programs', 'PCSX2'), 'PCSX2-qt', os.path.join('Downloads', 'PCSX2')):
                for exe in ('pcsx2-qt.exe', 'pcsx2.exe'):
                    out.append(os.path.join(root, sub, exe))
    else:
        for name in ('pcsx2-qt', 'pcsx2', 'PCSX2'):
            found = shutil.which(name)
            if found:
                out.append(found)
        for base in (home, os.path.join(home, 'Applications'), os.path.join(home, 'Downloads'), '/opt', '/usr/local/bin'):
            out += sorted(glob.glob(os.path.join(base, '[Pp][Cc][Ss][Xx]2*.[Aa]pp[Ii]mage')), reverse=True)
    return out


def flatpak_installed():
    if sc.WINDOWS or sc.MAC or not shutil.which('flatpak'):
        return False
    return any(os.path.isdir(p) for p in (os.path.expanduser('~/.var/app/' + FLATPAK_ID), '/var/lib/flatpak/app/' + FLATPAK_ID,
                                           os.path.expanduser('~/.local/share/flatpak/app/' + FLATPAK_ID)))


def find():
    """The command start (a list) for PCSX2, or None. The place the player picked once (server_config.json) wins."""
    saved = sc.load_config().get('pcsx2_path')
    if saved:
        exe = _usable(saved)
        if exe:
            return [exe]
    for c in candidates():
        exe = _usable(c)
        if exe:
            return [exe]
    if flatpak_installed():
        return ['flatpak', 'run', FLATPAK_ID]
    return None


def remember(path):
    """Save the program the player picked. Returns the program path, or raises ServerError when it cannot be started."""
    exe = _usable(path)
    if not exe:
        raise sc.ServerError('That is not a program that can be started. Pick PCSX2 itself (on a Mac, the PCSX2 app).')
    cfg = sc.load_config()
    cfg['pcsx2_path'] = path
    sc.save_config(cfg)
    return exe


def command(start, iso=ISO):
    """The full command line."""
    return list(start) + ['-batch', '--', iso]


def is_running():
    """True when PCSX2 is already open (a second copy would fight over the hard drive file)."""
    try:
        if sc.WINDOWS:
            out = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True, creationflags=sc.NO_WINDOW).stdout
            return any(l.lower().startswith('"pcsx2') for l in out.splitlines())
        r = subprocess.run(['pgrep', '-if', r'/(pcsx2|pcsx2-qt)( |$)|^(pcsx2|pcsx2-qt)( |$)'], capture_output=True, text=True)
        return bool(r.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return False


def launch(popen=subprocess.Popen, iso=ISO):
    """Starts PCSX2 with the patched disc. Returns the command that was run. Raises ServerError with a plain message when it cannot.
    (`popen` can be swapped by tests so nothing is really started.)"""
    if not os.path.isfile(iso):
        raise sc.ServerError('The patched disc is not there yet. Use "1. Make the disc" above first (it should end up in Disc > Patched ISO as '
                             '"%s").' % ISO_NAME)
    start = find()
    if not start:
        raise NeedProgram()
    if is_running():
        raise sc.ServerError('PCSX2 is already open. Close it first, then press the button again.')
    cmd = command(start, iso)
    kw = {'stdin': subprocess.DEVNULL, 'stdout': subprocess.DEVNULL, 'stderr': subprocess.DEVNULL}
    if sc.WINDOWS:
        kw['creationflags'] = 0x00000008 | sc.NO_WINDOW               # DETACHED_PROCESS
    else:
        kw['start_new_session'] = True
    try:
        popen(cmd, **kw)
    except OSError as e:
        raise sc.ServerError('PCSX2 could not be started (%s). Pick it again with "Choose PCSX2...".' % e)
    return cmd


class NeedProgram(sc.ServerError):
    """PCSX2 was not found: the player has to pick it once."""
    def __init__(self):
        super().__init__('PCSX2 was not found on this computer. Pick it once and it is remembered.')
