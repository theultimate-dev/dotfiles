# The Ultimate Dev — Dotfiles

My macOS development stack, shared publicly: shell, terminal, git, runtimes, and the tooling that
holds them together.

**No symlinks.** Not one. See [How configs are delivered](#how-configs-are-delivered).

**Included, never installed over your git config.** The installer will own one named block in
`~/.config/git/config`; it will never write your `~/.gitconfig`. See
[why that is structural, not a convention](#included-never-installed-over-your-git-config).

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
| **git** | push and branch-tracking defaults, aliases, pager and diff setup, a global ignore file | `[user]` identity, signing keys, per-client directory routing |
| **zsh** | the shell configuration itself | secrets, tokens, anything host-specific |
| **terminal** | the Ghostty configuration | machine-specific display and font tweaks |

The git line is the one worth stating outright: **this repo will never contain a `[user]`
section.** No name, no email, no signing key. Your identity lives in your own `~/.gitconfig`, which
is exactly where git already expects to find it.

That split is only practical because of the delivery model below. Two separate dotfiles repos can
sit on one machine because they write to two different files: this one is included from
`~/.config/git/config`, the private one keeps `~/.gitconfig`, and git reads the first before the
second — so public defaults land underneath private configuration, and neither installer touches
the other's destination. A farm of symlinks structurally cannot do this: there is only one
`~/.gitconfig`, and whichever repo you install second wins the whole file.

## How configs are delivered

Most dotfiles repos symlink `~/.zshrc` into the repo. This one does not.

Instead, the installer will write a small **real file** at each destination that redirects into the
repo using the target tool's own native include directive:

| Destination | Redirect |
|---|---|
| `~/.zshrc` | `source <repo>/zsh/.zshrc` |
| `~/.config/git/config` — never `~/.gitconfig` | `[include] path = <repo>/git/.gitconfig` |
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

### Included, never installed over your git config

This is the second promise, and it is the one that matters if you already have a git configuration
you care about.

`install.sh` has not landed. When it does, it will own exactly one destination for git —
`~/.config/git/config`, strictly `${XDG_CONFIG_HOME:-$HOME/.config}/git/config` — where it will
write a named, delimited block and preserve every other byte of that file.

It will never write `~/.gitconfig`. That is where essentially everyone keeps their identity, their
aliases, and years of accumulated settings, and this repo has no business editing it. There is one
exception, and it is a create rather than an overwrite: if you have no `~/.gitconfig` at all, the
installer will create an empty one. Without it, git's `--global` *write* target becomes the XDG
file, and the next `git config --global …` you run would put your identity inside a file this repo
manages.

This is what makes the promise **structural rather than conventional.** git reads
`~/.config/git/config` *before* `~/.gitconfig`, and the later value wins. Every setting you have
ever put in your own config therefore beats everything this repo ships, automatically. There is no
line ordering to get right inside a file we share, because we do not share one — this repo is a
defaults layer by construction.

The same mechanism is what lets a second, private dotfiles repo coexist. It keeps `~/.gitconfig`,
this one keeps the XDG file, and neither installer reads or writes the other's destination: no
sentinel to agree on, no install-order dependency.

Until `install.sh` lands, activation is manual: one `[include]` appended to the XDG git config.
[Manual setup, step 4](docs/manual-setup.md#4-git-push-defaults) has the command, the check that
proves it took effect, and the way to undo it.

## Installation

Installation follows the two-script split:

```sh
./setup.sh     # installs tools: Homebrew, runtimes, anything touching the network
./install.sh   # places config: writes the stubs above, and nothing else (not yet landed)
```

**Until `install.sh` lands, configuration is placed by hand** — see
[Manual setup](docs/manual-setup.md). It is the only page here that contains commands you run
yourself: every step in order, each with a way to check it worked and a way to undo it. Several of
those steps stay manual no matter what the installer does, because no script can complete an OAuth
login or type an API key on your behalf.

`setup.sh` installs the daily tools via Homebrew (Ghostty, Zed, T3 Code, Herdr, and coding agent
CLIs) and configures Herdr agent integrations. Re-running it is safe and convergent.

The split exists so that config placement never depends on the network and stays debuggable on a
half-broken machine. `install.sh` will land in a subsequent change; it will support `--dry-run` to
show exactly what it would change and `--check` to report drift without touching anything.

Watch [`CHANGELOG.md`](CHANGELOG.md) for when it lands. The steps it takes over are listed at the
end of [Manual setup](docs/manual-setup.md#what-the-installer-will-take-over).

## Repository layout

| Path | Contents |
|---|---|
| [`AGENTS.md`](AGENTS.md) | The working agreement — rules for contributors and coding agents |
| [`CLAUDE.md`](CLAUDE.md) | Claude Code guidance; imports `AGENTS.md` |
| [`CHANGELOG.md`](CHANGELOG.md) | Every notable change, newest first |
| [`Brewfile`](Brewfile) | Declarative package list installed via Homebrew |
| [`setup.sh`](setup.sh) | Tool installation and Herdr agent integration script |
| `git/` | Managed git configuration |
| [`LICENSE`](LICENSE) | MIT — see [Licence and scope](#licence-and-scope) |
| `docs/` | Deep dives on the pieces whose reasoning is not obvious from the code |
| [`docs/decisions/`](docs/decisions/) | Architecture decision records — why a choice was made, and what was rejected |

## Documentation

- [Manual setup](docs/manual-setup.md) — the only page here with commands to run by hand: every
  step from a fresh clone to a configured machine, in order, each with a way to verify it and a way
  to undo it. Start here. The pages below explain *why* each of those choices was made.
- [Agent tooling & installation](docs/agent-tooling.md) — why Homebrew is used for all daily tools,
  how `auto_updates` casks behave, the Herdr integration lifecycle, and how to avoid installer traps
  when juggling multiple coding agents on macOS.
- [Decision records](docs/decisions/) — the choices that outlive the change that introduced them,
  each in five terse sections with the alternative that lost. Start with
  [0001](docs/decisions/0001-deliver-configs-as-include-stubs-not-symlinks.md) for the no-symlink
  model and [0002](docs/decisions/0002-include-git-config-from-xdg-never-gitconfig.md) for why this
  repo never writes your `~/.gitconfig`.
- [Git push defaults](docs/git-push-defaults.md) — why `push.autoSetupRemote = true` on its own does
  not do what everyone expects, why `branch.autoSetupMerge = simple` is the other half of it, and
  why the popular `push.default = current` workaround is worse than the problem: the push succeeds,
  but git then misreports your branch instead of erroring.
- [Herdr notifications on macOS](docs/herdr-notifications.md) — how to get reliable "your agent
  finished" notifications when running coding agents inside [Herdr](https://herdr.dev) in
  [Ghostty](https://ghostty.org). A multiplexer swallows the escape sequence your agent emits, so
  the terminal-side setup you already have goes quiet; this covers what to configure instead, why
  `delivery = "system"` beats the intuitive choice, and when it doesn't.

## Conventions

This repo runs on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
[Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html),
[Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/), and
[Michael Nygard's ADR format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
for [`docs/decisions/`](docs/decisions/).
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
