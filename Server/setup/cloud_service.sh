#!/bin/bash
# Run on a Linux cloud server after "Setup Linux.sh": opens the game ports in ufw and starts the server at boot.
# usage: sudo ./cloud_service.sh          (remove it again with: sudo ./cloud_service.sh remove)
set -e
if [ "$(id -u)" != 0 ]; then echo "Run this with sudo."; exit 1; fi
HERE="$(cd "$(dirname "$0")/.." && pwd)"                  # the Server folder
USER_NAME="${SUDO_USER:-root}"
UNIT=/etc/systemd/system/ffxi2016.service
if [ "$1" = remove ]; then
  systemctl disable --now ffxi2016 2>/dev/null || true
  rm -f "$UNIT"; systemctl daemon-reload
  echo "Removed. The firewall rules were left as they are."; exit 0
fi
if command -v ufw >/dev/null 2>&1; then
  for rule in 54001/tcp 54240/udp 54242/tcp 54460/tcp; do ufw allow "$rule" >/dev/null; done
  echo "Opened TCP 54001, UDP 54240, TCP 54242, TCP 54460 in ufw."
else
  echo "ufw is not installed, so no firewall rules were added here. Open those four ports yourself if this machine has a firewall."
fi
PY="$(command -v python3)"
cat > "$UNIT" <<UNITFILE
[Unit]
Description=FFXI 2016 server
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=$USER_NAME
WorkingDirectory=$HERE
ExecStart=$PY $HERE/server_control.py start
ExecStop=$PY $HERE/server_control.py stop
TimeoutStartSec=600

[Install]
WantedBy=multi-user.target
UNITFILE
systemctl daemon-reload
systemctl enable ffxi2016
echo "Installed. Start it now with: sudo systemctl start ffxi2016   (check with: python3 $HERE/server_control.py status)"
echo "Do not forget the cloud provider's own firewall (see CLOUD.txt)."
