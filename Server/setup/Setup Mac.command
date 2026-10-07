#!/bin/bash
# FFXI 2016 Server: one time setup for a Mac (Fan Project by Habex).
# Usually NOT needed: the release comes with the database and the game server programs for Apple M-series and
# Intel Macs (macOS 13.3 or newer). This setup only installs what is still missing:
#   Python (for the server window), if there is none
#   On older macOS: the database program and the build tools (Homebrew), then builds the game servers (20-60 minutes)
# It never changes a database that is already running.
cd "$(dirname "$0")/.." || exit 1
SERVER="$(pwd)"
echo
echo "  FFXI 2016 Server setup for Mac"
echo "  Fan Project by Habex"
echo "  --------------------------------"
echo
done_close() { read -r -p "Press Return to close this window."; exit "${1:-0}"; }
# the Mac's own processor (an M-series Mac says arm64 even if this window runs under Rosetta)
if [ "$(/usr/sbin/sysctl -n hw.optional.arm64 2>/dev/null)" = "1" ]; then ARCH=arm64; PDIR=mac-arm64; else ARCH=x86_64; PDIR=mac-intel; fi
OSV="$(sw_vers -productVersion)"; MAJ="${OSV%%.*}"; REST="${OSV#*.}"; MIN="${REST%%.*}"; [ "$REST" = "$OSV" ] && MIN=0
FITS=0
if [ "$MAJ" -gt 13 ] || { [ "$MAJ" -eq 13 ] && [ "${MIN:-0}" -ge 3 ]; }; then FITS=1; fi
INCLUDED=0
if [ "$FITS" = 1 ] && [ -x "$SERVER/programs/$PDIR/xi_map" ] && [ -x "$SERVER/programs/$PDIR/mariadb/bin/mariadbd" ]; then INCLUDED=1; fi

find_python() {
  PY=""
  for c in /Library/Frameworks/Python.framework/Versions/Current/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    [ -x "$c" ] && "$c" -c "import tkinter" >/dev/null 2>&1 && { PY="$c"; return 0; }
  done
  xcode-select -p >/dev/null 2>&1 && /usr/bin/python3 -c "import tkinter" >/dev/null 2>&1 && { PY=/usr/bin/python3; return 0; }
  return 1
}

if [ "$INCLUDED" = 1 ]; then
  echo "This Mac uses the database and game server programs that come with the release."
  if find_python; then
    echo
    "$PY" "$SERVER/server_control.py" check
    echo
    echo "Nothing to install. Go back to the FFXI Server window and click \"Check again\"."
    done_close 0
  fi
  echo
  echo "Only Python is missing (it opens the server window). Install it from python.org:"
  echo "click the big yellow Download button, open the file and click Continue until it is done."
  open "https://www.python.org/downloads/macos/"
  echo
  echo "Then open FFXI Server again."
  done_close 1
fi

echo "This Mac has macOS $OSV. The included server programs need macOS 13.3 or newer,"
echo "so this setup installs the database and builds the game servers here (20-60 minutes)."
echo
BREW=""
for b in /opt/homebrew/bin/brew /usr/local/bin/brew "$(command -v brew)"; do
  [ -n "$b" ] && [ -x "$b" ] && { BREW="$b"; break; }
done
if [ -z "$BREW" ]; then
  echo "Homebrew is not installed. Homebrew is the free tool this setup uses to install the database"
  echo "and the other pieces (see https://brew.sh)."
  echo
  read -r -p "Install Homebrew now? It will ask for your Mac password. (y/n) " ans
  if [ "$ans" != "y" ] && [ "$ans" != "Y" ]; then
    echo "Setup stopped. Install Homebrew from https://brew.sh, then run this setup again."; done_close 1
  fi
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || {
    echo "Homebrew did not install. Try again later or install it from https://brew.sh"; done_close 1; }
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && BREW="$b"; done
fi
eval "$("$BREW" shellenv)"
export HOMEBREW_NO_INSTALL_UPGRADE=1 HOMEBREW_NO_ENV_HINTS=1   # never upgrade something already installed (it may be in use)
NEED="mariadb zeromq luajit openssl@3 brotli zstd python-tk git cmake ninja pkgconf"
for f in $NEED; do
  if "$BREW" list --versions "$f" >/dev/null 2>&1; then echo "  ok      $f"
  else echo "  install $f"; "$BREW" install "$f" || { echo "Could not install $f. Check your internet connection and run setup again."; done_close 1; }
  fi
done
echo
echo "Building the game server programs (20-60 minutes)..."
bash "$SERVER/setup/build_server_programs.sh" || { echo "The build did not finish. See the messages above."; done_close 1; }
echo
if find_python || { PY="$("$BREW" --prefix)/bin/python3"; [ -x "$PY" ]; }; then
  "$PY" "$SERVER/server_control.py" check
  echo
  echo "Setup is finished. Go back to the FFXI Server window and click \"Check again\"."
else
  echo "Python with its window toolkit was not found. Install Python 3 from https://www.python.org/downloads/ and run setup again."
fi
done_close 0
