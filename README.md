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

## Is this for you?

This project is for a fairly specific situation - check all of these before
installing:

- You've customized `~/.XCompose` to make a **single dead key + one letter**
  produce something other than its system default (e.g. remapping
  `dead_acute + c` so it types `ç` instead of the default `ç`... er, `ć`).
  This does **not** cover multi-key Compose sequences (a dedicated
  Compose/`Multi_key` key followed by two or more characters) - only
  single-dead-key sequences are modeled here.
- That override works in native/GTK apps (terminals, text editors) but
  **not** in Chrome, Chromium, or any Electron app (VS Code, Slack, Discord,
  Claude Desktop, ...) specifically.
- You're on **Linux with systemd** (`keyd` runs as a systemd system
  service).
- You're on **Wayland or X11** - both are supported (X11 support is less
  tested; see **Known limitations**).
- Ideally you're using a keyboard layout with dead keys, like an `intl`
  XKB variant (check with `localectl status` - if `X11 Variant` says
  `intl` or similar, that's you). The technique itself generalizes to
  *any* physical key you designate as the trigger, dead-key layout or not
  - see **Customizing**.

If your actual problem is different (e.g. you need multi-key Compose
sequences, or a completely different input method), this project's specific
scripts won't directly apply, but the core idea - intercept at the raw
input-device level with `keyd`, since Chromium ignores `~/.XCompose`
entirely regardless of what's in it - still holds.

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

- **Linux with systemd** (for the `keyd` system service and the `ydotool`
  user service) and either **Wayland or X11** (both supported, see below -
  X11 is less tested).
- Four packages: `keyd`, `wl-clipboard` (Wayland) or `xclip` (X11),
  `ydotool`, and `python-evdev`. `install.sh` auto-detects `pacman`/`apt`/
  `dnf` and installs what it can; here's exact, verified availability if you
  need to install manually or `install.sh` can't cover your case:

  | Package | Arch/Manjaro | Debian | Ubuntu | Fedora |
  |---|---|---|---|---|
  | `keyd` | `pacman -S keyd` | `apt install keyd` (13/trixie+) | `apt install keyd` (25.10/questing+) | not official; `dnf copr enable alternateved/keyd && dnf install keyd` |
  | `wl-clipboard` | `pacman -S wl-clipboard` | `apt install wl-clipboard` (10/buster+) | `apt install wl-clipboard` (20.04+) | `dnf install wl-clipboard` |
  | `xclip` (X11 alt.) | `pacman -S xclip` | `apt install xclip` | `apt install xclip` | `dnf install xclip` |
  | `ydotool` | `pacman -S ydotool` | `apt install ydotool` (11/bullseye+) | `apt install ydotool` (22.04+) | `dnf install ydotool` |
  | `python-evdev` | `pacman -S python-evdev` | `apt install python3-evdev` (11/bullseye+) | `apt install python3-evdev` (22.04+) | `dnf install python3-evdev` |

  On an older Debian/Ubuntu release than listed, `keyd` has no official
  package or PPA as of this writing - build it from source per
  [keyd's own instructions](https://github.com/rvaiya/keyd#installation)
  (`git clone`, `make`, `sudo make install`, `systemctl enable --now keyd`).
  For any distro/version, `pip install evdev` is a universal fallback for
  `python-evdev` (needs a C compiler and Python/Linux dev headers - see
  [python-evdev's install docs](https://python-evdev.readthedocs.io/en/latest/install.html)).

## Install

```bash
./install.sh
```

This will:
1. Detect your package manager (`pacman`, `apt`, or `dnf`) and install
   `keyd`, a clipboard tool (`wl-clipboard` on Wayland, `xclip` on X11),
   `ydotool`, and `python-evdev` - see the table above for exact
   availability; on Fedora this enables the `alternateved/keyd` COPR repo
   for `keyd` specifically, since it isn't in Fedora's official repos.
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

Only the Arch/pacman path has actually been run end-to-end; the apt/dnf
paths use verified package names and commands but haven't been tested on
real Debian/Ubuntu/Fedora installs - please open an issue if something's
wrong.

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

If your dead key is bound to a different physical key (not apostrophe) -
say you use `grave` for `dead_grave`/`dead_tilde`, or any other single key
that acts as a dead key in your layout - change `TRIGGER_KEY` and
`TRIGGER_CHAR` at the top of `generate-keyd-config.py`:

```python
TRIGGER_KEY = "grave"   # run `keyd list-keys` for valid names
TRIGGER_CHAR = "`"      # the literal character that key normally produces alone
```

Everything else (the oneshot layer, space/double-tap fallbacks, the
`CEDILLA_ACCENTS`/`NATIVE_COMPOSE_LETTERS` split) is generated relative to
these two values, so you shouldn't need to touch anything else.

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

- **Uppercase `NATIVE_COMPOSE_LETTERS` typed with Shift held can come out
  wrong** - e.g. apostrophe then Shift+e can produce `Ë` instead of the
  intended `É`. This happens because `macro($TRIGGER_KEY <letter>)` doesn't
  clear ambient modifiers: if Shift is held for the uppercase letter, it
  also applies to the synthetic trigger-key emission, and under `us(intl)`
  apostrophe unshifted is `dead_acute` but apostrophe *shifted* is
  `dead_diaeresis`. This was deliberately left unfixed - fixing it correctly
  requires routing through an external script to explicitly manage Shift
  (the same pattern `type-accent.sh`/`CEDILLA_ACCENTS` uses), which
  reintroduces real latency for characters that don't otherwise need it.
  This project prioritizes keeping `NATIVE_COMPOSE_LETTERS` fast and simple
  over handling this less-common case - if it matters for your use case,
  adapt the `CEDILLA_ACCENTS`/`type-accent.sh` pattern for the affected
  letters instead.
- **Apps running via XWayland (not native Wayland) may not work correctly**,
  even for `NATIVE_COMPOSE_LETTERS`. XWayland keeps its own X11 keyboard
  mapping, separate from the native Wayland session's - on at least one
  system, XWayland reported a plain `us` layout with no `intl` variant while
  the real session used `us(intl)`. Since this project's dead-key replay
  (`macro(apostrophe e)`, etc.) depends on the receiving side interpreting
  those keycodes the same way the compositor does, a mismatched XWayland
  keymap breaks it - this is a system/compositor configuration issue, not
  something fixable in this project's config. Check whether an app is
  affected by inspecting its process environment for
  `QT_QPA_PLATFORM=xcb` (Qt apps) or by comparing
  `DISPLAY=:1 setxkbmap -query` (adjust the display number) against your
  session's real layout. Known affected: WPS Office. Native Wayland apps
  (Chrome, Electron apps, most GTK/Qt-Wayland apps) are unaffected.
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
- `type-accent.sh` finds your session via the first `/run/user/*/.ydotool_socket`
  it finds. On a multi-user system with several simultaneous graphical
  sessions, it may pick the wrong one.
- Only tested on Manjaro KDE Plasma (Wayland). Should work on other systemd
  + Wayland desktop environments; X11 support (via `xclip`) is implemented
  but untested end-to-end, and other compositors/window managers aren't
  verified.
- If you ever run `shift-state-daemon.py` manually or as a user-level
  service before switching it to the root system service (as happened
  during development), delete `/dev/shm/keyd-shift-state` before starting
  the root version. The kernel's `fs.protected_regular` hardening
  (`cat /proc/sys/fs/protected_regular`) blocks *even root* from writing to
  a regular file in a sticky world-writable directory (`/dev/shm`, like
  `/tmp`) if the file's existing owner doesn't match - the daemon will fail
  silently into "always reports Shift not held" instead of erroring loudly.
  `install.sh` already removes any stale copy before starting the service.
