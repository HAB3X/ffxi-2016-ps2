#!/bin/bash
# FFXI Server.app (Fan Project by Habex): opens the server window (Server App/app/ffxi_server_app.py) with a Python 3
# that has Tk. Keep this app inside the "Server App" folder, next to the "Server" folder.
APP="$(cd "$(dirname "$0")/../.." && pwd)"          # .../FFXI Server.app
HERE="$(dirname "$APP")"                            # .../Server App
PYAPP="$HERE/app/ffxi_server_app.py"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
oops() { osascript -e "display dialog \"$1\" with title \"FFXI Server - Fan Project by Habex\" buttons {\"OK\"} default button 1 with icon caution" >/dev/null 2>&1; exit 1; }
[ -f "$PYAPP" ] || oops "The app's files were not found. Keep FFXI Server inside the Server App folder (with the app folder next to it)."
PY=""
CANDS=(/Library/Frameworks/Python.framework/Versions/Current/bin/python3 /Library/Frameworks/Python.framework/Versions/3.*/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3)
xcode-select -p >/dev/null 2>&1 && CANDS+=(/usr/bin/python3)    # Apple's own Python only if the developer tools are there
for c in "${CANDS[@]}"; do
  [ -x "$c" ] && "$c" -c "import tkinter" >/dev/null 2>&1 && { PY="$c"; break; }
done
if [ -z "$PY" ]; then
  osascript -e 'display dialog "Python 3 is needed to open the FFXI Server window.\n\nInstall it from python.org (the big yellow Download button), then open FFXI Server again." with title "FFXI Server - Fan Project by Habex" buttons {"Open python.org", "OK"} default button 1 with icon caution' 2>/dev/null | grep -q "python.org" && open "https://www.python.org/downloads/"
  exit 1
fi
LOG="$(dirname "$HERE")/Server/data/logs/server_app.log"
mkdir -p "$(dirname "$LOG")" 2>/dev/null
( : >>"$LOG" ) 2>/dev/null || LOG="${TMPDIR:-/tmp}/ffxi_server_app.log"   # macOS may block the Downloads folder until you allow it
# On Apple M-series Macs, run Python natively (if the app was opened under Rosetta the server programs look "missing")
# (an Intel-only Python is left as it is: it still works, Rosetta runs it)
if [ "$(/usr/sbin/sysctl -n hw.optional.arm64 2>/dev/null)" = "1" ] && /usr/bin/arch -arm64 "$PY" -c "" >/dev/null 2>&1; then
  exec /usr/bin/arch -arm64 "$PY" "$PYAPP" "$@" >>"$LOG" 2>&1
fi
exec "$PY" "$PYAPP" "$@" >>"$LOG" 2>&1
