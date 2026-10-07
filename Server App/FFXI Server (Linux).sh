#!/bin/bash
# FFXI Server for Linux. Fan Project by Habex. Opens the server window.
# Needs Python 3 with Tk (Debian/Ubuntu: sudo apt install python3-tk). The first run also adds
# "FFXI Server" to your applications menu.
HERE="$(cd "$(dirname "$0")" && pwd)"
PYAPP="$HERE/app/ffxi_server_app.py"
say() { (command -v zenity >/dev/null && zenity --error --title="FFXI Server" --text="$1" 2>/dev/null) || \
        (command -v kdialog >/dev/null && kdialog --error "$1" 2>/dev/null) || echo "$1"; }
[ -f "$PYAPP" ] || { say "The app's files were not found. Keep this file inside the Server App folder."; exit 1; }
PY=""
for c in "$(command -v python3)" /usr/bin/python3 /usr/local/bin/python3; do
  [ -n "$c" ] && [ -x "$c" ] && "$c" -c "import tkinter" >/dev/null 2>&1 && { PY="$c"; break; }
done
[ -n "$PY" ] || { say "The FFXI Server window needs Python 3 with Tk (one small package). Install it from a terminal:
  Ubuntu, Debian, Mint:  sudo apt install python3-tk
  Fedora:                sudo dnf install python3-tkinter
  Arch, Manjaro:         sudo pacman -S tk
then open FFXI Server again."; exit 1; }
# applications menu entry with this folder's real path (so it works wherever the release folder is)
"$PY" - "$HERE/FFXI Server (Linux).sh" <<'PYEOF' 2>/dev/null
import os, sys
p = sys.argv[1]
q = '"' + ''.join('\\' + c if c in '"`$\\' else c for c in p) + '"'
q = q.replace('\\', '\\\\')
d = os.path.expanduser('~/.local/share/applications')
os.makedirs(d, exist_ok=True)
with open(os.path.join(d, 'ffxi-2016-server.desktop'), 'w') as f:
    f.write('[Desktop Entry]\nType=Application\nName=FFXI Server\nComment=FFXI 2016 Server. Fan Project by Habex\n'
            'Exec=bash ' + q + '\nIcon=' + os.path.join(os.path.dirname(p), 'app', 'icon.png') + '\nTerminal=false\nCategories=Game;\n')
PYEOF
LOGDIR="$(dirname "$HERE")/Server/data/logs"; mkdir -p "$LOGDIR" 2>/dev/null || LOGDIR=/tmp
exec "$PY" "$PYAPP" "$@" >>"$LOGDIR/server_app.log" 2>&1
