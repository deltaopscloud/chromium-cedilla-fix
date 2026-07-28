#!/usr/bin/env python3
"""
Generates /etc/keyd/default.conf content that reimplements a single dead-key
(TRIGGER_KEY below - defaults to apostrophe/dead_acute, as used by the
us(intl) XKB variant) entirely inside keyd, routing ONLY the specific
characters broken by Chromium's XCompose bug through type-accent.sh -
everything else (including other accented letters you use with the same
dead key) delegates back to the OS's own, already-working dead-key
handling.

This pattern generalizes to ANY single physical key that acts as a dead key
in your layout (dead_acute, dead_grave, dead_tilde, dead_diaeresis, ...) -
set TRIGGER_KEY/TRIGGER_CHAR below to match yours. It does NOT generalize to
multi-key Compose sequences (e.g. a dedicated Compose/Multi_key key followed
by two or more characters) - this script only models "one dead key, then
one letter".

Why does delegating back to the OS matter? The clipboard-paste trick in
type-accent.sh has real costs: ~130ms of latency per keystroke, and it
can't reliably support "rolling" fast typing (releasing the trigger key
before the next key) because of an open keyd bug in its tap/hold detection
(github.com/rvaiya/keyd/issues/756). The OS's native XCompose engine has
neither problem - it's a plain keysym state machine, not tap/hold-based.
So only characters that Chromium's compose bug actually breaks should pay
that cost; everything else should stay on the fast, native path via
`macro($TRIGGER_KEY <letter>)`, which re-emits the physical trigger keycode
(so the compositor's own keymap treats it as a dead key again, exactly as
if keyd weren't intercepting it at all) followed by the letter.

Known trade-off of this native path: `macro($TRIGGER_KEY <letter>)` doesn't
clear ambient modifiers, so holding Shift for an uppercase letter (e.g.
Shift+e for "É") also applies to the synthetic trigger-key emission - under
us(intl), apostrophe unshifted is dead_acute but apostrophe *shifted* is
dead_diaeresis, so this can produce "Ë" instead of "É".

Two attempts were made to fix this correctly and both failed for what
appears to be the same underlying reason: an external script
(compose-native.sh, since removed) tried to synthetically release Shift via
ydotool's own virtual device before re-emitting the trigger key. This
consistently failed to change the output (same failure mode as trying the
same trick around type-accent.sh's clipboard-paste for a different app).
The working theory: keyd's own virtual output device continuously forwards
your *real* Shift key's held state (keyd exclusively grabs the real
keyboard, so its virtual device is the sole source the compositor sees for
it), and a *separate* device (ydotool) asserting "Shift up" doesn't override
that - compositors appear to treat a modifier as held if any contributing
input device asserts it, not "most recent event wins". A fix would need to
happen through keyd's own output stream, not a separate synthetic device,
and keyd's macro() syntax has no documented way to clear/restore a
modifier's ambient state mid-macro. This project accepts the trade-off
(NATIVE_COMPOSE_LETTERS stays fast and simple, occasionally wrong on
Shift+letter) rather than continue chasing an unclear fix - see git history
if you want to pick this up.

An earlier version of this script routed ALL accented letters through
type-accent.sh, reasoning that once keyd owns the trigger key at all,
nothing else can compose. That's true for characters you explicitly
special-case, but it's *unnecessary* for characters that already survive
Chromium's bug. Don't repeat that mistake: keep CEDILLA_ACCENTS scoped to
exactly the characters you've confirmed break in Chromium, and put
everything else (including other accented letters you use) in
NATIVE_COMPOSE_LETTERS.

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

# Characters that Chromium's XCompose bug actually breaks (colliding with a
# system default, e.g. dead_acute+c defaults to "ç" not "ç"... er, "ć").
# Only these pay the ~130ms clipboard-paste cost and lose rolling-typing
# support. Add here ONLY if you've confirmed the character is broken in
# Chromium - see README.
CEDILLA_ACCENTS = {
    'c': ('ç', 'Ç'),
}

# Characters that already compose correctly via the OS's native dead-key
# handling (in every app, Chromium included) - kept fast and rolling-tolerant
# by delegating back to it instead of reimplementing them here. See the
# module docstring for the uppercase-with-Shift trade-off this implies.
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
    for k, (lo, hi) in CEDILLA_ACCENTS.items():
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
