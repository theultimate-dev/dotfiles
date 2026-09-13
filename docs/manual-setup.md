# Manual setup

Everything this repository asks you to do by hand, in order, each with a way to check that it
worked and a way to put it back.

**This is the only file here that contains commands you run yourself.** The other pages in `docs/`
explain *why* something is configured the way it is; this one is the *how*. If you have just cloned
the repo, start at step 1.

`<repo>` throughout means the absolute path of your clone. Substitute it yourself — nothing here
expands it for you.

## Before you start

macOS only. Git push defaults additionally need **git 2.37 or newer** — check with `git --version`,
because on older git the settings `install.sh` activates are silently inert.

**What gets written.** Four files outside this repo by hand, and nothing else. No step creates a
symlink, and no step overwrites a file wholesale:

| Path | Step | Action | Present today? |
|---|---|---|---|
| `~/.config/herdr/config.toml` | 4 | created, or edited | absent until Herdr first runs |
| `~/.claude/settings.json` | 4 | one key added | present if Claude Code is installed |
| `~/.grok/config.toml` | 6 | edited only if the collision fires | conditional |
| `~/.config/zed/settings.json` | 7 | one key added | present if Zed has been run |

`install.sh` in step 1 additionally writes three managed blocks — the include stubs
`~/.config/git/config` and `~/.config/ghostty/config.ghostty`, and an `export` of `YAZI_CONFIG_HOME`
in `~/.zshenv` — and one whole file, `~/.config/hunk/config.toml`, which it owns outright because
hunk has no include mechanism to hook into. It takes its own backups before touching any of them.
Steps 1 to 3 also install software and write credentials, but only into each tool's own
configuration directory. Steps 2, 3 and 5 are interactive — a browser login, a settings pane — and
have no terminal equivalent.

**Snapshot.** Do this once, before step 1. It is the difference between "I changed something" and
"I can put it back":

```sh
mkdir -p ~/.dotfiles-backup

for f in ~/.config/herdr/config.toml ~/.claude/settings.json ~/.grok/config.toml \
         ~/.config/ghostty/config.ghostty ~/.zshenv ~/.config/zed/settings.json \
         ~/.config/hunk/config.toml; do
  if [ -e "$f" ]; then
    cp -p "$f" ~/.dotfiles-backup/"$(printf '%s' "${f#$HOME/.}" | tr / -)"
    echo "saved:  $f"
  else
    echo "absent: $f   (roll back by deleting it)"
  fi
done

git config --list --show-scope --show-origin > ~/.dotfiles-backup/git-config-before.txt
```

Keep `~/.dotfiles-backup` outside this repo and out of version control: the git snapshot contains
your identity, and possibly your signing key.

**Act, then diff.** After a step, take the git snapshot again — from the same directory, or the
scopes will not line up — and compare:

```sh
git config --list --show-scope --show-origin > ~/.dotfiles-backup/git-config-after.txt
diff ~/.dotfiles-backup/git-config-{before,after}.txt
```

The diff is the acceptance test, and the rule is strict: **only added lines are acceptable. A line
that changes rather than appears is a defect** — roll the step back rather than reason about it.
Something you already depend on is being shadowed, and working out which is far cheaper from a
known-good state than from a half-applied one.

**Roll back.** The shape is the same everywhere: restore the copy in `~/.dotfiles-backup`, or delete
the file outright if the loop above reported it absent. Each step below names its own.

**Order.** Steps 1 to 3 run in sequence — you cannot log in to a tool that is not installed yet.
Steps 4 to 7 are independent of each other and of the first three: run them in any order, or skip
the ones you do not want. (Steps 4, 6 and 7 configure tools that step 1 installs; if you skipped
step 1 there is simply nothing there to configure.)

---

## 1. Install the tools and place configs

**What you get.** Homebrew plus every tool the rest of this guide configures — Ghostty, Zed, Herdr,
T3 Code, `terminal-notifier`, Yazi with glow and the tools its previews run through, and the
coding agent CLIs — installed and on `$PATH`, with Herdr's session-identity integration registered
for each agent whose config directory already exists, Yazi's two plugins restored from the
tracked lockfile, and the git and Ghostty include stubs plus the `YAZI_CONFIG_HOME` export in
`~/.zshenv` placed atomically via `./install.sh`. Open a new shell afterwards, or run
`source ~/.zshenv; rehash` in this one: `~/.zshenv` is read at shell start, so a Yazi started from
the shell that ran the installer does not see the export, and inside this repo that same shell's
stale command hash plus zsh's `auto_cd` turn a bare `yazi` into `cd yazi/` — see
[the trap](yazi.md#trap-the-shell-you-installed-from).

**Do this.**

```sh
cd <repo>
./setup.sh
./install.sh
```

Re-running is safe and convergent: `setup.sh` upgrades what Homebrew manages, leaves applications
you had installed by hand alone, and skips integrations already marked current. `install.sh`
verifies and maintains native include stubs without touching existing user configurations.

**Already have Ghostty, Zed or T3 Code in `/Applications`?** `setup.sh` lists an app it did not
install, leaves it alone, and installs everything else. To hand those apps over to Homebrew:

```sh
./setup.sh --adopt
```

It names the two prompts that can follow — a macOS dialog asking to let your terminal manage
other apps, which you must allow, and possibly your password — and checks the permission before
Homebrew touches anything. If the dialog appears, allow it and run the command once more: macOS
refuses the very attempt that makes it ask. Why the default is to skip, and what a refused dialog
would otherwise have cost you, is in
[Apps you installed before Homebrew did](agent-tooling.md#apps-you-installed-before-homebrew-did).

**Verify.**

```sh
brew bundle check --file=<repo>/Brewfile
./install.sh --check
zsh -c 'print $YAZI_CONFIG_HOME'
zsh -c 'ya pkg list'
```

```
The Brewfile's dependencies are satisfied.
Check passed: all managed stubs are current.
<repo>/yazi
Plugins:
	yazi-rs/plugins:git (…)
	yazi-rs/plugins:piper (…)
Flavors:
```

The last two run in a fresh `zsh` on purpose, so they see the `~/.zshenv` the installer just
wrote. Then, in any git repository with an uncommitted change, `yazi` shows a mark next to the
changed file, hovering a `.md` file renders it in the preview pane, and Enter on it opens glow.

An app `setup.sh` skipped shows up in the first check as missing until you adopt it. That is the
expected state, not drift. After `--adopt`, `brew list --cask zed` names it.

**Undo.** Not `brew bundle cleanup` — that removes what is *not* in the `Brewfile`. Uninstall per
entry instead, and remove Homebrew itself only with its own uninstaller:

```sh
brew bundle list --all --file=<repo>/Brewfile   # everything setup.sh installed
brew uninstall --cask ghostty                   # ...one entry at a time
brew uninstall yazi glow                        # ...Yazi and its reader likewise
herdr integration uninstall claude              # ...and any integration it registered
cp -p ~/.dotfiles-backup/zshenv ~/.zshenv       # the ~/.zshenv from before the export block
```

If `~/.zshenv` did not exist before, delete it instead of restoring it; the snapshot loop above
reported which. Yazi's plugin code is inside the repo under `yazi/plugins/`, untracked, and goes
away with the clone.

Adoption has no undo that keeps the app: `brew uninstall --cask zed` removes the bundle Homebrew
took over. To have it outside Homebrew again, reinstall it from the vendor's download.

**Why it works this way.** Homebrew is the single installer of record because the vendors' curl
scripts rewrite `~/.zshrc` and symlink into `$HOME` — see
[Agent tooling and installation](agent-tooling.md#why-vendor-curl-installers-were-rejected).
Configuration placement is kept strictly offline in `install.sh` to adhere to the two-script split.

---

## 2. Install and authenticate the coding agents

**What you get.** `claude`, `codex`, `copilot`, `grok` and `agy` start straight into their own
prompt instead of opening a browser or printing a device code.

**Do this.** Claude Code first, because it is the one agent the `Brewfile` does not install: its
native installer puts the self-updating binary in `~/.local/bin`, and the Homebrew cask would only
add a stale second copy — see
[Agent tooling](agent-tooling.md#specific-tools-deliberately-handled-differently).

```sh
curl -fsSL https://claude.ai/install.sh | bash
```

Then the logins, one at a time. Each opens a browser and waits for you to finish there:

```sh
claude           # Anthropic, browser login
codex            # OpenAI, browser login
copilot          # GitHub, browser login
grok             # xAI, browser login
agy auth login   # Google, browser login
```

Credentials land in each agent's own configuration directory — `~/.claude`, `~/.codex`,
`~/.copilot`, `~/.grok`, `~/.gemini`. Nothing in this repo reads, ships, or backs them up.

**Verify.** Start each one again:

```sh
codex
```

An authenticated CLI drops you at its prompt. If it opens a browser, prints a device code, or says
it is not signed in, that agent still needs this step. There is no scriptable check here; the answer
is what the program does on screen.

**Undo.** Use the agent's own sign-out subcommand where it has one — `claude auth logout`,
`agy auth --help`, and the equivalent for the others, will say. Failing that, quit the agent and
delete the credential file its login created in the directory listed above, then revoke the session
at the provider. Claude Code itself is removed by deleting `~/.local/bin/claude` and
`~/.local/share/claude`.

**Why it works this way.** Every agent owns its own credential store, and this repo ships no tokens
and no identity at all — see [Public-repo hygiene](../AGENTS.md#public-repo-hygiene).

---

## 3. Configure T3 Code

**What you get.** T3 Code can reach a model provider: a new session runs instead of stopping on a
missing API key.

**Do this.**

```sh
open "/Applications/T3 Code (Alpha).app"
```

In the app's settings, add an API key for at least one provider. T3 Code is an alpha GUI control
plane rather than a CLI, so there is no flag for this and no file in this repo to edit.

Leave the keys in the app. If you also need them in your shell, they belong in a file of your own
that your shell sources — outside this repo, `chmod 600` — and never in a file this repo tracks.

**Verify.** Start a session in the app. It responds, rather than reporting a missing or invalid API
key. This is a GUI check; there is nothing to run in a terminal.

**Undo.** Remove the keys in the same settings pane, and revoke them at the provider if they were
issued for this machine alone.

**Why it works this way.** T3 Code ships through Homebrew but configures itself interactively, so it
is documented here rather than managed — see
[Agent tooling and installation](agent-tooling.md#specific-tools-deliberately-handled-differently).

---

## 4. Herdr notifications

**What you get.** A macOS notification when an agent in any Herdr pane finishes or needs input,
carrying your terminal's icon, with a click that raises the terminal and `prefix+g` that jumps to
the pane behind it. Step 5 is what makes it stay on screen.

**Do this.** Three parts. First, Herdr's own configuration:

```sh
mkdir -p ~/.config/herdr
cat >> ~/.config/herdr/config.toml <<'EOF'
[ui.toast]
delivery = "system"
delay_seconds = 1        # default; suppresses notifications for blips shorter than this

[ui.sound]
enabled = true

[ui.sound.agents]        # optional: per-agent, "default" | "on" | "off"
claude = "on"

[keys]
open_notification_target = "prefix+g"   # jump to the pane behind the last notification
EOF

herdr config check          # validate the TOML first
herdr server reload-config  # hot-reload the running server
```

If `config.toml` already defines any of those tables, **edit the keys in place instead of
appending** — TOML rejects a table defined twice, and `herdr config check` is where you find out.

Second, the agent-side integration, but only for an agent you launched for the first time *after*
running step 1 (`setup.sh` registers it for every agent whose config directory already existed):

```sh
herdr integration install claude
```

Third, Claude Code's own notification channel, left enabled so the same agent still notifies
correctly on the days you run it outside Herdr. `iterm2_with_bell` emits the OSC 9 sequence Ghostty
turns into a banner *and* a terminal bell — the bell is what Zed's Terminal Threads, and any other
terminal that never parses OSC 9, key their "agent finished" popup on. In Ghostty the bell only
adds a Dock bounce and a 🔔 tab marker (tunable via `bell-features`):

```sh
mkdir -p ~/.claude
[ -f ~/.claude/settings.json ] || printf '{\n  "preferredNotifChannel": "iterm2_with_bell"\n}\n' > ~/.claude/settings.json
```

If `~/.claude/settings.json` already exists, add `"preferredNotifChannel": "iterm2_with_bell"` to
its top-level object by hand and leave everything else alone — including the `SessionStart` hook
Herdr put there.

Zed needs no step of its own: its Terminal Threads key their popup on that bell with Zed's default
settings — see [One agent setting, three hosts](herdr-notifications.md#one-agent-setting-three-hosts).

**Verify.**

```sh
grep -A 1 '^\[ui\.toast\]' ~/.config/herdr/config.toml
grep -o '"preferredNotifChannel": *"[^"]*"' ~/.claude/settings.json
```

```
[ui.toast]
delivery = "system"
"preferredNotifChannel": "iterm2_with_bell"
```

Then the live test, which needs the Herdr server running:

```sh
herdr notification show "test" --body "hello" --sound done
```

A notification appears carrying your terminal's icon; until step 5 is done it leaves again after a
few seconds. If nothing appears at all, do step 5. If the icon is a script or scroll and clicking it
opens Finder, `terminal-notifier` is missing — go back to step 1.

**Undo.**

```sh
rm ~/.config/herdr/config.toml       # or restore ~/.dotfiles-backup/config-herdr-config.toml
herdr server reload-config
herdr integration uninstall claude   # only if you ran the install above
```

Then remove the `"preferredNotifChannel"` key from `~/.claude/settings.json`, or restore
`~/.dotfiles-backup/claude-settings.json`.

**Why it works this way.** Herdr owns the PTY, so the notification escape sequence your agent emits
never reaches the terminal and `delivery = "system"` is what replaces it — see
[The four delivery modes](herdr-notifications.md#the-four-delivery-modes).

---

## 5. Allow notifications and make them stay on screen

**What you get.** The notifications from step 4 actually appear, and they stay on screen until you
dismiss them instead of leaving after a few seconds. Until the first toggle is on, everything is
configured correctly and nothing shows up; until the second, a banner shows and is gone before you
look up. Both are the most confusing failures in this guide.

**Do this.**

```sh
open "x-apple.systempreferences:com.apple.Notifications-Settings.extension"
```

Find **terminal-notifier** in the application list, turn **Allow Notifications** on, and set
**Alert style** to **Persistent** (older macOS versions call it **Alerts**). Then do both for
**Ghostty**, which is the sender on the days you run an agent outside Herdr.

An entry only appears once the app has tried to notify at least once. If `terminal-notifier` is
missing, run the live test from step 4 and look again; if Ghostty is missing, run this in a Ghostty
pane that is not inside Herdr, switch to another app for a moment, and look again:

```sh
sleep 3; printf '\e]9;dotfiles\a'
```

**Verify.**

```sh
terminal-notifier -diagnose | grep -E 'authorization|alert style'
terminal-notifier -title "dotfiles" -message "notification permission check"
```

```
  authorization       authorized
  alert style         alerts (stay until dismissed)
```

The notification is the output — the terminal is not where to look. It stays in the corner of the
screen until you dismiss it. No notification means the permission is still off; one that leaves on
its own means the style is still Temporary, and the diagnose line still says `banners`.

**Undo.** Set **Alert style** back to **Temporary**, or turn **Allow Notifications** off, in the
same pane.

**Why it works this way.** Herdr posts through `terminal-notifier` so the notification gets the
right icon and click target, which is why the permission and the style macOS asks about are
`terminal-notifier`'s rather than Herdr's — see
[Why terminal-notifier is not optional](herdr-notifications.md#why-terminal-notifier-is-not-optional-in-practice).
The style itself is a per-app choice macOS keeps in a private preference file, which is why no
installer sets it — see
[Making a notification stay on screen](herdr-notifications.md#making-a-notification-stay-on-screen).

---

## 6. Known collisions to check

Conditional. Do each of these only if its check fires. `setup.sh` detects the first and warns;
neither touches a file this repo manages, which is why neither is fixed for you.

**What you get.** `agy` runs the Homebrew-managed binary rather than a stale standalone copy, and a
Grok pane inside Herdr fires one set of agent hooks instead of two.

**Do this.** The `agy` PATH shadow first — `~/.local/bin` precedes Homebrew on `$PATH`, so a binary
left there by Google's standalone installer wins:

```sh
command -v agy                                 # a path under ~/.local/bin means the shadow is live
mv ~/.local/bin/agy ~/.dotfiles-backup/agy     # move rather than delete: it is not ours to replace
```

Then Grok's Claude hook compatibility — Grok reads `~/.claude/settings.json` as an always-on hook
source, so once Herdr's `claude` integration exists a Grok pane fires Claude's hook alongside its
own:

```sh
mkdir -p ~/.grok
cat >> ~/.grok/config.toml <<'EOF'
[compat.claude]
hooks = false
EOF
```

**Verify.**

```sh
command -v agy
grep -A 1 '^\[compat\.claude\]' ~/.grok/config.toml
```

```
/opt/homebrew/bin/agy
[compat.claude]
hooks = false
```

**Undo.**

```sh
mv ~/.dotfiles-backup/agy ~/.local/bin/agy   # put the standalone binary back
```

Then delete the `[compat.claude]` block you appended, or restore
`~/.dotfiles-backup/grok-config.toml`.

**Why it works this way.** Both are collisions with software this repo does not own, so it reports
them instead of acting — see
[Machine-state collisions to expect](agent-tooling.md#machine-state-collisions-to-expect) and
[Grok's Claude hook collision](agent-tooling.md#2-groks-claude-compatibility-hook-collision).

---

## 7. Yazi icons in Zed's terminal

**What you get.** Yazi's file icons and git status signs rendered in Zed's built-in terminal.
Ghostty needs nothing: it ships the Nerd Font symbols and falls back to them on its own. Zed has
no such fallback, so it must be pointed at the symbols font that step 1 installed.

**Do this.** Open Zed's settings (`Cmd+,`) and add a font fallback for the terminal:

```json
{
  "terminal": {
    "font_fallbacks": ["Symbols Nerd Font Mono"]
  }
}
```

**Verify.** In a Zed terminal, `yazi` shows an icon before each file name rather than an empty
box, and a changed file in a git repository carries its sign.

**Undo.** Remove the `font_fallbacks` line, or restore
`~/.dotfiles-backup/config-zed-settings.json`.

**Why it works this way.** Zed's settings are unmanaged here, so this is a by-hand edit rather than
an installer step — see
[ADR 0005](decisions/0005-install-agent-tooling-without-managing-its-config.md) and
[Icons: two hosts, two answers](yazi.md#icons-two-hosts-two-answers).

---

## What the installer has taken over

`install.sh` has landed. It automates Git push defaults by writing the `[include]` into
`${XDG_CONFIG_HOME:-~/.config}/git/config`, the Ghostty configuration by writing a
`config-file` block into `${XDG_CONFIG_HOME:-~/.config}/ghostty/config.ghostty`, and the Yazi
configuration by appending an `export YAZI_CONFIG_HOME` block to `~/.zshenv` — all with
pre-modification backups, delimited blocks, and `--check` drift detection. Machine-local Ghostty
settings go in `~/.config/ghostty/local.ghostty`, which that block includes last so that it wins.
Yazi has no such file: it reads one directory, and that directory is the repo's `yazi/`.

The hunk configuration is the one destination it copies rather than includes, at
`${XDG_CONFIG_HOME:-~/.config}/hunk/config.toml`. An edit made directly to that file does not
survive the next run: change `hunk/config.toml` in the repo and re-run `./install.sh`, and use
`./install.sh --check` to find out when the two have drifted apart. See
[hunk](hunk.md#how-the-config-reaches-hunk).

The rest stays, and stays here:

| Step | Why no installer takes it over |
|---|---|
| [1. Install the tools and place configs](#1-install-the-tools-and-place-configs) | the two-script split: `setup.sh` needs the network, `install.sh` may not |
| [2. Install and authenticate the coding agents](#2-install-and-authenticate-the-coding-agents) | interactive OAuth; nothing types a password into a browser for you |
| [3. Configure T3 Code](#3-configure-t3-code) | provider API keys are secrets, and this repo ships none |
| [4. Herdr notifications](#4-herdr-notifications) | Herdr has no include mechanism; agent settings unmanaged per ADR 0005 |
| [5. Allow notifications and make them stay on screen](#5-allow-notifications-and-make-them-stay-on-screen) | two GUI toggles only you can flip |
| [6. Known collisions to check](#6-known-collisions-to-check) | detection is automatable; the remedy edits files this repo does not manage |
| [7. Yazi icons in Zed's terminal](#7-yazi-icons-in-zeds-terminal) | Zed's settings are unmanaged per ADR 0005 |

One rule outlives the prune: **a command that writes to `$HOME` appears exactly once in this
repository.** If a procedure ever comes back out of `install.sh`, it comes back to this file — not
to the deep dives it left.
