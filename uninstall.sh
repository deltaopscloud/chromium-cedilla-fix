#!/bin/bash
# Reverses install.sh: stops/disables the services and removes the files it
# created. Leaves keyd/wl-clipboard/ydotool/python-evdev packages installed
# (in case you use them for something else) - remove those yourself with
# `sudo pacman -Rns keyd wl-clipboard ydotool python-evdev` if you want them gone too.
set -euo pipefail

echo "== Disabling ydotool (user service) =="
systemctl --user disable --now ydotool.service || true

echo "== Disabling keyd-shift-state (system service) =="
sudo systemctl disable --now keyd-shift-state || true
sudo rm -f /etc/systemd/system/keyd-shift-state.service
sudo rm -f /dev/shm/keyd-shift-state
sudo systemctl daemon-reload

echo "== Disabling keyd (system service) =="
sudo systemctl disable --now keyd || true

echo "== Removing /etc/keyd/default.conf =="
sudo rm -f /etc/keyd/default.conf
LATEST_BACKUP="$(ls -t /etc/keyd/default.conf.bak.* 2>/dev/null | head -1 || true)"
if [ -n "$LATEST_BACKUP" ]; then
  echo "   A pre-install backup exists at: $LATEST_BACKUP"
  echo "   Restore it with: sudo cp '$LATEST_BACKUP' /etc/keyd/default.conf"
fi

echo "== Removing /usr/local/bin/type-accent.sh and shift-state-daemon.py =="
sudo rm -f /usr/local/bin/type-accent.sh /usr/local/bin/shift-state-daemon.py

echo
echo "Done. Your apostrophe key is back to normal OS-level dead-key handling."
echo "(Group membership in 'input' was left as-is; remove with"
echo " 'sudo gpasswd -d \$USER input' if you don't need it elsewhere.)"
