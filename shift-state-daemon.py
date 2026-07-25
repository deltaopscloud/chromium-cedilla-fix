#!/usr/bin/env python3
"""
Keeps /dev/shm/keyd-shift-state updated with '1' while any physical Shift
key is held, '0' otherwise. Runs continuously so type-accent.sh can check
Shift state with a plain file read instead of paying Python-interpreter-
plus-evdev-import startup cost (~50-60ms) on every single keystroke.

Must run as root (see the systemd unit): reading /dev/input/event* requires
either the 'input' group (which needs a fresh login to take effect after
usermod) or root, and this avoids depending on the former.
"""
import evdev
import glob
import select
import time

STATE_FILE = "/dev/shm/keyd-shift-state"
SHIFT_CODES = {42, 54}  # KEY_LEFTSHIFT, KEY_RIGHTSHIFT


def write_state(held):
    try:
        with open(STATE_FILE, "w") as f:
            f.write("1" if held else "0")
    except OSError:
        pass


def main():
    devices = {}
    held = set()
    write_state(False)

    while True:
        for path in glob.glob('/dev/input/event*'):
            if path not in devices:
                try:
                    devices[path] = evdev.InputDevice(path)
                except OSError:
                    pass

        if not devices:
            time.sleep(1)
            continue

        try:
            ready, _, _ = select.select(devices.values(), [], [], 1.0)
        except (OSError, ValueError):
            # A device likely disappeared; drop everything and rediscover.
            devices.clear()
            time.sleep(0.5)
            continue

        for dev in ready:
            try:
                for event in dev.read():
                    if event.type == evdev.ecodes.EV_KEY and event.code in SHIFT_CODES:
                        if event.value == 1:
                            held.add(event.code)
                        elif event.value == 0:
                            held.discard(event.code)
                        write_state(bool(held))
            except OSError:
                devices.pop(dev.path, None)


if __name__ == "__main__":
    main()
