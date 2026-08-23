# The Ultimate Dev — Dotfiles

My macOS development stack, shared publicly: shell, terminal, git, runtimes, and the tooling that
holds them together.

**No symlinks.** Not one. See [How configs are delivered](#how-configs-are-delivered).

> **Status:** this repo is being built in the open. Documentation lands first; the installer and the
> configuration follow. [`CHANGELOG.md`](CHANGELOG.md) tracks what has arrived.

## Platform

**macOS only.** This is my daily driver, and it is the only platform any of this is developed,
used, or tested on. The installer targets macOS's system bash 3.2 and coreutils so that it keeps
working on a machine where everything else is broken. Linux and WSL are not supported and not
planned — you are welcome to lift whatever is useful, but nothing here has been run there.

## What's here, and what isn't

This repo holds only what can go public and is worth sharing. A separate, private repo holds the
rest: identity, credentials, client-specific and machine-specific configuration. That split is a
rule, not an accident, and it shapes what you will find here.

| | This repo | Stays private / machine-local |
|---|---|---|
| **git** | aliases, pager and diff setup, a global ignore file | `[user]` identity, signing keys, per-client directory routing |
| **zsh** | the shell configuration itself | secrets, tokens, anything host-specific |
| **terminal** | the Ghostty configuration | machine-specific display and font tweaks |

The git line is the one worth stating outright: **this repo will never contain a `[user]`
section.** No name, no email, no signing key. Your identity lives in your own `~/.gitconfig`, which
is exactly where git already expects to find it.

That split is only practical because of the delivery model below. Two separate dotfiles repos can
compose into a single `~/.gitconfig` through ordered include directives — public defaults first,
private configuration after, machine-local edits last. A farm of symlinks structurally cannot do
this: there is only one `~/.gitconfig`, and whichever repo you install second wins the whole file.

## How configs are delivered

Most dotfiles repos symlink `~/.zshrc` into the repo. This one does not.

Instead, the installer will write a small **real file** at each destination that redirects into the
repo using the target tool's own native include directive:

| Destination | Redirect |
|---|---|
| `~/.zshrc` | `source <repo>/zsh/.zshrc` |
| `~/.gitconfig` | `[include] path = <repo>/git/.gitconfig` |
| `~/.config/ghostty/config.ghostty` | `config-file = <repo>/ghostty/config.ghostty` |
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
internalizing before editing anything here.

## Installation

**Not yet.** The installer has not landed — this repo is documentation for now. When it arrives it
will be two commands, deliberately kept apart:

```sh
./setup.sh     # installs tools: Homebrew, runtimes, anything touching the network
./install.sh   # places config: writes the stubs above, and nothing else
```

The split exists so that config placement never depends on the network and stays debuggable on a
half-broken machine. `install.sh` will support `--dry-run` to show exactly what it would change,
and `--check` to report drift without touching anything.

Watch [`CHANGELOG.md`](CHANGELOG.md) for when it lands.

## Repository layout

| Path | Contents |
|---|---|
| [`AGENTS.md`](AGENTS.md) | The working agreement — rules for contributors and coding agents |
| [`CLAUDE.md`](CLAUDE.md) | Claude Code guidance; imports `AGENTS.md` |
| [`CHANGELOG.md`](CHANGELOG.md) | Every notable change, newest first |
| [`LICENSE`](LICENSE) | MIT — see [Licence and scope](#licence-and-scope) |
| `docs/` | Deep dives on the pieces whose reasoning is not obvious from the code |

## Documentation

- [Herdr notifications on macOS](docs/herdr-notifications.md) — how to get reliable "your agent
  finished" notifications when running coding agents inside [Herdr](https://herdr.dev) in
  [Ghostty](https://ghostty.org). A multiplexer swallows the escape sequence your agent emits, so
  the terminal-side setup you already have goes quiet; this covers what to configure instead, why
  `delivery = "system"` beats the intuitive choice, and when it doesn't.

## Conventions

This repo runs on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
[Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html), and
[Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).
[`AGENTS.md`](AGENTS.md) is the full contract; it binds human contributors and coding agents alike.

## Licence and scope

The configuration, scripts, and documentation in this repository are MIT licensed — see
[`LICENSE`](LICENSE). Take them, change them, ship them.

That covers **my configuration and nothing else.** The tools shown here — the editors, terminals,
shells, and utilities — belong to their respective authors and are distributed under their own
licences and terms. I have no rights over any of them and claim none. Nothing in this repository
implies affiliation with, sponsorship by, or endorsement from any of the projects or companies
whose tools appear in it. What is on offer is how I install and configure the things I use daily,
and that is all.
