#!/usr/bin/env python3
"""
Generates /etc/keyd/default.conf content that reimplements the apostrophe
dead-key (dead_acute, as used by the us(intl) XKB variant) entirely inside
keyd, routing ONLY the specific characters broken by Chromium's XCompose
bug through type-accent.sh - everything else (including the other accented
vowels) delegates back to the OS's own, already-working dead-key handling.

Why does delegating back to the OS matter? The clipboard-paste trick in
type-accent.sh has real costs: ~130ms of latency per keystroke, and it
can't reliably support "rolling" fast typing (releasing apostrophe before
the next key) because of an open keyd bug in its tap/hold detection
(github.com/rvaiya/keyd/issues/756). The OS's native XCompose engine has
neither problem - it's a plain keysym state machine, not tap/hold-based.
So only characters that Chromium's compose bug actually breaks should pay
that cost; everything else should stay on the fast, native path via
`macro(apostrophe <letter>)`, which re-emits the physical apostrophe
keycode (so the compositor's own keymap treats it as dead_acute again,
exactly as if keyd weren't intercepting it at all) followed by the letter.

An earlier version of this script routed ALL vowels through
type-accent.sh too, reasoning that once keyd owns the apostrophe key at
all, nothing else can compose. That's true for characters you explicitly
special-case, but it's *unnecessary* for characters that already survive
Chromium's bug - only `ç` did not. Don't repeat that mistake: keep
CEDILLA_ACCENTS scoped to exactly the characters you've confirmed break in
Chromium, and put everything else (including other accented letters you
use) in NATIVE_COMPOSE_LETTERS.

Usage:
    python3 generate-keyd-config.py /usr/local/bin/type-accent.sh > default.conf
"""
import sys

# Characters that Chromium's XCompose bug actually breaks (colliding with a
# system default, e.g. dead_acute+c defaults to "ć" not "ç"). Only these pay
# the ~130ms clipboard-paste cost and lose rolling-typing support. Add here
# ONLY if you've confirmed the character is broken in Chromium - see README.
CEDILLA_ACCENTS = {
    'c': ('ç', 'Ç'),
}

# Characters that already compose correctly via the OS's native dead_acute
# handling (in every app, Chromium included) - kept fast and rolling-tolerant
# by delegating back to it instead of reimplementing them here.
NATIVE_COMPOSE_LETTERS = ['e', 'a', 'i', 'o', 'u']

FALLBACK_LETTERS = [
    c for c in "bdfghjklmnpqrstvwxyz"
    if c not in CEDILLA_ACCENTS and c not in NATIVE_COMPOSE_LETTERS
]
DIGITS = list("1234567890")
PUNCT = {
    'comma': ',', 'dot': '.', 'semicolon': ';', 'slash': '/', 'minus': '-',
    'equal': '=', 'leftbrace': '[', 'rightbrace': ']', 'backslash': '\\', 'grave': '`',
}


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <path-to-type-accent.sh>", file=sys.stderr)
        sys.exit(1)
    script = sys.argv[1]

    print("[ids]")
    print("*")
    print()
    print("[main]")
    print("apostrophe = oneshot(cedilla)")
    print()
    print("[cedilla]")
    print("space = macro(' space)")   # dead_acute + space => literal apostrophe, then a real space
    print("apostrophe = macro('')")   # dead_acute + dead_acute => two literal apostrophes
    print("backspace = backspace")    # let Backspace cancel the pending accent, not type anything
    print("esc = esc")
    print("tab = tab")
    print("delete = delete")
    print("left = left")
    print("right = right")
    print("up = up")
    print("down = down")
    print("enter = macro('enter)")
    for k, (lo, hi) in CEDILLA_ACCENTS.items():
        print(f'{k} = command({script} "{lo}" "{hi}")')
    for k in NATIVE_COMPOSE_LETTERS:
        print(f"{k} = macro(apostrophe {k})")
    for k in FALLBACK_LETTERS:
        print(f"{k} = macro('{k})")
    for d in DIGITS:
        print(f"{d} = macro('{d})")
    for name, ch in PUNCT.items():
        esc = ch.replace('\\', '\\\\')
        print(f"{name} = macro('{esc})")


if __name__ == "__main__":
    main()
