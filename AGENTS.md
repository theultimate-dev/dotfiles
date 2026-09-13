# AGENTS.md

Working agreement for **The Ultimate Dev — Dotfiles**. It binds every coding agent and human
contributor. `CLAUDE.md` imports this file; Claude-specific notes live there and nowhere else.

## What this repo is

A personal macOS development stack, published so that anyone can read it, lift a piece from it, or
install it whole: the installer, the tool list, and the configuration for each tool, with the
reasoning written down next to every choice that was not obvious.

**Current state:** the installer, the git defaults, the Ghostty configuration, the Yazi
configuration and the hunk configuration are in; the shell configuration and the runtime versions
follow. The delivery model below is not aspirational — it is in daily use, and it is binding for
every file that lands here.

**macOS only.** It is the only platform anything here is developed or tested on. Do not add Linux
or WSL branches to make something "portable"; untested portability is worse than a documented
limit.

### Scope — what belongs here

This repo holds configuration and never holds identity. Anything that names a person, a machine, or
an account stays in untracked files on the machine that needs it, and the docs say where. The
boundary:

| Belongs here | Stays on your machine, untracked |
|---|---|
| Configuration any developer could adopt as-is | Anything naming a person, employer, client, or host |
| Tool setup, aliases, keybindings, themes | `[user]` identity, signing keys, tokens |
| The reasoning behind a choice — including rejected ones | Per-directory routing keyed on paths that exist on one machine |

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
| `~/.config/git/config` — never `~/.gitconfig` | `[include] path = <repo>/git/.gitconfig`; see ADR 0002 |
| `~/.config/ghostty/config.ghostty` | `config-file = <repo>/ghostty/config.ghostty`; see ADR 0009 |
| `~/.zshenv` | `export YAZI_CONFIG_HOME=<repo>/yazi` — the variable names the directory; see ADR 0010 |
| `~/.config/hunk/config.toml` | byte copy — hunk has no include directive and no config variable; see ADR 0011 |

Planned, not yet delivered — listed so the mechanism is decided before the port lands:

| Destination | Redirect mechanism |
|---|---|
| `~/.zshrc` | `source <repo>/zsh/.zshrc` |
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
2. If the tool has no include directive but reads its config directory from an environment
   variable, export that variable from the named block in `~/.zshenv` — and accept that the tool
   then has no machine-local override layer. See
   [ADR 0010](docs/decisions/0010-export-a-config-directory-variable-from-zshenv.md).
3. If the tool has neither, copy the file — and make the installer *report* drift rather than
   pretend to prevent it.
4. If the tool can be reached through `$PATH`, install no file at all.

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

**This repo never assumes it is the sole manager of a destination file.** A destination may already
hold hand-written settings, lines a vendor installer appended, or a block another tool maintains.
Where a destination genuinely must be shared, the installer owns a **named, delimited block** — its
own BEGIN/END markers — and preserves every byte outside it. It may not own "everything above a
sentinel", and it may not rewrite a destination wholesale.

> The known trap: a single-sentinel scheme that regenerates everything above the line and preserves
> only what is below cannot compose. Two managers that both do this each silently erase the other's
> block. Whichever ran last appears to work, which is what makes it expensive to diagnose.

**For git, the sharing problem is avoided rather than solved.** This repo owns
`~/.config/git/config` and never writes `~/.gitconfig`, so your own settings and this repo's live in
two different files and no block negotiation is needed — see
[ADR 0002](docs/decisions/0002-include-git-config-from-xdg-never-gitconfig.md). Prefer a separate
destination over a shared file wherever a tool's include order allows it; reach for the named block
only when it does not.

**git and Ghostty have opposite include precedence.** This is the single most surprising thing here:

| | Who wins | Machine-local overrides go |
|---|---|---|
| **git** | **`~/.gitconfig`** — git reads `~/.config/git/config` first, and the later value wins | `~/.gitconfig`, which this repo never writes |
| **Ghostty** | the **repo** — `config-file` is processed at the *end* of the containing file | `~/.config/ghostty/local.ghostty` |
| **Yazi** | the **repo** — it is the only directory Yazi reads | none; a different `YAZI_CONFIG_HOME` exported below the block in `~/.zshenv` |
| **hunk** | the **repo** — the installer owns the destination outright | none machine-wide; a per-project `.hunk/config.toml` overrides it for one repository |
| **zsh** *(planned)* | **local** — later lines win | a local file sourced last; the file name is decided with the port |

Practical consequence: `git config --global …` writes into `~/.gitconfig`, not into this repo, and
wins over it. That is intentional — `~/.gitconfig` is the machine-local override layer — but it
means such edits never show up in `git status` here.

---

## Public-repo hygiene

This repo is public. Anything brought in from a personal configuration is sanitised first; nothing
is copied in verbatim.

Never commit, in any tracked file:

- Real email addresses, GPG or SSH key IDs and fingerprints, tokens, API keys
- Employer names, client names, or work-specific directory paths
- Hostnames, machine names, or home-directory paths

Personal configuration is not shipped at all. Each kind has a documented place on your machine:

| Kind | This repo holds | Real values live in |
|---|---|---|
| Git identity | **nothing — no `[user]` section, ever** | `~/.gitconfig` — untracked, and never written by this repo |
| Secrets, tokens | nothing | a file of your own that your shell sources — untracked, `chmod 600` |
| Machine-specific terminal settings | nothing | `~/.config/ghostty/local.ghostty` |

The git identity row is stronger than the others and deliberately so: **not a placeholder, not a
template, nothing at all.** A `[user]` section holding a dummy address is still an address-shaped
string in a public repo, it is one careless edit away from being a real one, and it defeats the
check below — which cannot tell a placeholder from the real thing, and should not have to. Git
already looks in `~/.gitconfig` for identity; leave it there and ship none.

This rule is load-bearing for the check in *Verifying a change*: it is what lets that grep demand
**zero** matches rather than maintaining an allowlist of "safe" example domains. Write the rule
down in prose without ever writing a specimen address — including in this file.

**Bringing a file in from a personal configuration is a sanitising operation, not a copy.** Read
it, strip the personal values, replace them with placeholders, and grep the result before staging
it.

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
  entry, not by rewriting the old one. Entries still under `[Unreleased]` may be folded together or
  corrected freely: nobody has shipped them yet.

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
  `setup`, `zsh`, `git`, `ghostty`, `yazi`, `hunk`, `scripts`, `brew`, `asdf`, `docs`, `claude`.
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
work; the commit itself is a human decision.

---

## Verifying a change

Every change passes these before it is staged. None of them needs anything beyond git and macOS's
system bash.

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

Every change to shell code must also pass:

```bash
bash -n install.sh setup.sh   # syntax check; no dependencies
./install.sh --dry-run        # show exactly what would change; touch nothing
./install.sh --check          # report drift; exit non-zero if anything is off
```

`shellcheck` is welcome but not required, and it does not replace `--dry-run` and `--check`.

---

## Documentation conventions

- `README.md` is the entry point: what this is, what you get, how it installs, and the no-symlink
  promise. It links onward; it does not repeat the deep dives.
- `docs/` holds deep dives for the pieces whose *rationale* is non-obvious — the reasoning that
  would otherwise be lost, including rejected alternatives and upstream bugs worked around.
  `docs/herdr-notifications.md` sets the expected depth and tone.
- `docs/decisions/` holds **ADRs** in Michael Nygard's five-section format: Title, Status, Context,
  Decision, Consequences — plus the *Alternatives Considered* section every record here carries.
  One decision per file, `NNNN-kebab-title.md`, numbered append-only. An ADR records *why* a choice
  was made, what was rejected, and what it costs — and is **written once and not edited
  afterwards.** A reversal is a new ADR that supersedes the old one; the old record stays as
  history. Use the `writing-adrs` skill rather than hand-rolling the format.
- [`docs/decisions/README.md`](docs/decisions/README.md) is the **index**: one row per record with
  the decision in a sentence. Read it before adding a record — a new decision is often a supersede
  rather than a fresh number — and add a row whenever a record is added or superseded. The README
  links the index, the index links the records, and nothing else enumerates them.
- **An ADR and a deep dive are not the same document, and neither repeats the other.** The ADR
  argues the decision and then stops; the `docs/` page explains how the thing behaves *now* —
  mechanism, traps, current versions — and is updated freely as tools change. Each links to the
  other. When a deep dive already carries the reasoning, the ADR states the decision and the
  trade-off accepted and points at the page for detail.
- **Implementation specs are not tracked.** `spec/` is git-ignored, because a spec describes a plan
  at one moment rather than the system, and it rots as soon as the code moves. What outlives the
  change is distilled into an ADR. A tracked `.ignore` file un-ignores `spec/` for search tools, so
  coding agents can still read it — git and ripgrep disagree here deliberately.
- `docs/manual-setup.md` is the only **how-to** here, not a deep dive. It holds every command a
  reader runs by hand, in order, with a verify and an undo for each. It carries no rationale beyond
  a one-line pointer into the `docs/` page that explains the choice.
- **A command that writes to `$HOME` appears exactly once in the repository.** Procedures live in
  `docs/manual-setup.md`; the reasoning behind them lives in `docs/`. A deep dive may name a
  setting in prose, but a second copy-pasteable block is a defect — two copies of a command that
  edits a live machine will drift, and nothing here can check them against each other.
- Document the trap, not the API. If a behaviour surprised you, that is the paragraph worth writing.
- **Wrap prose at 100 columns.** Tables, code blocks, long URLs and link destinations are exempt —
  never break those to fit. Consistent width keeps `git diff` readable when a paragraph is edited
  years later.
