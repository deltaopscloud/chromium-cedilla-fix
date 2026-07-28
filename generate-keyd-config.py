#!/usr/bin/env python3
"""
Generates /etc/keyd/default.conf content that reimplements a single dead-key
(TRIGGER_KEY below - defaults to apostrophe/dead_acute, as used by the
us(intl) XKB variant) entirely inside keyd, routing the characters in
SCRIPT_ACCENTS through type-accent.sh and letting everything else
(including NATIVE_COMPOSE_LETTERS) delegate back to the OS's own dead-key
handling via a plain keyd macro().

This pattern generalizes to ANY single physical key that acts as a dead key
in your layout (dead_acute, dead_grave, dead_tilde, dead_diaeresis, ...) -
set TRIGGER_KEY/TRIGGER_CHAR below to match yours. It does NOT generalize to
multi-key Compose sequences (e.g. a dedicated Compose/Multi_key key followed
by two or more characters) - this script only models "one dead key, then
one letter".

Why does a character belong in SCRIPT_ACCENTS vs NATIVE_COMPOSE_LETTERS?
Two independent reasons to route through type-accent.sh's clipboard-paste
trick instead of a native `macro($TRIGGER_KEY <letter>)` replay:

1. Chromium bug: Chromium ignores custom ~/.XCompose overrides, so a
   character that collides with a system default (e.g. dead_acute+c
   defaulting to "ć" instead of your intended "ç") never composes correctly
   in Chrome/Electron no matter what - only the clipboard-paste trick
   sidesteps that. ('c' is here for this reason.)
2. Ambient-Shift bug: `macro($TRIGGER_KEY <letter>)` re-emits the physical
   trigger keycode, and if Shift is held for an uppercase letter, that
   Shift also applies to the synthetic trigger-key emission - under
   us(intl), apostrophe unshifted is dead_acute but apostrophe *shifted* is
   dead_diaeresis, so Shift+e can produce "Ë" instead of "É". This has
   nothing to do with Chromium - it happens in every app, and is an
   unavoidable side effect of keyd owning the trigger key at all. It
   affects every letter in NATIVE_COMPOSE_LETTERS equally, but each one
   only gets moved to SCRIPT_ACCENTS if getting Shift+uppercase right for
   it is worth the latency/rolling-typing cost - a per-letter judgment
   call, not an automatic one. ('e' is here for this reason, as the letter
   that actually came up in practice; 'a'/'i'/'o'/'u' are equally affected
   but kept on the fast native path.)

type-accent.sh sidesteps the Shift bug entirely because it decides the
character from Shift state up front and pastes it directly - it never
"replays" a modifiable keycode, so there's no ambient-modifier interaction
to go wrong. (Two attempts to fix the native-replay path's Shift handling
via a *different* synthetic device both failed - see git history around
compose-native.sh if curious why.)

The trade-off: type-accent.sh costs ~130ms of latency per keystroke and
can't reliably support "rolling" fast typing (releasing the trigger key
before the next key) because of an open keyd bug in its tap/hold detection
(github.com/rvaiya/keyd/issues/756). NATIVE_COMPOSE_LETTERS pays neither
cost but keeps the Shift+uppercase risk - move a letter to SCRIPT_ACCENTS
if that risk matters more than speed for it.

Usage:
    python3 generate-keyd-config.py /usr/local/bin/type-accent.sh > default.conf
"""
import sys

# The physical key that acts as your dead key, and the literal character it
# normally produces on its own (used for the double-tap and post-space
# fallback cases below). Run `keyd list-keys` for valid key names if yours
# isn't apostrophe. Common alternatives: 'grave' (` key, often dead_grave or
# dead_tilde on intl layouts), 'equal', 'minus' - whatever your layout uses.
TRIGGER_KEY = "apostrophe"
TRIGGER_CHAR = "'"

# Characters routed through type-accent.sh's clipboard-paste trick - see the
# module docstring for the two reasons a letter ends up here.
SCRIPT_ACCENTS = {
    'c': ('ç', 'Ç'),
    'e': ('é', 'É'),
    'a': ('á', 'Á'),
    'i': ('í', 'Í'),
    'o': ('ó', 'Ó'),
    'u': ('ú', 'Ú'),
}

# Characters that already compose correctly via the OS's native dead-key
# handling (in every app, Chromium included) - kept fast and rolling-tolerant
# by delegating back to it instead of reimplementing them here. Shares the
# same Shift+uppercase risk as any letter here - see module docstring. Empty
# for now: every vowel this project actually uses turned out to need the
# Shift fix once tested (Shift+a/i/o/u produced Ä/Ï/Ö/Ü, the same bug e had).
NATIVE_COMPOSE_LETTERS = []

FALLBACK_LETTERS = [
    c for c in "bdfghjklmnpqrstvwxyz"
    if c not in SCRIPT_ACCENTS and c not in NATIVE_COMPOSE_LETTERS
]
DIGITS = list("1234567890")
PUNCT = {
    'comma': ',', 'dot': '.', 'semicolon': ';', 'slash': '/', 'minus': '-',
    'equal': '=', 'leftbrace': '[', 'rightbrace': ']', 'backslash': '\\', 'grave': '`',
}


def esc(ch):
    return ch.replace('\\', '\\\\')


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <path-to-type-accent.sh>", file=sys.stderr)
        sys.exit(1)
    script = sys.argv[1]
    t = TRIGGER_CHAR

    print("[ids]")
    print("*")
    print()
    print("[main]")
    print(f"{TRIGGER_KEY} = oneshot(cedilla)")
    print()
    print("[cedilla]")
    print(f"space = macro({esc(t)} space)")   # dead-key + space => literal trigger char, then a real space
    print(f"{TRIGGER_KEY} = macro({esc(t)}{esc(t)})")   # dead-key + dead-key => two literal trigger chars
    print("backspace = backspace")    # let Backspace cancel the pending accent, not type anything
    print("esc = esc")
    print("tab = tab")
    print("delete = delete")
    print("left = left")
    print("right = right")
    print("up = up")
    print("down = down")
    print(f"enter = macro({esc(t)}enter)")
    for k, (lo, hi) in SCRIPT_ACCENTS.items():
        print(f'{k} = command({script} "{lo}" "{hi}")')
    for k in NATIVE_COMPOSE_LETTERS:
        print(f"{k} = macro({TRIGGER_KEY} {k})")
    for k in FALLBACK_LETTERS:
        print(f"{k} = macro({esc(t)}{k})")
    for d in DIGITS:
        print(f"{d} = macro({esc(t)}{d})")
    for name, ch in PUNCT.items():
        print(f"{name} = macro({esc(t)}{esc(ch)})")


if __name__ == "__main__":
    main()
