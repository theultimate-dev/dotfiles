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

**What gets written.** Six files outside this repo by hand, and nothing else. No step creates a
symlink, and no step overwrites a file holding settings of yours — step 4 replaces Herdr's config
only while it holds nothing but the `onboarding = false` Herdr's first run writes:

| Path | Step | Action | Present today? |
|---|---|---|---|
| `~/.config/agent-sync/manifest.toml` | 3 | copied from `agent-sync/`, then edited | absent |
| `~/.config/herdr/config.toml` | 4 | copied from `herdr/`, or merged | absent until Herdr first runs |
| `~/.config/herdr/plugins/config/hhdebb.herdr-radar/config.toml` | 4 | copied from `herdr/`, or merged | absent until you save herdr-radar's settings |
| `~/.claude/settings.json` | 4 | one key added | present if Claude Code is installed |
| `~/.grok/config.toml` | 6 | edited only if the collision fires | conditional |
| `~/.docker/config.json` | 7 | one key added; Colima then sets the current context, defined in `~/.docker/contexts/` | absent until Docker or Colima first runs |

`install.sh` in step 1 additionally writes three managed blocks — the include stubs
`~/.config/git/config` and `~/.config/ghostty/config.ghostty`, and an `export` of `YAZI_CONFIG_HOME`
in `~/.zshenv` — and one whole file, `~/.config/hunk/config.toml`, which it owns outright because
hunk has no include mechanism to hook into. It takes its own backups before touching any of them.
Steps 1 and 2 also install software and write credentials, but only into each tool's own
configuration directory. The one exception is the Herdr plugin `setup.sh` installs: it copies its
icon font into `~/Library/Fonts` and appends a block of its own, fenced by `herdr-radar` markers,
to each Ghostty config file that already exists, `~/.config/ghostty/config.ghostty` among them —
see [Herdr plugins](agent-tooling.md#herdr-plugins) for the full list and the `./install.sh
--check` warning it can cause. Step 3 runs `scripts/agent-sync`, which asks Claude Code and Codex
to install plugins through their own commands, copies skills into `~/.gemini/config/skills/`, and
keeps its own state, archive and Git cache under `~/.local/state/agent-sync/` and
`~/.cache/agent-sync/`. Step 7 creates Colima's VM in Colima's own `~/.colima` and caches
its image in `~/Library/Caches/colima`. Steps 2 and 5 are interactive — a browser login, a
settings pane — and have no terminal equivalent.

**Snapshot.** Do this once, before step 1. It is the difference between "I changed something" and
"I can put it back":

```sh
mkdir -p ~/.dotfiles-backup

for f in ~/.config/herdr/config.toml ~/.claude/settings.json ~/.grok/config.toml \
         ~/.config/agent-sync/manifest.toml \
         ~/.config/ghostty/config.ghostty ~/.zshenv \
         ~/.config/hunk/config.toml ~/.docker/config.json \
         ~/.config/herdr/plugins/config/hhdebb.herdr-radar/config.toml; do
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

**Order.** Steps 1 and 2 run in sequence — you cannot log in to a tool that is not installed yet.
Steps 3 to 7 are independent of each other: run them in any order, or skip the ones you do not
want. (They configure tools that steps 1 and 2 install, and step 3 needs the agents signed in; if
you skipped those, there is simply nothing there to configure.)

---

## 1. Install the tools and place configs

**What you get.** Homebrew plus every tool the rest of this guide configures — Ghostty, Herdr,
`terminal-notifier`, Yazi with Leaf and the tools its previews run through, Colima with the Docker
CLI and its Compose and Buildx plugins, and the coding agent CLIs — installed and on `$PATH`, with
Herdr's session-identity integration registered for each agent whose config directory already
exists, the Herdr plugins pinned in `herdr/plugins.txt` installed at their pinned release, Yazi's
two plugins restored from the tracked lockfile, and the git and Ghostty include stubs plus the
`YAZI_CONFIG_HOME` export in `~/.zshenv` placed atomically via `./install.sh`. Open a new shell
afterwards, or run `source ~/.zshenv; rehash` in this one: `~/.zshenv` is read at shell start, so
a Yazi started from the shell that ran the installer does not see the export, and inside this repo
that same shell's stale command hash plus zsh's `auto_cd` turn a bare `yazi` into `cd yazi/` — see
[the trap](yazi.md#trap-the-shell-you-installed-from).

**Do this.**

```sh
cd <repo>
./setup.sh
./install.sh
```

Re-running is safe and convergent: `setup.sh` upgrades what Homebrew manages, leaves applications
you had installed by hand alone, skips integrations already marked current, and leaves a Herdr
plugin alone once it is at its pinned commit. `install.sh`
verifies and maintains native include stubs without touching existing user configurations.

**Already have Ghostty in `/Applications`?** `setup.sh` lists an app it did not install, leaves
it alone, and installs everything else. To hand it over to Homebrew:

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
changed file, hovering a `.md` file renders it in the preview pane, and Enter on it opens Leaf.

An app `setup.sh` skipped shows up in the first check as missing until you adopt it. That is the
expected state, not drift. After `--adopt`, `brew list --cask ghostty` names it.

**Undo.** Not `brew bundle cleanup` — that removes what is *not* in the `Brewfile`. Uninstall per
entry instead, and remove Homebrew itself only with its own uninstaller:

```sh
brew bundle list --all --file=<repo>/Brewfile   # everything setup.sh installed
brew uninstall --cask ghostty                   # ...one entry at a time
brew uninstall yazi leaf-markdown-viewer         # ...Yazi and its reader likewise
herdr integration uninstall claude              # ...and any integration it registered
herdr plugin action invoke hhdebb.herdr-radar.uninstall-font   # the plugin's font and Ghostty block
herdr plugin uninstall hhdebb.herdr-radar       # ...and the plugin itself
cp -p ~/.dotfiles-backup/zshenv ~/.zshenv       # the ~/.zshenv from before the export block
```

Run the `herdr` lines while Herdr is still installed, and after the undo of
[step 4](#4-configure-herdr) if you did that step: the plugin has to take its blocks out of Herdr's
config before it goes. If `~/.zshenv` did not exist before, delete it instead of restoring it; the
snapshot loop above reported which. Yazi's plugin code is inside the repo under `yazi/plugins/`,
untracked, and goes away with the clone.

Adoption has no undo that keeps the app: `brew uninstall --cask ghostty` removes the bundle
Homebrew took over. To have it outside Homebrew again, reinstall it from the vendor's download.

**Why it works this way.** Homebrew is the single installer of record because the vendors' curl
scripts rewrite `~/.zshrc` and symlink into `$HOME` — see
[Agent tooling and installation](agent-tooling.md#why-vendor-curl-installers-were-rejected).
Configuration placement is kept strictly offline in `install.sh` to adhere to the two-script split.

### Switch an existing installation from Glow to Leaf

**Do this.** Install the Markdown viewer formula, then quit and restart Yazi:

```sh
brew install leaf-markdown-viewer
```

The executable is `leaf`; the formula named `leaf` is an unrelated program. Existing installations
already pointing `YAZI_CONFIG_HOME` at this repo need no `install.sh` re-run. Leave Glow installed
until you finish comparing the readers. Full setup also installs Leaf through the Brewfile.

**Verify.**

```sh
leaf --version
leaf --theme ocean --inline ansi:80 -- README.md
./install.sh --check
```

In a fresh Yazi session, hover a Markdown file with a table and a Mermaid flowchart. Check the
preview, scroll it with `J` and `K`, and resize the terminal. Enter opens Leaf in Ocean; `q` returns
to Yazi. `Ctrl+E` inside Leaf opens micro, and `O` in Yazi still offers micro as the second entry.
Compare the same file in Glow before removing it. See [rendering limits](yazi.md#leaf-and-glow)
for why a narrow preview or an unsupported diagram can look different from a browser.

**Optional cleanup after verification.**

```sh
brew uninstall glow
```

This does not remove personal Glow settings. Do not use `brew bundle cleanup` for this migration:
it can remove unrelated tools absent from this repository's Brewfile.

**Undo.** Restore the previous `Brewfile` and `yazi/yazi.toml` together from your pre-migration
revision, preserving any unrelated edits, then restart Yazi. If you removed Glow, reinstall it:

```sh
brew install glow
```

Leaf can remain installed while you verify the rollback. To remove it afterwards, use the
per-entry uninstall procedure above with the `leaf-markdown-viewer` formula.

### Remove Zed and Copilot CLI from an existing installation

Zed, GitHub Copilot CLI and the `font-symbols-only-nerd-font` cask are no longer in the `Brewfile`,
and `setup.sh` no longer registers Herdr's Copilot integration. `setup.sh` never uninstalls
anything, so an installation made before that change keeps all three, and the integration, until
you remove them here. This is optional: skip it, or any part of it, for a tool you still use.
Nothing else in this guide depends on them being gone.

**Do this.** First, see which of the three casks Homebrew manages on this Mac. A tool you
installed by hand and never adopted is not on the list, and Homebrew cannot remove it:

```sh
brew list --cask | grep -x -E 'zed|copilot-cli|font-symbols-only-nerd-font'
```

If you want Copilot CLI's login gone from this Mac, sign out before uninstalling: start `copilot`,
type `/logout`, then quit. macOS keeps that credential in the Keychain, under the service
`copilot-cli`, and no uninstall below touches it. Signing out removes only the local token; to end
the authorization itself, revoke it at GitHub as well.

Then Herdr's Copilot integration, while Herdr is installed and `~/.copilot` still exists, because
the hook it removes lives in that directory:

```sh
herdr integration uninstall copilot
```

Then the casks. Name only the ones the first command printed, and leave out any you want to keep:

```sh
brew uninstall --cask zed copilot-cli font-symbols-only-nerd-font
```

That removes the apps, the `zed` and `copilot` commands and the symbols font, and keeps your
settings and data. To delete those files as well, run the same command with `--zap` instead,
naming the same casks:

```sh
brew uninstall --zap --cask zed copilot-cli font-symbols-only-nerd-font
```

`--zap` moves to the Trash Zed's `~/.config/zed` and `~/Library/Application Support/Zed` with its
caches, logs and preferences, and Copilot CLI's `~/.copilot` and `~/Library/Caches/copilot`. It
leaves the Keychain credential alone; only `/logout` above removes that. Keep the font cask out of
either command if another terminal of yours falls back to Symbols Nerd Font Mono for its icons.

**Zed you installed yourself.** If `zed` was not printed but `/Applications/Zed.app` exists,
`setup.sh` left your own copy alone. Do not adopt it just to remove it: quit Zed and drag
`Zed.app` from `/Applications` to the Trash. Its settings stay in `~/.config/zed` and
`~/Library/Application Support/Zed` until you trash those folders too.

**Verify.** Each line reports on a tool only if you chose to remove it:

```sh
herdr integration status | grep '^copilot:'
brew list --cask | grep -x -E 'zed|copilot-cli|font-symbols-only-nerd-font'
brew bundle check --file=<repo>/Brewfile
```

```
copilot: not installed (…)
The Brewfile's dependencies are satisfied.
```

The second command prints only the casks you kept, or nothing. For each tool you removed,
`command -v zed` or `command -v copilot` prints nothing, and a removed Zed leaves no
`/Applications/Zed.app`.

**Undo.** Reinstall the casks you removed. After `--zap`, start `copilot` once and quit it, so
that `~/.copilot` exists again; then put the integration back:

```sh
brew install --cask zed copilot-cli font-symbols-only-nerd-font
herdr integration install copilot
```

Copilot CLI asks you to sign in only if you ran `/logout` or revoked its authorization at GitHub;
`--zap` alone does not sign you out. A Zed you trashed by hand comes back from the Trash or the
vendor's download. A later `setup.sh` run neither reinstalls the casks nor re-registers the
integration, so these steps are the whole undo. Settings removed with `--zap` come back only from
the Trash, or from a backup of your own.

---

## 2. Install and authenticate the coding agents

**What you get.** `claude`, `codex`, `grok` and `agy` start straight into their own
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
grok             # xAI, browser login
agy auth login   # Google, browser login
```

Credentials land in each agent's own configuration directory — `~/.claude`, `~/.codex`,
`~/.grok`, `~/.gemini`. Nothing in this repo reads, ships, or backs them up.

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

## 3. Sync agent plugins and skills

**What you get.** Claude Code and Codex holding the plugins you list, installed through their own
plugin commands; Antigravity holding copies of the skills you pick from them, in its personal
skills folder; and one report of what changed, what was already current and what needs you. Each
skill reaches a harness once: the cleanup at the end archives the older flat copies that shadow a
plugin.

This step needs step 2 done, and a Python 3.11 or newer on `$PATH` as `python3`; step 1's
`Brewfile` installs one. Check with `python3 --version`. If you set `XDG_STATE_HOME`, keep it on
the same volume as your home folder: agent-sync only ever renames into its archive there, and an
item whose archive is on another volume fails with nothing moved. A `scripts/` entry on `$PATH` is
still planned, so every command below calls the script by its path.

**Do this.** First, the manifest. It is yours, untracked, and starts as a copy of the commented
example. The copy goes where the script looks: `$XDG_CONFIG_HOME/agent-sync/` when that variable
holds an absolute path, else `~/.config/agent-sync/`. It refuses to overwrite a manifest that is
already there, or a link in its place, even a dangling one:

```sh
case "$XDG_CONFIG_HOME" in
  /*) dir="$XDG_CONFIG_HOME/agent-sync" ;;
  *)  dir="$HOME/.config/agent-sync" ;;
esac
mkdir -p "$dir"
if [ -e "$dir/manifest.toml" ] || [ -L "$dir/manifest.toml" ]; then
  echo "kept: $dir/manifest.toml exists or is a link; edit or remove it instead"
else
  cp <repo>/agent-sync/manifest.example.toml "$dir/manifest.toml"
fi
echo "manifest: $dir/manifest.toml"
```

Edit the manifest the last line names: your marketplaces, their Git sources and the paths
of your checkouts, and the plugins you want. The comments in it explain every key. Then look
before anything changes, and read the whole report:

```sh
<repo>/scripts/agent-sync --dry-run
```

Nothing is written and nothing is fetched. Each `unchecked` row says what a run would do: the
exact command for a harness change, the copy it would make for agy, or that a catalog is not
fetched yet, in which case its plugins are listed once a run or `--check` has fetched it. When the
plan is what you meant, run it:

```sh
<repo>/scripts/agent-sync
```

A `held` row waits for you and names the flag that releases it: `--accept-command <plugin>=<hash>`
for a command a catalog declares, after you have read it, or `--adopt <name>` for an agy folder
agent-sync did not create, which it archives first. Re-run with that flag. A `stale` row is a Codex
cache that differs from its source; `--repair` reinstalls exactly those plugins.

Then, once, the duplicates already on this machine. Look first, then answer for each folder:

```sh
<repo>/scripts/agent-sync cleanup --dry-run
<repo>/scripts/agent-sync cleanup
```

A yes moves the folder into the archive unless cleanup prints why not, under the folder: it is
or holds a symlink, part of it cannot be read, it changed while the question was open, or its
archive is on another volume. Nothing is deleted. When anything was archived, the last line prints
the `--restore` command for this cleanup run; keep it.

**Verify.** Run it again:

```sh
<repo>/scripts/agent-sync --check
```

It exits 0 and its summary reads `0 changed`: nothing has drifted. A `duplicate` row may remain.
It names a flat copy that cleanup kept, because you answered no or for one of the reasons cleanup
printed under it. Each such copy still shadows its plugin until you deal with it. Then start a
fresh session in each harness, run `/skills reload` first in agy, and open its list of skills: a
skill from a managed plugin appears once, apart from the copies the `duplicate` rows name.

**Undo.** Each part has its own:

- **The cleanup:** run the `--restore` line it printed, as
  `<repo>/scripts/agent-sync cleanup --restore <timestamp>`, with the flat folders resolving
  where they did at cleanup: the same `CLAUDE_CONFIG_DIR`, and `~/.claude` and `~/.agents`
  leading to the same folders. Restore refuses a folder whose profile changed and keeps it
  archived. Add `--dry-run` first to see what it would move.
- **An agy copy:** it is `~/.gemini/config/skills/<name>/`, where `<name>` is the `copied` row's
  item without its `<plugin>/` prefix; a dry run's `unchecked` row prints the whole path. If you
  have edited the copy since, move it out of agy's skills folder to keep your edits; otherwise
  delete it. Where a run replaced a folder, its `copied` row names where the previous copy went in
  `~/.local/state/agent-sync/archive/<timestamp>/agy/`; move that folder back instead.
- **A plugin:** agent-sync never uninstalls. Use the harness's own command:
  `claude plugin uninstall <plugin>@<marketplace>` and `claude plugin marketplace remove <name>`
  for Claude Code, `codex plugin remove <plugin>@<marketplace>` and
  `codex plugin marketplace remove <name>` for Codex.
- **agent-sync itself:** delete the manifest folder the first command named,
  `~/.cache/agent-sync/` and, once nothing in its archive is wanted,
  `~/.local/state/agent-sync/`.

**Why it works this way.** agent-sync drives each harness through its own CLI and writes no harness
settings file, and agy is the one harness that gets copies, because it cannot follow a third-party
catalog. See [agent-sync](agent-sync.md) for each trap, and
[ADR 0014](decisions/0014-sync-agent-plugins-through-their-own-clis.md).

---

<a id="3-configure-herdr"></a>

## 4. Configure Herdr

**What you get.** Herdr set up from this repo's `herdr/` directory. A macOS notification when an
agent in any Herdr pane finishes or needs input, carrying your terminal's icon, with a click that
raises the terminal and `prefix+g` that jumps to the pane behind it; step 5 is what makes it stay
on screen. And [herdr-radar](https://github.com/hhdebb/herdr-radar), the plugin step 1 installed,
drawing the sidebar's Agents list: who is working and who is waiting on you, grouped by project,
with `prefix+a` flipping its order and `prefix+comma` opening its settings.

**Do this.** Four parts, from the repository root, with Herdr running. No script does this for
you: Herdr's config file is also written by Herdr itself and by herdr-radar, so the repo's copy is
copied only where there is nothing to keep, and merged everywhere else. The prompt after the four
parts hands the same work to a coding agent.

First, Herdr's own configuration. This copies `herdr/config.toml` only onto a Mac where Herdr has
no configuration yet, or none beyond the `onboarding = false` its first run writes; anywhere else
it changes nothing and says so:

```sh
cd <repo>
mkdir -p ~/.config/herdr
if [ ! -e ~/.config/herdr/config.toml ] ||
   [ "$(grep -Ev '^[[:space:]]*(#|$)' ~/.config/herdr/config.toml)" = 'onboarding = false' ]; then
  cp herdr/config.toml ~/.config/herdr/config.toml && echo "copied"
else
  echo "~/.config/herdr/config.toml holds settings of its own: merge by hand"
fi
herdr config check
```

To merge by hand, bring every table of `herdr/config.toml` across and keep everything of your own:

- **Edit a table that already exists in place** instead of adding it again: TOML rejects a table
  defined twice, and `herdr config check` is where you find out.
- **Keep `[ui]` as a header line of its own**, even with no keys under it. herdr-radar writes its
  tab-bar block directly below that line, and without it configures nothing at all.
- **Leave herdr-radar's parts alone:** every line from a `# >>> herdr-radar … block` marker to its
  `# <<< herdr-radar … block`, and `name` and `auto_switch` under `[theme]`.
- **Never add** `tab_bar_right`, `tab_bar_right_separator`, `[theme.custom]` or any
  `[ui.sidebar.…]` table. The plugin owns them, and drops its own block when it finds yours.

`herdr config check` has to print `config: ok` before you go on.

Second, herdr-radar's own settings, guarded the same way. The plugin's settings popup is the only
other writer of this file, so one that exists holds choices you made there:

```sh
dir="$(herdr plugin config-dir hhdebb.herdr-radar)"
if [ -e "$dir/config.toml" ]; then
  echo "$dir/config.toml exists: merge by hand"
else
  mkdir -p "$dir" && cp herdr/plugins/hhdebb.herdr-radar/config.toml "$dir/" && echo "copied"
fi
```

To merge, set each key from the repo's file in place. A comment goes on a line of its own: the
popup rewrites every key line it saves, and drops a comment at the end of one.

Third, make it live. The reload picks up Herdr's settings. `configure` writes herdr-radar's three
blocks, and has to be run once by hand: the plugin's first start skips them for good if `[ui]` was
missing then — see [the trap](agent-tooling.md#herdr-plugins). `state-restart` restarts only the
plugin's own process, which reads its settings file when it starts. Nothing in your panes is
touched:

```sh
herdr server reload-config
herdr plugin action invoke hhdebb.herdr-radar.configure
herdr plugin action invoke hhdebb.herdr-radar.state-restart
```

Fourth, the agent side of notifications. The integration, but only for an agent you launched for
the first time *after* running step 1 (`setup.sh` registers it for every agent whose config
directory already existed):

```sh
herdr integration install claude
```

Then Claude Code's own notification channel, left enabled so the same agent still notifies
correctly on the days you run it outside Herdr. `iterm2_with_bell` emits the OSC 9 sequence Ghostty
turns into a banner *and* a terminal bell — the bell is what a terminal that never parses OSC 9,
such as Zed's Terminal Threads, keys its "agent finished" popup on. In Ghostty the bell only
adds a Dock bounce and a 🔔 tab marker (tunable via `bell-features`):

```sh
mkdir -p ~/.claude
[ -f ~/.claude/settings.json ] || printf '{\n  "preferredNotifChannel": "iterm2_with_bell"\n}\n' > ~/.claude/settings.json
```

If `~/.claude/settings.json` already exists, add `"preferredNotifChannel": "iterm2_with_bell"` to
its top-level object by hand and leave everything else alone — including the `SessionStart` hook
Herdr put there.

**Or hand it to an agent.** Paste this into a coding agent started in the repository. It points the
agent at the parts above rather than repeating them, so the two cannot drift apart:

```text
Apply this repository's Herdr configuration to this Mac. Follow parts one to three of step 4 in
docs/manual-setup.md, from the repository root, and do nothing that step does not describe.

- Where a destination file already holds settings, merge by the rules written in that step.
  Never replace such a file, and copy it to ~/.dotfiles-backup/ before you change it.
- Leave every herdr-radar block, and name and auto_switch under [theme], exactly as they are.
- Do not stop the Herdr server or kill Herdr: that ends every program in every pane, possibly
  including you.
- Finish with the step's Verify section, and report each key you added or changed, by file.
```

**Verify.**

```sh
herdr config check
grep -c '^# >>> herdr-radar' ~/.config/herdr/config.toml
diff -B -I '^[[:space:]]*#' \
  <(sed -E -e '/^# >>> herdr-radar/,/^# <<< herdr-radar/d' -e '/^(name|auto_switch) = /d' \
  ~/.config/herdr/config.toml) herdr/config.toml
diff "$(herdr plugin config-dir hhdebb.herdr-radar)/config.toml" \
  herdr/plugins/hhdebb.herdr-radar/config.toml
grep -o '"preferredNotifChannel": *"[^"]*"' ~/.claude/settings.json
```

```
config: ok
3
"preferredNotifChannel": "iterm2_with_bell"
```

The `3` counts herdr-radar's blocks: tab bar, theme and sidebar. After a copy the two `diff`s print
nothing. The first compares your file with the repo's, leaving out comments, blank lines,
herdr-radar's blocks and its two `[theme]` keys: a line marked `>` is a repo setting your file
lacks, one marked `<` is a setting of your own. Run it again whenever `herdr/config.toml` changes;
its `>` lines are the merge to do.

In Herdr, the sidebar's Agents list now groups agents under their workspace, each with its
vendor's logo. If the logos come out as boxes, open a new Ghostty window, and restart Ghostty if
they stay that way: a newly installed font reaches new windows, not the ones already open.

Then the live test for notifications:

```sh
herdr notification show "test" --body "hello" --sound done
```

A notification appears carrying your terminal's icon; until step 5 is done it leaves again after a
few seconds. If nothing appears at all, do step 5. If the icon is a script or scroll and clicking it
opens Finder, `terminal-notifier` is missing — go back to step 1.

**Undo.**

```sh
herdr plugin action invoke hhdebb.herdr-radar.unconfigure   # its blocks out, [theme] restored
cp -p ~/.dotfiles-backup/config-herdr-config.toml ~/.config/herdr/config.toml
rm "$(herdr plugin config-dir hhdebb.herdr-radar)/config.toml"
herdr server reload-config
herdr integration uninstall claude   # only if you ran the install above
```

If the snapshot loop reported `~/.config/herdr/config.toml` absent, delete it instead of restoring
it. If it saved herdr-radar's settings file, restore
`~/.dotfiles-backup/config-herdr-plugins-config-hhdebb.herdr-radar-config.toml` instead of deleting
it. Then remove the `"preferredNotifChannel"` key from `~/.claude/settings.json`, or restore
`~/.dotfiles-backup/claude-settings.json`.

**Why it works this way.** Herdr has no include directive, and its config file has two other
writers, Herdr's own settings panel and herdr-radar, so no script here writes it; see
[ADR 0013](decisions/0013-apply-the-herdr-config-by-hand.md). How the plugin is pinned and kept
current: [Herdr plugins](agent-tooling.md#herdr-plugins). Herdr owns the PTY, so the notification
escape sequence your agent emits never reaches the terminal and `delivery = "system"` is what
replaces it — see [The four delivery modes](herdr-notifications.md#the-four-delivery-modes).

---

<a id="4-allow-notifications-and-make-them-stay-on-screen"></a>

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

<a id="5-known-collisions-to-check"></a>

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

<a id="8-run-containers-with-colima"></a>

## 7. Run containers with Colima

**What you get.** `docker`, `docker compose` and `docker buildx` working against Colima's Linux VM,
sized for several Compose stacks at once, with file watchers inside containers seeing the edits
you make on the Mac. The VM runs only while you have started it.

**Do this.** First, tell Docker where Homebrew put the Compose and Buildx plugins. This adds one
key to `~/.docker/config.json`, creating the file if it is absent and keeping everything else in
it. Re-running it changes nothing:

```sh
mkdir -p ~/.docker
cfg=~/.docker/config.json
{ cat "$cfg" 2>/dev/null || echo '{}'; } |
  jq --arg dir "$(brew --prefix)/lib/docker/cli-plugins" \
    '.cliPluginsExtraDirs = ((.cliPluginsExtraDirs // []) - [$dir] + [$dir])' > "$cfg.tmp" &&
  chmod 600 "$cfg.tmp" && mv "$cfg.tmp" "$cfg"
```

Then create and start the VM. These numbers fit an Apple silicon Mac with 10 cores and 32 GiB
running three or four web stacks at once. Work out your own from
[Sizing the VM](colima.md#sizing-the-vm-for-several-stacks-at-once) **before the first start**: the
disk can only grow, and the VM type is fixed once the VM exists.

```sh
colima start --vm-type vz --mount-type virtiofs --mount-inotify \
  --cpus 8 --memory 12 --disk 150 --ssh-config=false
```

The first start downloads the VM image. Colima saves these flags, so from then on a bare
`colima start` and `colima stop` are all you type. To change the CPUs or the memory, stop the VM
and start it again with only the new value:

```sh
colima stop
colima start --memory 16
```

**Verify.**

```sh
docker context ls
docker compose version
docker buildx version
docker run --rm hello-world
```

`colima` is the context marked current with `*`, both plugins print a version, and `hello-world`
prints `Hello from Docker!`. Then, in any project whose containers run a file watcher over a bind
mount, save a real change to a watched file on the Mac and watch `docker compose logs -f` show the
reload. A bare `touch` is not enough: it does not trigger the watcher, even with the flag on.

**Undo.** Delete the VM. This deletes every image, container and volume inside it, along with the
`colima` Docker context, and asks first. Then remove what it leaves behind: Colima's shared state
and the cached VM image. Skip the second line if you keep other Colima profiles.

```sh
colima delete
rm -rf ~/.colima ~/Library/Caches/colima
```

Then restore `~/.dotfiles-backup/docker-config.json`, or delete `~/.docker/config.json` if the
snapshot loop reported it absent. The packages themselves go with step 1's undo.

**Why it works this way.** Colima rewrites its own config on every start that passes flags, so it
stays unmanaged, as [ADR 0005](decisions/0005-install-agent-tooling-without-managing-its-config.md)
leaves other self-rewriting configs. The plugin directory is listed rather than symlinked. See
[Colima](colima.md) for every flag, the sizing, and the traps.

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
| [3. Sync agent plugins and skills](#3-sync-agent-plugins-and-skills) | needs Python, the network and signed-in agents, and can stop to ask you; `install.sh` is offline and `setup.sh` should not stop to ask — see ADR 0014 |
| [4. Configure Herdr](#4-configure-herdr) | Herdr's config file is also written by Herdr and herdr-radar; kept in `herdr/` and applied by hand per ADR 0013 |
| [5. Allow notifications and make them stay on screen](#5-allow-notifications-and-make-them-stay-on-screen) | two GUI toggles only you can flip |
| [6. Known collisions to check](#6-known-collisions-to-check) | detection is automatable; the remedy edits files this repo does not manage |
| [7. Run containers with Colima](#7-run-containers-with-colima) | the VM's size is a choice per machine; Colima's config is unmanaged per ADR 0005, and `config.json` is Docker's own |

One rule outlives the prune: **a command that writes to `$HOME` appears exactly once in this
repository.** If a procedure ever comes back out of `install.sh`, it comes back to this file — not
to the deep dives it left.
