# chromium-deadkey-fix

Makes custom dead-key sequences (e.g. remapping `dead_acute + c` to type `ç`
instead of the default `ć`) actually work in Chrome, Claude Desktop, VS Code,
Slack, Discord, and every other Chromium/Electron app on Linux.

## The problem

Chromium has a long-standing, unresolved bug: it ignores custom
`~/.XCompose` dead-key sequences. It only recognizes a small, hardcoded set
of dead-key combinations, so any override you add to `~/.XCompose` is
silently dropped - only "native" toolkit apps (terminals, GTK apps using the
classic X11 compose path) honor it. No amount of editing, reordering, or
cache-clearing your `~/.XCompose` fixes this, because Chromium never reads
your override for a sequence it already has a built-in answer for.

Relevant upstream reports:
- [Chromium: Custom compose key sequences (.XCompose) do not work](https://issues.chromium.org/issues/40272818)
- [Chromium: XCompose ignored](https://issues.chromium.org/issues/41186472)
- [Electron: ignores XCompose settings when running natively on Wayland](https://github.com/electron/electron/issues/29345)
- [Ubuntu bug tracker, since 2014](https://bugs.launchpad.net/ubuntu/+source/chromium-browser/+bug/1309145)

## The fix

Since the fix can't happen inside Chromium, it happens *before* Chromium (or
any app) ever sees the keystrokes:

1. **[keyd](https://github.com/rvaiya/keyd)**, a low-level key-remapping
   daemon, intercepts the apostrophe key at the raw input-device level
   (`/dev/input`), before X11/Wayland/any app sees it.
2. Pressing apostrophe arms a one-shot layer. The next keypress determines
   what happens:
   - `c` (the *only* character actually broken by Chromium's bug - see
     below) &rarr; runs `type-accent.sh`, which briefly puts `ç`/`Ç` on the
     clipboard and simulates a paste via
     [ydotool](https://github.com/ouges/ydotool). This sidesteps Chromium's
     compose bug entirely, since "paste text" isn't dead-key composition at
     all.
   - `e/a/i/o/u` &rarr; re-emits the physical apostrophe keycode followed by
     the letter (`macro(apostrophe e)`, etc.), delegating straight back to
     the OS's own dead-key handling - which already produces `é á í ó ú`
     correctly in every app, Chromium included. These were never broken, so
     they don't pay the clipboard-paste cost and keep the OS's native
     compose engine's tolerance for fast/rolling typing (see **Known
     limitations**).
   - `space` &rarr; types a literal apostrophe followed by a real space.
   - Everything else (other letters, digits, punctuation, arrows,
     Backspace, Enter, ...) falls back to "type apostrophe, then whatever
     you pressed", so ordinary typing (`don't`, `isn't`, `you're`, ...)
     keeps working exactly as before.

   An earlier version of this project routed the vowels through
   `type-accent.sh` too, reasoning that once keyd owns the apostrophe key,
   nothing else can compose natively. That's only true for characters you
   explicitly special-case - everything else can delegate straight back to
   the OS. Only special-case a character here if you've actually confirmed
   Chromium breaks it (test it in `~/.XCompose` first, per the "problem"
   section above); routing more than necessary through the clipboard-paste
   path costs both speed and rolling-typing support for no reason.
3. A small background daemon, `shift-state-daemon.py`, continuously tracks
   whether Shift is physically held and writes `0`/`1` to
   `/dev/shm/keyd-shift-state`. `type-accent.sh` reads that file to decide
   upper vs. lower case. This exists purely for speed - see **Performance**
   below - and isn't load-bearing for correctness (keyd's own
   `[layer:shift]` modifier-scoped sections turned out to be unreliable in
   combination with `oneshot()`, which is why case detection was moved out
   to a plain evdev check in the first place).

This was built and tested for the **`us(intl)`** XKB variant, where the
apostrophe key is `dead_acute` by default (check with `localectl status` -
if it says `X11 Variant: intl`, you're using this layout). If you use a
different layout/dead key, see **Customizing** below.

## Requirements

- Arch-based distro (Manjaro, Arch, etc.) with `pacman` - `install.sh` uses
  it directly. On other distros, install `keyd`, `wl-clipboard`, `ydotool`,
  and `python-evdev` (or your distro's equivalents) yourself, then run
  `generate-keyd-config.py` manually (see below).
- A Wayland session (the clipboard/paste trick uses `wl-copy`/`wl-paste`).
- systemd (for the `keyd` system service and the `ydotool` user service).

## Install

```bash
./install.sh
```

This will:
1. Install `keyd`, `wl-clipboard`, `ydotool`, `python-evdev`.
2. Install `type-accent.sh` and `shift-state-daemon.py` to `/usr/local/bin/`.
3. Install and enable the `keyd-shift-state` system service (runs as root -
   reading `/dev/input/event*` needs either root or the `input` group with a
   fresh login, so this avoids the login requirement for this piece).
4. Generate `/etc/keyd/default.conf` (backing up any existing one first).
5. Add you to the `input` group (may be unnecessary on distros that grant
   `/dev/uinput` access via a `uaccess` udev tag to the active session -
   `ydotool` may already work without it).
6. Enable and start the `keyd` system service and the `ydotool` user
   service.

If ydotool silently fails to inject the paste keystroke after install, log
out and back in - group membership changes need a fresh login session on
some systems.

**Test:** press apostrophe, release, then press `c` &rarr; should type `ç`.
Press apostrophe then Shift+`c` &rarr; should type `Ç`. Press apostrophe
then `e` &rarr; should type `é` instantly (no clipboard-paste delay). Try a
contraction like `don't` to confirm normal typing still works.

## Uninstall

```bash
./uninstall.sh
```

## Customizing

`generate-keyd-config.py` has two lists, and which one a character belongs
in matters a lot (see **Known limitations** for why):

- `CEDILLA_ACCENTS` - characters that get the clipboard-paste treatment.
  Only put a character here if you've *confirmed* Chromium's compose bug
  actually breaks it (e.g. it collides with a system default, the way
  `dead_acute+c` defaults to `ć` instead of `ç`). This is the slow
  (~130ms), rolling-typing-unfriendly path - use it as little as possible.
- `NATIVE_COMPOSE_LETTERS` - characters that already compose correctly via
  the OS's own dead-key handling in every app. This is the fast, instant,
  rolling-tolerant path - prefer it whenever a character isn't actually
  broken.

For example, to add Spanish's `ñ` (assuming it composes fine natively,
which it should unless you've seen it collide with something):

```python
CEDILLA_ACCENTS = {
    'c': ('ç', 'Ç'),
}
NATIVE_COMPOSE_LETTERS = ['e', 'a', 'i', 'o', 'u', 'n']
```

Then regenerate and reinstall the config:

```bash
python3 generate-keyd-config.py /usr/local/bin/type-accent.sh | sudo tee /etc/keyd/default.conf
sudo keyd reload
```

If your dead key is bound to a different physical key (not apostrophe), or
if you use a different XKB variant entirely, change the
`apostrophe = oneshot(cedilla)` line (and the `[cedilla]` section's
`space`/`apostrophe` fallback entries) in `generate-keyd-config.py`
accordingly.

## Performance

The clipboard-paste trick has unavoidable overhead (forking `wl-copy`,
`ydotool`, etc.), but two things matter most for how it *feels* while typing:

- **Don't sleep more than you need to.** The first working version used
  `sleep 0.05` before simulating the paste and `sleep 0.15` after it (as a
  safety margin so the target app has time to actually read the clipboard
  before it gets restored). That's 200ms of pure, deliberate delay on top of
  everything else - very noticeable when typing at speed. The pre-paste
  sleep turned out to be unnecessary (`wl-copy` already returns only after
  registering with the compositor) and the post-paste one could be cut to
  `0.05`.
- **Don't spawn Python fresh on every keystroke.** Checking Shift state
  inline (`python3 -c "import evdev; ..."`) costs ~50-60ms just for the
  interpreter + import, every single time. `shift-state-daemon.py` pays
  that cost once at boot and keeps a plain text file updated instead, so
  `type-accent.sh` just does a ~1ms file read.

Net effect measured on the reference machine: **~336ms &rarr; ~130ms** per
accented keystroke. Still not free, but no longer disruptive at normal
typing speed.

## Known limitations

- **Characters routed through `type-accent.sh` (`CEDILLA_ACCENTS`) don't
  reliably support "rolling" fast typing** - releasing apostrophe before
  the next key, rather than releasing it first. This is an
  [open, unresolved keyd bug](https://github.com/rvaiya/keyd/issues/756):
  its tap/hold detection can misinterpret a key released before the one
  that follows it. The OS's native XCompose engine doesn't have this
  problem (it's a keysym state machine, not tap/hold-based), which is
  exactly why `NATIVE_COMPOSE_LETTERS` exists - keep as many characters as
  possible on that path rather than `CEDILLA_ACCENTS`. A different
  remapper, [kanata](https://github.com/jtroo/kanata), *can* solve this
  properly (`tap-hold-order`, binding both its tap and hold outcomes to the
  same layer - verified with kanata's `simulated_input` tool), but its own
  tap-hold decision adds ~60-70ms, which combined with the clipboard-paste
  cost ends up slower overall than keyd for this use case. Worth
  revisiting if kanata's cmd-execution support or keyd's tap/hold detection
  improves.
- **keyd has a hard limit of 64 chords** (a different feature from what
  this uses, but worth knowing about if you extend the config with `key1+key2`
  bindings elsewhere).
- The clipboard is briefly overwritten on every accented keystroke and then
  restored - if something reads your clipboard in that ~50ms window, it
  could see the accented character instead of your actual clipboard
  content. In practice this hasn't been an issue, but it's not atomic.
- `type-accent.sh` finds your session via the first `/run/user/*/wayland-0`
  socket it finds. On a multi-user system with several simultaneous
  graphical sessions, it may pick the wrong one.
- Only tested on Manjaro KDE Plasma (Wayland). Should work on any
  systemd + Wayland setup, but other compositors aren't verified.
- If you ever run `shift-state-daemon.py` manually or as a user-level
  service before switching it to the root system service (as happened
  during development), delete `/dev/shm/keyd-shift-state` before starting
  the root version. The kernel's `fs.protected_regular` hardening
  (`cat /proc/sys/fs/protected_regular`) blocks *even root* from writing to
  a regular file in a sticky world-writable directory (`/dev/shm`, like
  `/tmp`) if the file's existing owner doesn't match - the daemon will fail
  silently into "always reports Shift not held" instead of erroring loudly.
  `install.sh` already removes any stale copy before starting the service.
