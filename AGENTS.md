# AGENTS.md

Working agreement for **The Ultimate Dev — Dotfiles**. It binds every coding agent and human
contributor. `CLAUDE.md` imports this file; Claude-specific notes live there and nowhere else.

## What this repo is

The public share of a personal macOS development stack — everything from a private `~/dotfiles`
that can be made public and is worth sharing.

**Current state:** documentation only. The installer and the configuration are ported in over time.
The delivery model below is not aspirational — it is proven in the private original and is binding
for every file that lands here.

**macOS only.** The maintainer's daily driver, and the only platform anything here is developed or
tested on. Do not add Linux or WSL branches to make something "portable"; untested portability is
worse than a documented limit.

### Scope — what belongs here

This repo is the **public** half of a two-repo split. A separate private repo holds identity,
credentials, and client- and machine-specific configuration. The boundary:

| Belongs here | Stays in the private repo |
|---|---|
| Configuration any developer could adopt as-is | Anything naming a person, employer, client, or host |
| Tool setup, aliases, keybindings, themes | `[user]` identity, signing keys, tokens |
| The reasoning behind a choice — including rejected ones | Directory-conditional routing keyed on private paths |

Two consequences that are easy to get wrong:

- **This repo will never contain a `[user]` section**, in any file, in any form — not even a
  placeholder. See *Public-repo hygiene* below.
- **Not every tool here is a managed config.** Some are documented or linked only — an app worth
  recommending that needs no configuration, or whose setup is better covered by its own docs. That
  is in scope. A `docs/` page that installs and explains a tool is a legitimate contribution with
  no accompanying config directory.

---

## Rule #1 — No symlinks

**Nothing in this repo ever creates a symlink in `$HOME`.** No `ln -s`. Not in the installer, not in
a helper script, not "just for this one file."

Instead, the installer writes a small **real file** at each destination that redirects into the repo
using the target tool's *own* native include directive:

| Destination | Redirect mechanism |
|---|---|
| `~/.zshrc` | `source <repo>/zsh/.zshrc` |
| `~/.gitconfig` | `[include] path = <repo>/git/.gitconfig` |
| `~/.config/ghostty/config.ghostty` | `config-file = <repo>/ghostty/config.ghostty` |
| `~/.tool-versions` | byte copy — asdf has no include mechanism |
| `scripts/` | `<repo>/scripts` prepended to `$PATH`; no file installed |

This keeps the one property that made symlinks attractive — **the repo is the live source of truth,
edits take effect with no reinstall, and `git diff` audits the whole configuration** — without the
symlinks themselves.

Why symlinks are rejected outright:

- `ln -sf` silently clobbers a pre-existing real file. No warning, no backup.
- A symlink farm hardcodes the repo location. Clone elsewhere and you get dangling links, no error,
  and a shell that quietly loses half its config.
- Symlinked dotfiles confuse some tools and backup/sync agents.

If a change appears to require a symlink, it requires a different design. Raise it; do not add one.

### Adding a new destination

1. Prefer the tool's own include directive, and generate a stub containing it.
2. If the tool has no include mechanism, copy the file — and make the installer *report* drift
   rather than pretend to prevent it.
3. If the tool can be reached through `$PATH`, install no file at all.

---

## Hard invariants

Each of these, when violated, fails silently, late, or both.

**No machine-specific absolute paths in tracked files.** Every absolute path is generated into a
stub by the installer, which resolves the repo root itself. This is what makes the repo
clone-anywhere. A tracked file containing a home-directory path is a bug, not a detail.

**The installer depends on bash 3.2 and coreutils. Nothing else.** No `brew`, no `git`, no network —
config delivery has to stay debuggable on a half-broken machine. bash 3.2 is macOS's system bash: no
associative arrays, no `mapfile`, no `${var^^}`.

**Keep the two-script split.** Tool *installation* — Homebrew, runtimes, anything touching the
network — belongs in `setup.sh`. Config *placement* belongs in `install.sh`. Never move network
access into the installer.

**Never clobber silently.** Anything unmanaged at a destination is backed up, with a manifest,
before it is replaced. Writes are atomic: render to a temp file in the same directory, then `mv`.
Re-running an unchanged install is a true no-op. Ambiguity is a hard error, never a guess.

**This repo is never the sole manager of a destination file.** It is installed alongside a second,
private dotfiles repo on the same machine, and both want to write `~/.gitconfig`. The installer
therefore owns a **named, delimited block** — its own BEGIN/END markers — and preserves every byte
outside it. It may not own "everything above a sentinel", and it may not rewrite a destination
wholesale.

> The known trap, from the private original: a single-sentinel scheme that regenerates everything
> above the line and preserves only what is below cannot compose. Install two repos that both do
> this and each run silently erases the other's block. Whichever ran last appears to work, which is
> what makes it expensive to diagnose.
>
> The concrete mechanism is still an open design decision. Settle it — and write it up as an ADR —
> when `install.sh` lands. Do not let an installer merge without it.

**git and Ghostty have opposite include precedence.** This is the single most surprising thing here:

| | Who wins | Machine-local overrides go |
|---|---|---|
| **git** | the **stub** — includes expand in place, so anything below the include beats the repo | `~/.gitconfig`, below the sentinel line |
| **Ghostty** | the **repo** — `config-file` is processed at the *end* of the containing file | `~/.config/ghostty/local.ghostty` |
| **zsh** | **local** — later lines win | `~/.config/dotfiles/local.zsh`, sourced last |

Practical consequence: `git config --global …` writes into the stub, not into this repo, and wins
over it. That is intentional — the stub is the machine-local override layer — but it means such
edits never show up in `git status` here.

**The Powerlevel10k instant-prompt block stays first in `zsh/.zshrc`,** with nothing above it that
can write to the terminal.

---

## Public-repo hygiene

This repo is public. The private original is not, and its files are not safe to copy verbatim.

Never commit, in any tracked file:

- Real email addresses, GPG or SSH key IDs and fingerprints, tokens, API keys
- Employer names, client names, or work-specific directory paths
- Hostnames, machine names, or home-directory paths

Personal configuration ships as a **placeholder template** plus a documented machine-local override:

| Kind | This repo holds | Real values live in |
|---|---|---|
| Git identity | **nothing — no `[user]` section, ever** | `~/.gitconfig`, below the sentinel — untracked |
| Secrets, tokens | nothing | `~/.config/dotfiles/local.zsh` — untracked, `chmod 600` |
| Machine-specific terminal settings | nothing | `~/.config/ghostty/local.ghostty` |

The git identity row is stronger than the others and deliberately so: **not a placeholder, not a
template, nothing at all.** A `[user]` section holding a dummy address is still an address-shaped
string in a public repo, it is one careless edit away from being a real one, and it defeats the
check below — which cannot tell a placeholder from the real thing, and should not have to. Git
already looks in `~/.gitconfig` for identity; leave it there and ship none.

This rule is load-bearing for the check in *Verifying a change*: it is what lets that grep demand
**zero** matches rather than maintaining an allowlist of "safe" example domains. Write the rule
down in prose without ever writing a specimen address — including in this file.

**Porting a file from the private repo is a sanitizing operation, not a copy.** Read it, strip the
personal values, replace them with placeholders, and grep the result before staging it.

---

## Changelog — Keep a Changelog 1.1.0

This repo follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

**Every user-facing change updates `CHANGELOG.md` under `## [Unreleased]` in the same change that
makes it.** Not afterwards, not at release time.

The parts that are easy to get wrong:

- Categories are exactly `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`. Use them
  verbatim; do not invent new ones, and omit the ones with nothing under them.
- Newest version first. Dates are ISO-8601 (`YYYY-MM-DD`).
- Entries are written **for a human reading them later**, not derived from commit subjects. Say what
  changed for someone running these dotfiles, and what they have to do about it.
- An `[Unreleased]` section stays at the top at all times.
- Version headings resolve through link references kept at the bottom of the file.
- Released entries are not edited or deleted. A mistake in a released entry is corrected by a new
  entry, not by rewriting the old one.

### What the version numbers mean here

| Bump | Meaning in a dotfiles repo | Examples |
|---|---|---|
| **MAJOR** | The user must act — re-run the installer, or move something | Stub format changed; a destination path moved; a managed config removed |
| **MINOR** | New capability, no action required | A newly managed config, a new script on `$PATH`, a new tool in `Brewfile` |
| **PATCH** | Fix or refinement, no action required | Corrected alias, documentation fix, installer edge case |

Anything in the MAJOR row is also a breaking change in its commit — see below.

---

## Commits — Conventional Commits 1.0.0

Format is `type(scope): description`, per
[Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).

- **Descriptions are past tense** — `feat(zsh): added a notification for long-running commands`.
- **Scope is optional but preferred**, naming the top-level directory or subject: `install`,
  `setup`, `zsh`, `git`, `ghostty`, `scripts`, `brew`, `asdf`, `docs`, `claude`.
- **One self-contained unit of work per commit.** Unrelated changes get their own commits; when the
  working tree mixes them, split rather than bundle.
- **Breaking changes** — anything in the MAJOR row above — take a `!` after the type or scope *and*
  a `BREAKING CHANGE:` footer saying what the user must re-run or move.

How types map onto changelog categories:

| Type | Changelog category |
|---|---|
| `feat` | Added — or Changed, when it alters existing behaviour |
| `fix` | Fixed |
| `refactor`, `perf`, `style` | Changed when user-visible; usually no entry |
| `docs`, `test`, `build`, `ci`, `chore` | usually no entry |
| a feature removed | Removed |
| something marked for future removal | Deprecated |
| a vulnerability or exposure fixed | Security |

**Do not create commits unless the current request explicitly asks for one.** Stage and prepare the
work; the commit itself is the maintainer's call.

---

## Verifying a change

Available today, in a documentation-only repo:

```bash
# No home-directory paths. The character class keeps the pattern from matching
# this very file; --untracked is required or newly added files are skipped.
git grep -nI --untracked '/User[s]/'

# No stray email addresses
git grep -nIE --untracked '[[:alnum:]._%+-]+@[[:alnum:].-]+\.[[:alpha:]]{2,}'
```

Both must print nothing. `git grep` searches only tracked files unless you pass `--untracked`, so
omitting it lets a brand-new file through the check unexamined.

**These greps are a floor, not a ceiling.** The hygiene rules above also ban hostnames, machine
names, employer and client names, and work-specific directory paths — and *no grep can catch
those*, because they are ordinary words until you know the context. They are caught by reading the
diff before staging it, and by nothing else. A clean grep run means the two mechanical traps are
clear; it does not mean the change is safe to publish.

Once the installer is ported, every change to shell code must also pass:

```bash
bash -n install.sh setup.sh   # syntax check; no dependencies
./install.sh --dry-run        # show exactly what would change; touch nothing
./install.sh --check          # report drift; exit non-zero if anything is off
```

`shellcheck` is not currently installed on the maintainer's machine. If you have it, running it is
welcome — but it does not replace `--dry-run` and `--check`.

---

## Documentation conventions

- `README.md` is the entry point: what this is, what is in scope, how it installs, and the
  no-symlink promise.
- `docs/` holds deep dives for the pieces whose *rationale* is non-obvious — the reasoning that
  would otherwise be lost, including rejected alternatives and upstream bugs worked around.
  `docs/herdr-notifications.md` sets the expected depth and tone.
- `docs/manual-setup.md` is the exception, and the only one: a **how-to**, not a deep dive. It
  holds every command a reader runs by hand, in order, with a verify and an undo for each. It
  carries no rationale beyond a one-line pointer into the `docs/` page that explains the choice.
- **A command that writes to `$HOME` appears exactly once in the repository.** Procedures live in
  `docs/manual-setup.md`; the reasoning behind them lives in `docs/`. A deep dive may name a
  setting in prose, but a second copy-pasteable block is a defect — two copies of a command that
  edits a live machine will drift, and nothing here can check them against each other.
- Document the trap, not the API. If a behaviour surprised you, that is the paragraph worth writing.
- **Wrap prose at 100 columns.** Tables, code blocks, and long URLs are exempt — never break those
  to fit. Consistent width keeps `git diff` readable when a paragraph is edited years later.
