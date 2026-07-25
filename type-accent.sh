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
#
# Works on both Wayland (wl-copy/wl-paste) and X11 (xclip), auto-detected.
# ydotool itself works identically on both since it operates at the
# uinput/evdev level below the display server - only the clipboard tool
# and its connection details differ.
set -euo pipefail

LOWER="$1"
UPPER="${2:-$1}"

# ydotoold's runtime dir is the one reliable anchor regardless of session
# type (Wayland vs X11), since ydotool doesn't care about the display server.
RUNTIME_DIR="$(find /run/user/*/.ydotool_socket 2>/dev/null | head -1 | xargs -r dirname)"
if [ -z "$RUNTIME_DIR" ]; then
  echo "type-accent.sh: no active session found under /run/user/*/.ydotool_socket (is ydotoold running?)" >&2
  exit 1
fi
export XDG_RUNTIME_DIR="$RUNTIME_DIR"
export YDOTOOL_SOCKET="$RUNTIME_DIR/.ydotool_socket"

if [ -e "$RUNTIME_DIR/wayland-0" ]; then
  SESSION_TYPE="wayland"
  export WAYLAND_DISPLAY="wayland-0"
elif command -v xclip >/dev/null 2>&1; then
  SESSION_TYPE="x11"
  # Best-effort: DISPLAY/XAUTHORITY discovery varies a lot across display
  # managers. This covers common cases; set them yourself via environment
  # if your setup isn't found automatically (see README's X11 notes).
  if [ -z "${DISPLAY:-}" ]; then
    X11_SOCKET="$(ls /tmp/.X11-unix/X* 2>/dev/null | head -1)"
    [ -n "$X11_SOCKET" ] && export DISPLAY=":${X11_SOCKET##*/X}"
  fi
  if [ -z "${XAUTHORITY:-}" ]; then
    for candidate in "$RUNTIME_DIR"/gdm/Xauthority "$HOME"/.Xauthority /var/run/lightdm/root/:0; do
      if [ -f "$candidate" ]; then
        export XAUTHORITY="$candidate"
        break
      fi
    done
  fi
else
  echo "type-accent.sh: no Wayland session and no xclip found for X11 - install wl-clipboard or xclip" >&2
  exit 1
fi

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

if [ "$SESSION_TYPE" = "wayland" ]; then
  OLD="$(wl-paste -n 2>/dev/null || true)"
  printf '%s' "$CHAR" | wl-copy
else
  OLD="$(xclip -selection clipboard -o 2>/dev/null || true)"
  printf '%s' "$CHAR" | xclip -selection clipboard
fi

# Force-release Shift first: if the real Shift key is still physically held
# (as it naturally is right after typing an uppercase letter), our Ctrl+V
# would arrive as Ctrl+Shift+V instead - many apps (WPS Office, etc.) treat
# that as "paste special/unformatted" instead of a normal paste, so nothing
# visibly happens.
ydotool key 42:0 54:0 29:1 47:1 47:0 29:0   # leftshift up, rightshift up, leftctrl down, v down, v up, leftctrl up
sleep 0.05

if [ "$SESSION_TYPE" = "wayland" ]; then
  if [ -n "$OLD" ]; then
    printf '%s' "$OLD" | wl-copy
  else
    wl-copy -c
  fi
else
  if [ -n "$OLD" ]; then
    printf '%s' "$OLD" | xclip -selection clipboard
  else
    printf '' | xclip -selection clipboard
  fi
fi
