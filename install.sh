#!/bin/bash
# Installs the Chromium/Electron dead-key workaround described in README.md.
#
# Detects pacman (Arch/Manjaro), apt (Debian/Ubuntu), or dnf (Fedora) and
# installs accordingly - see README.md's Requirements table for exact
# package availability per distro/release. Only the pacman path has been
# tested end-to-end; apt/dnf use verified package names but are otherwise
# unverified - please open an issue if something's wrong for your distro.
#
# Requires systemd, and either Wayland or X11 (auto-detected via
# WAYLAND_DISPLAY - if unset, assumes X11 and installs xclip instead of
# wl-clipboard).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_BIN="/usr/local/bin/type-accent.sh"

if [ -n "${WAYLAND_DISPLAY:-}" ]; then
  CLIPBOARD_PKG="wl-clipboard"
else
  CLIPBOARD_PKG="xclip"
  echo "No WAYLAND_DISPLAY detected - assuming X11 and installing xclip instead of wl-clipboard."
  echo "(X11 support is less tested than Wayland - see README's Known limitations.)"
fi

if command -v pacman >/dev/null; then
  echo "== Installing packages via pacman: keyd $CLIPBOARD_PKG ydotool python-evdev =="
  sudo pacman -S --needed keyd "$CLIPBOARD_PKG" ydotool python-evdev
elif command -v apt >/dev/null; then
  echo "== Installing packages via apt: keyd $CLIPBOARD_PKG ydotool python3-evdev =="
  echo "   (keyd needs Debian 13/trixie+ or Ubuntu 25.10/questing+ - see README if this fails)"
  sudo apt update
  sudo apt install -y keyd "$CLIPBOARD_PKG" ydotool python3-evdev
elif command -v dnf >/dev/null; then
  echo "== keyd isn't in Fedora's official repos - enabling the alternateved/keyd COPR =="
  sudo dnf copr enable -y alternateved/keyd
  echo "== Installing packages via dnf: keyd $CLIPBOARD_PKG ydotool python3-evdev =="
  sudo dnf install -y keyd "$CLIPBOARD_PKG" ydotool python3-evdev
else
  echo "No supported package manager found (pacman/apt/dnf)." >&2
  echo "Install keyd, $CLIPBOARD_PKG, ydotool, and python-evdev manually (see README's" >&2
  echo "Requirements table), then run generate-keyd-config.py yourself and follow the" >&2
  echo "manual steps in README.md." >&2
  exit 1
fi

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
