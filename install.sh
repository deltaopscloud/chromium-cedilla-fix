#!/bin/bash
# Installs the Chromium/Electron dead-key workaround described in README.md.
#
# Assumes an Arch-based distro (pacman) with a KDE/GNOME-style Wayland
# session where systemd manages the user session. Tested on Manjaro KDE
# Plasma Wayland with the us(intl) XKB variant.
set -euo pipefail

if ! command -v pacman >/dev/null; then
  echo "This installer uses pacman (Arch/Manjaro). Install keyd, wl-clipboard," >&2
  echo "ydotool, and python-evdev manually for other distros, then run" >&2
  echo "generate-keyd-config.py yourself and follow the manual steps in README.md." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_BIN="/usr/local/bin/type-accent.sh"

echo "== Installing packages: keyd wl-clipboard ydotool python-evdev =="
sudo pacman -S --needed keyd wl-clipboard ydotool python-evdev

echo "== Installing $INSTALL_BIN =="
sudo install -Dm755 "$SCRIPT_DIR/type-accent.sh" "$INSTALL_BIN"

echo "== Installing shift-state-daemon.py (tracks Shift key state for fast case detection) =="
sudo install -Dm755 "$SCRIPT_DIR/shift-state-daemon.py" /usr/local/bin/shift-state-daemon.py
sudo rm -f /dev/shm/keyd-shift-state   # in case a stale file with the wrong owner exists
sudo cp "$SCRIPT_DIR/keyd-shift-state.service" /etc/systemd/system/keyd-shift-state.service
sudo systemctl daemon-reload
sudo systemctl enable --now keyd-shift-state

if [ -f /etc/keyd/default.conf ]; then
  BACKUP="/etc/keyd/default.conf.bak.$(date +%s 2>/dev/null || echo pre-install)"
  echo "== Existing /etc/keyd/default.conf found, backing up to $BACKUP =="
  sudo cp /etc/keyd/default.conf "$BACKUP"
fi

echo "== Generating /etc/keyd/default.conf =="
python3 "$SCRIPT_DIR/generate-keyd-config.py" "$INSTALL_BIN" | sudo tee /etc/keyd/default.conf >/dev/null
sudo keyd check /etc/keyd/default.conf

echo "== Adding $USER to the input group (may not be necessary on systems with uaccess ACLs) =="
sudo usermod -aG input "$USER"

echo "== Enabling keyd (system service) =="
sudo systemctl enable --now keyd

echo "== Enabling ydotool (user service) =="
systemctl --user enable --now ydotool.service

echo
echo "Done."
echo "If ydotool key events silently fail, log out and back in (group membership"
echo "needs a fresh login session on some systems)."
echo
echo "Test it: press apostrophe, release, then press 'c' -> should type 'ç'."
echo "See README.md to customize which characters are remapped."
