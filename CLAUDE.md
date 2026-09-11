# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository.

@AGENTS.md

The file imported above is the working agreement: the no-symlink delivery model, the repository
invariants, public-repo hygiene, and the changelog and commit conventions. Everything below is
Claude-specific and is deliberately stated nowhere else.

## Skills to use

- **`semver-changelog`** for any `CHANGELOG.md` work — creating it, backfilling, adding an entry
  under `[Unreleased]`, or deciding a MAJOR/MINOR/PATCH bump. Do not hand-roll the format.
- **`writing-conventional-commits`** when preparing a commit message. It already encodes the
  past-tense descriptions and scope selection this repo uses.
- **`writing-adrs`** when a decision about the delivery model will outlive the change that
  introduces it: a rejected alternative worth recording, a new destination mechanism, a precedence
  trap. Records go in `docs/decisions/` as `NNNN-kebab-title.md`, numbered append-only. Read the
  existing ones first — `0001`–`0010` already cover the no-symlink model, the git destination, the
  Homebrew channel, auto-updating casks, why agent config is unmanaged, delimited blocks, app
  adoption, the notification channel, Ghostty's block position, and the environment-variable
  redirect, so a new decision is often a *supersede* rather than a fresh number.

## Working style here

- **Plan before touching the install model.** Anything that changes what lands in `$HOME`, how a
  stub is generated, or precedence between the repo and a stub gets planned and approved first.
  These failures are silent, and they land on a machine the user depends on daily.
- **Verify against the private original rather than inferring.** When porting from `~/dotfiles`,
  read the source file *and* its `docs/` rationale. The reasons behind these rules are written
  down; reconstructing them from the code alone loses the traps — and the port must be sanitized,
  never a straight copy.
- **Never `git commit`** unless Igor asks in the current request. This restates the global rule so
  that it binds at project level too.

## Repository-local files

- `.claude/settings.local.json` is per-machine permission state and stays untracked.
