#!/bin/bash
# Types $1 (or $2 if Shift is physically held right now) by briefly parking it
# on the clipboard and simulating a paste, then restores the previous clipboard.
# Used by keyd to work around Chromium/Electron ignoring custom XCompose
# dead-key sequences. keyd runs this as root, so the user session env vars
# must be set explicitly.
#
# Shift state is read from /dev/shm/keyd-shift-state, kept up to date by
# shift-state-daemon.py, instead of checking evdev inline here - spawning
# python3 + importing evdev fresh on every keystroke cost ~50-60ms, which
# was very noticeable while typing. Falls back to the slower inline check
# if the daemon isn't running for some reason.
set -euo pipefail

RUNTIME_DIR="$(find /run/user/*/wayland-0 2>/dev/null | head -1 | xargs -r dirname)"
if [ -z "$RUNTIME_DIR" ]; then
  echo "type-accent.sh: no active Wayland session found under /run/user/*/wayland-0" >&2
  exit 1
fi
export XDG_RUNTIME_DIR="$RUNTIME_DIR"
export WAYLAND_DISPLAY="wayland-0"
export YDOTOOL_SOCKET="$RUNTIME_DIR/.ydotool_socket"

LOWER="$1"
UPPER="${2:-$1}"

SHIFT_STATE_FILE="/dev/shm/keyd-shift-state"
if [ -r "$SHIFT_STATE_FILE" ]; then
  SHIFT_HELD="$(cat "$SHIFT_STATE_FILE" 2>/dev/null || echo 0)"
else
  SHIFT_HELD="$(python3 -c "
import evdev, glob, sys
SHIFT = {42, 54}  # KEY_LEFTSHIFT, KEY_RIGHTSHIFT
for p in glob.glob('/dev/input/event*'):
    try:
        d = evdev.InputDevice(p)
        if any(c in SHIFT for c in d.active_keys()):
            print(1); sys.exit(0)
    except Exception:
        pass
print(0)
" 2>/dev/null || echo 0)"
fi

if [ "$SHIFT_HELD" = "1" ]; then
  CHAR="$UPPER"
else
  CHAR="$LOWER"
fi

OLD="$(wl-paste -n 2>/dev/null || true)"
printf '%s' "$CHAR" | wl-copy
ydotool key 29:1 47:1 47:0 29:0   # leftctrl down, v down, v up, leftctrl up
sleep 0.05

if [ -n "$OLD" ]; then
  printf '%s' "$OLD" | wl-copy
else
  wl-copy -c
fi
