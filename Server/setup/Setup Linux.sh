#!/bin/bash
# FFXI 2016 Server: one time setup for Linux (Fan Project by Habex).
# Usually only Python's window toolkit is installed: the release comes with the database and the game server
# programs for 64-bit Intel/AMD Linux. On other processors (e.g. ARM) it installs the database program (MariaDB)
# and the build tools, then builds the game servers (20-60 minutes). Asks for your password (sudo).
cd "$(dirname "$0")/.." || exit 1
SERVER="$(pwd)"
echo
echo "  FFXI 2016 Server setup for Linux"
echo "  Fan Project by Habex"
echo "  ----------------------------------"
echo
pause() { read -r -p "Press Return to close this window."; }
# Usually NOT needed on a 64-bit Intel/AMD PC: the release comes with the database and the game server programs.
# Then only Python's window toolkit (Tk) may be missing.
if [ "$(uname -m)" = "x86_64" ] && [ -x "$SERVER/programs/linux/xi_map" ] && [ -x "$SERVER/programs/linux/mariadb/bin/mariadbd" ]; then
  echo "This computer uses the database and game server programs that come with the release."
  if ! python3 -c "import tkinter" >/dev/null 2>&1; then
    echo "Installing Python's window toolkit (asks for your password)..."
    if command -v apt-get >/dev/null; then sudo apt-get install -y python3 python3-tk
    elif command -v dnf >/dev/null; then sudo dnf install -y python3 python3-tkinter
    elif command -v pacman >/dev/null; then sudo pacman -S --needed --noconfirm python tk
    elif command -v zypper >/dev/null; then sudo zypper install -y python3 python3-tk
    else echo "Install Python 3 with Tk (tkinter) with your system's package manager."; fi
  fi
  echo
  python3 "$SERVER/server_control.py" check
  echo
  echo "The server uses these network ports. Allow them in your firewall if it is on:"
  echo "  TCP 54001, 54242, 54460 and UDP 54240   (Ubuntu: sudo ufw allow 54001/tcp  ... etc.)"
  echo
  echo "Setup is finished. Go back to the FFXI Server window and click \"Check again\"."
  pause; exit 0
fi
echo "This computer is not a 64-bit Intel/AMD PC, so the game servers are built here (20-60 minutes)."
echo
if command -v apt-get >/dev/null; then
  sudo apt-get update
  sudo apt-get install -y git python3 python3-tk python3-venv python3-pip cmake ninja-build pkg-config libluajit-5.1-dev \
       libzmq3-dev libssl-dev zlib1g-dev libzstd-dev libdwarf-dev mariadb-server mariadb-client libmariadb-dev-compat binutils-dev \
       || { echo "Installing packages did not work."; pause; exit 1; }
  for v in 15 14 13; do sudo apt-get install -y "g++-$v" >/dev/null 2>&1 && { export CC="gcc-$v" CXX="g++-$v"; break; }; done
  [ -z "$CXX" ] && sudo apt-get install -y g++
elif command -v dnf >/dev/null; then
  sudo dnf install -y git python3 python3-tkinter gcc-c++ cmake ninja-build pkgconf luajit-devel zeromq-devel openssl-devel \
       zlib-devel libzstd-devel libdwarf-devel mariadb-server mariadb mariadb-connector-c-devel binutils-devel \
       || { echo "Installing packages did not work."; pause; exit 1; }
elif command -v pacman >/dev/null; then
  sudo pacman -S --needed --noconfirm git python tk gcc cmake ninja pkgconf luajit zeromq openssl zlib zstd libdwarf mariadb binutils \
       || { echo "Installing packages did not work."; pause; exit 1; }
elif command -v zypper >/dev/null; then
  sudo zypper install -y git python3 python3-tk gcc-c++ cmake ninja pkg-config luajit-devel zeromq-devel libopenssl-devel \
       zlib-devel libzstd-devel libdwarf-devel mariadb mariadb-client libmariadb-devel binutils-devel \
       || { echo "Installing packages did not work."; pause; exit 1; }
else
  echo "This Linux is not one this setup knows (it knows apt, dnf, pacman, zypper)."
  echo "Install by hand: MariaDB server + client, Python 3 with tkinter, and the LandSandBoat build tools"
  echo "(see Server/lsb/docs/wiki/Quick-Start-Guide.md), then run Server/setup/build_server_programs.sh"
  pause; exit 1
fi
echo
echo "Building the game server programs (20-60 minutes)..."
bash "$SERVER/setup/build_server_programs.sh" || { echo "The build did not finish. See the messages above."; pause; exit 1; }
echo
python3 "$SERVER/server_control.py" check
echo
echo "The server uses these network ports. Allow them in your firewall if it is on:"
echo "  TCP 54001, 54242, 54460 and UDP 54240   (Ubuntu: sudo ufw allow 54001/tcp  ... etc.)"
echo
echo "Setup is finished. Go back to the FFXI Server window and click \"Check again\"."
pause
