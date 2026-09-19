# The Ultimate Dev — Dotfiles

My macOS development stack, shared publicly: terminal, file manager, live diff pane, git defaults,
and the tooling that holds them together — installed without a single symlink.

<!--
Hero screenshot goes here once captured. Suggested shot: Ghostty with Herdr open, a coding agent in
one pane, Yazi with git status marks and a Leaf-rendered Markdown preview in another, and
`hunk diff --watch` in a third showing the agent's edits as they land. Add the file as
docs/assets/hero.png and replace this comment with:

![Ghostty running Herdr, Yazi and hunk side by side](docs/assets/hero.png)
-->

## What you get

- **A terminal that follows the system appearance** — [Ghostty](https://ghostty.org) with a light
  and a dark Catppuccin theme, JetBrains Mono, and native macOS notifications when a long command
  or a coding agent finishes in a pane you are not looking at.
- **A file manager built for reading code** — [Yazi](https://yazi-rs.github.io) renders Markdown in
  its preview pane through [Leaf](https://github.com/RivoLink/leaf), including Mermaid diagrams,
  uses a dark Ocean theme for Markdown reading, opens text in
  [micro](https://micro-editor.github.io), and marks the git status of every file and directory.
- **A live diff pane for agent work** — [hunk](https://hunk.dev) redraws the whole working-tree
  diff as a coding agent edits it, so review happens while the change lands rather than afterwards.
  Three git aliases open a commit, a branch or a GitHub pull request in the same viewer.
- **git push that just works** — a new branch creates and tracks its remote on the first push, and
  the popular workaround that misreports your branch is explained and rejected.
- **"Your agent finished" notifications that survive a multiplexer** — one setting that reaches
  Claude Code in Ghostty, in [Herdr](https://herdr.dev) and in Zed's Terminal Threads.
- **One command for the tools** — a `Brewfile` covering Ghostty, Zed, Herdr, Yazi, hunk, micro,
  Leaf, the GitHub CLI and four coding-agent CLIs, and a `setup.sh` that installs it convergently.
- **Nothing installed over your own configuration.** Every managed file is reached through the
  tool's own include mechanism, your existing settings are preserved byte for byte, and your git
  identity is never touched.

## Quick Start

### Before you start

- **macOS only.** Everything here is verified on macOS 26 with Apple silicon. Older releases are
  untested; nothing here knowingly needs 26, but nothing has been run there either.
- **Homebrew is installed for you** if it is missing. Its installer asks for your password and
  pulls in the Xcode Command Line Tools when they are absent.
- **git 2.37 or newer** — the push defaults are silently inert on older git. The Command Line
  Tools ship a recent enough version.
- **Time and disk.** The `Brewfile` includes `ffmpeg`, `imagemagick` and four GUI apps; a first
  run takes a while and a few gigabytes.
- **What gets written.** Four small files in your home directory, each backed up first. The
  [manual setup](docs/manual-setup.md#before-you-start) lists every one, and how to put it back.

### Three steps

1. **Clone the repository:**
   ```sh
   git clone https://github.com/theultimate-dev/dotfiles.git
   cd dotfiles
   ```

2. **Install the tools** (Homebrew, casks, agent CLIs, Herdr integrations):
   ```sh
   ./setup.sh
   ```

3. **Place the configuration** (offline, atomic, no symlinks):
   ```sh
   ./install.sh
   ```

Then open a new shell. Browser logins for the coding agents, API keys, and one macOS notification
toggle cannot be scripted; [Manual setup](docs/manual-setup.md) walks through them, in order, each
with a check and an undo.

> **Status:** this repo is being built in the open. Tool installation, git defaults, and the
> Ghostty, Yazi and hunk configurations are live; the shell configuration and runtime versions
> follow. [`CHANGELOG.md`](CHANGELOG.md) tracks what has arrived.

## The tools

Every tool here is someone else's work; this repo only installs and configures it. The links go
to the projects.

| Tool | What it is here |
|---|---|
| [Ghostty](https://ghostty.org) | The terminal. Managed config; machine-local overrides in `local.ghostty`. |
| [Herdr](https://herdr.dev) | A terminal multiplexer built for running coding agents in panes. Installed, not configured here. |
| [Yazi](https://yazi-rs.github.io) | Terminal file manager. Managed config, reached through `YAZI_CONFIG_HOME`. |
| [hunk](https://hunk.dev) | Read-only diff viewer with a live watch mode. Managed config, copied. |
| [micro](https://micro-editor.github.io) | Terminal editor for quick edits beside a running agent. |
| [Leaf](https://github.com/RivoLink/leaf) | Markdown reader; Yazi's preview and its `.md` opener. |
| [Zed](https://zed.dev) | GUI editor. Installed; its settings stay yours. |
| [T3 Code](https://t3.codes) | An alpha GUI control plane for coding agents. Installed; needs your own provider keys. |
| [Claude Code](https://claude.ai/code) | Anthropic's agent CLI. Installed by its own installer, deliberately not through Homebrew. |
| [Codex](https://github.com/openai/codex), [Copilot CLI](https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli), [Antigravity CLI](https://antigravity.google/product/antigravity-cli) (`agy`), [Grok Build](https://x.ai/build) | The other agent CLIs, all from the `Brewfile`. |
| [GitHub CLI](https://cli.github.com) | Feeds a pull request into hunk for review. |

## Platform

**macOS only.** This is my daily driver, and it is the only platform any of this is developed,
used, or tested on. The installer targets macOS's system bash 3.2 and coreutils so that it keeps
working on a machine where everything else is broken. Linux and WSL are not supported and not
planned — you are welcome to lift whatever is useful, but nothing here has been run there.

## What's here, and what isn't

This repo holds configuration and never holds identity. Anything that names a person, a machine or
an account stays on your machine, untracked, and the docs say where.

| | This repo | Stays on your machine |
|---|---|---|
| **git** | push and branch-tracking defaults, review aliases | `[user]` identity, signing keys, everything else in your `~/.gitconfig` |
| **terminal** | the Ghostty configuration | machine-specific display and font tweaks, in `local.ghostty` |
| **files** | the Yazi configuration: openers, Markdown preview, git status marks | nothing — Yazi reads one directory, so there is no local layer |
| **review** | the hunk configuration | a per-project `.hunk/config.toml`, if a repository needs one |
| **shell** *(planned)* | the zsh configuration | secrets, tokens, anything host-specific |

The git line is the one worth stating outright: **this repo will never contain a `[user]`
section.** No name, no email, no signing key. Your identity lives in your own `~/.gitconfig`, which
is exactly where git already expects to find it.

That is only practical because of the delivery model below. This repo is included from
`~/.config/git/config`; your own settings stay in `~/.gitconfig`; git reads the first before the
second — so the defaults here land underneath everything you have ever set, and nothing this repo
does can override you. A farm of symlinks structurally cannot do this: there is only one
`~/.gitconfig`, and whatever installs second wins the whole file.

## How configs are delivered

Most dotfiles repos symlink `~/.zshrc` into the repo. This one does not.

Instead, the installer writes a small **real file** at each destination that redirects into the
repo using the target tool's own native include directive:

| Destination | Redirect |
|---|---|
| `~/.config/git/config` — never `~/.gitconfig` | `[include] path = <repo>/git/.gitconfig` |
| `~/.config/ghostty/config.ghostty` | `config-file = <repo>/ghostty/config.ghostty` |
| `~/.zshenv` | `export YAZI_CONFIG_HOME=<repo>/yazi` — Yazi has no include directive; the variable names the directory |
| `~/.config/hunk/config.toml` | byte copy — hunk offers no include directive and no config variable |

Planned, with the mechanism already decided:

| Destination | Redirect |
|---|---|
| `~/.zshrc` | `source <repo>/zsh/.zshrc` |
| `~/.tool-versions` | byte copy — asdf has no include mechanism |
| `scripts/` | added to `$PATH`; no file installed |

You keep everything symlinks gave you — the repo is the live source of truth, an edit takes effect
immediately, and `git diff` audits your entire configuration — and you lose the parts that hurt:

- `ln -sf` silently destroys a real file that was already there. No warning, no backup.
- A symlink farm hardcodes where the repo lives. Clone it somewhere else and you get dangling links,
  no error, and a shell that quietly loses half its config.
- Some tools and backup/sync agents handle symlinked dotfiles badly.

The cost is that each tool's include semantics differ, and two of them are opposites: **git's stub
overrides the repo, while Ghostty's repo overrides the stub.** That is the one thing worth
internalizing before editing anything here. The third kind, an environment variable that names the
repo directory, has no precedence at all: Yazi reads that one directory, and nothing else.

### Included, never installed over your git config

This is the second promise, and it is the one that matters if you already have a git configuration
you care about.

`install.sh` owns exactly one destination for git —
`~/.config/git/config`, strictly `${XDG_CONFIG_HOME:-$HOME/.config}/git/config` — where it
writes a named, delimited block (`# BEGIN dotfiles (public)` ... `# END dotfiles (public)`)
and preserves every other byte of that file.

It will never write `~/.gitconfig`. That is where essentially everyone keeps their identity, their
aliases, and years of accumulated settings, and this repo has no business editing it. There is one
exception, and it is a create rather than an overwrite: if you have no `~/.gitconfig` at all, the
installer creates an empty one. Without it, git's `--global` *write* target becomes the XDG
file, and the next `git config --global …` you run would put your identity inside a file this repo
manages.

This is what makes the promise **structural rather than conventional.** git reads
`~/.config/git/config` *before* `~/.gitconfig`, and the later value wins. Every setting you have
ever put in your own config therefore beats everything this repo ships, automatically. There is no
line ordering to get right inside a file we share, because we do not share one — this repo is a
defaults layer by construction.

The same mechanism is what lets anything else that manages `~/.gitconfig` — another tool, a work
setup, or just your own edits — coexist with this repo: it keeps `~/.gitconfig`, this one keeps
the XDG file, and neither touches the other's destination.

`install.sh` writes this include stub automatically with pre-modification backups and atomic writes.
See [ADR 0006](docs/decisions/0006-manage-shared-destinations-with-delimited-blocks.md).

## Installation

Installation follows the two-script split:

```sh
./setup.sh     # installs tools: Homebrew, runtimes, anything touching the network
./install.sh   # places config: writes native stubs atomically (offline, no symlinks)
```

The split exists so that config placement never depends on the network and stays debuggable on a
half-broken machine.

`setup.sh` installs the daily tools via Homebrew (Ghostty, micro, hunk, Yazi and Leaf with the
tools Yazi previews through, Zed, T3 Code, Herdr, and coding agent CLIs), restores Yazi's plugins
from the tracked lockfile, and configures Herdr agent integrations. Re-running it is safe and
convergent. An app installed by hand before is left alone and reported; `./setup.sh --adopt`
hands it to Homebrew, after explaining the macOS permission prompt that needs.

`install.sh` places configuration stubs using native include directives and named delimited blocks,
and copies the one config whose tool offers no include mechanism at all. It supports two
non-destructive flags:

- `./install.sh --dry-run` — preview planned changes without modifying any files.
- `./install.sh --check` — verify drift against expected stubs; exits 0 if current, 1 if drifted.

Interactive steps (agent installs and logins, API keys, and notification permissions) remain
manual — see [Manual setup](docs/manual-setup.md).

## Repository layout

| Path | Contents |
|---|---|
| [`AGENTS.md`](AGENTS.md) | The working agreement — rules for contributors and coding agents |
| [`CLAUDE.md`](CLAUDE.md) | Claude Code guidance; imports `AGENTS.md` |
| [`CHANGELOG.md`](CHANGELOG.md) | Every notable change, newest first |
| [`Brewfile`](Brewfile) | Declarative package list installed via Homebrew |
| [`setup.sh`](setup.sh) | Tool installation and Herdr agent integration script |
| [`install.sh`](install.sh) | Configuration placement script (atomic writes, no symlinks) |
| `git/` | Managed git configuration |
| `ghostty/` | Managed Ghostty configuration |
| `yazi/` | Managed Yazi configuration; `plugins/` inside it is restored by `setup.sh` and untracked |
| `hunk/` | Managed hunk configuration; copied to its destination rather than included |
| [`LICENSE`](LICENSE) | MIT — see [Licence and scope](#licence-and-scope) |
| `docs/` | Deep dives on the pieces whose reasoning is not obvious from the code |
| [`docs/decisions/`](docs/decisions/README.md) | Architecture decision records, with an index — why a choice was made, and what was rejected |

## Documentation

- [Manual setup](docs/manual-setup.md) — the only page here with commands to run by hand: every
  step from a fresh clone to a configured machine, in order, each with a way to verify it and a way
  to undo it. Start here. The pages below explain *why* each of those choices was made.
- [Decision records](docs/decisions/README.md) — the choices that outlive the change that
  introduced them, each in five terse sections with the alternative that lost. The index has one
  line per decision; start with
  [0001](docs/decisions/0001-deliver-configs-as-include-stubs-not-symlinks.md) for the no-symlink
  model, [0002](docs/decisions/0002-include-git-config-from-xdg-never-gitconfig.md) for why this
  repo never writes your `~/.gitconfig`, and
  [0010](docs/decisions/0010-export-a-config-directory-variable-from-zshenv.md) for the one tool
  reached through an environment variable instead of a stub.
- [Agent tooling & installation](docs/agent-tooling.md) — why Homebrew is used for all daily tools,
  how `auto_updates` casks behave, the Herdr integration lifecycle, and how to avoid installer traps
  when juggling multiple coding agents on macOS.
- [hunk](docs/hunk.md) — a live diff pane for watching a coding agent edit the working tree as it
  happens, rather than reading the whole changeset afterwards, plus how to review a commit, a
  branch or a GitHub pull request with the same viewer. Also: why a read-only viewer beats a git
  client in a pane beside a running agent, why this one config is copied instead of included, the
  TOML rule that makes a shared block impossible, and the git alias trap that makes a relative
  pathspec vanish.
- [Yazi](docs/yazi.md) — a terminal file manager that opens files in micro, reads Markdown in
  Leaf with micro one menu away, renders Markdown in its preview pane, and marks git status next
  to every file. Also: why its config is delivered through `YAZI_CONFIG_HOME` in `~/.zshenv`
  rather than a stub, why that means no machine-local override, why the Markdown rule matches the
  file name and not the mime type, and which of your two terminals needs a Nerd Font for the
  icons.
- [Git push defaults](docs/git-push-defaults.md) — why `push.autoSetupRemote = true` on its own does
  not do what everyone expects, why `branch.autoSetupMerge = simple` is the other half of it, and
  why the popular `push.default = current` workaround is worse than the problem: the push succeeds,
  but git then misreports your branch instead of erroring.
- [Herdr notifications on macOS](docs/herdr-notifications.md) — how to get reliable "your agent
  finished" notifications when running coding agents inside [Herdr](https://herdr.dev) in
  [Ghostty](https://ghostty.org). A multiplexer swallows the escape sequence your agent emits, so
  the terminal-side setup you already have goes quiet; this covers what to configure instead, why
  `delivery = "system"` beats the intuitive choice, and when it doesn't. Also: the one macOS toggle
  that makes a notification stay on screen, what the badge on Ghostty's Dock icon is, and how the
  same Claude Code setting reaches Zed's Terminal Threads.

## Who is behind this

I am [Igor Wnęk](https://github.com/IgorWnek), a senior agentic product engineer. This is the
stack I use every day, shared as it is. It lives under
[The Ultimate Dev](https://github.com/theultimate-dev), where the org profile says what that is
and lists the other repositories.

## Contributing and support

This is a working setup published as-is, not a product. Read it, lift from it, or install it
whole; the licence below covers all three. Issues are welcome for anything that misbehaves on a
fresh machine, and pull requests for fixes are welcome too. A change to what gets installed or how
a file lands in `$HOME` needs the reasoning written down first, and [`AGENTS.md`](AGENTS.md) is
the working agreement that says how: it binds human contributors and coding agents alike.

## Conventions

This repo runs on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
[Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html),
[Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/), and
[Michael Nygard's ADR format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
for [`docs/decisions/`](docs/decisions/README.md).

Releases are cut from tags: a `vX.Y.Z` tag on `main` becomes a GitHub Release whose notes are that
version's section of the changelog.

## Licence and scope

The configuration, scripts, and documentation in this repository are MIT licensed — see
[`LICENSE`](LICENSE). Take them, change them, ship them.

That covers **my configuration and nothing else.** The tools shown here — the editors, terminals,
shells, and utilities — belong to their respective authors and are distributed under their own
licences and terms. I have no rights over any of them and claim none. Nothing in this repository
implies affiliation with, sponsorship by, or endorsement from any of the projects or companies
whose tools appear in it. What is on offer is how I install and configure the things I use daily,
and that is all.
