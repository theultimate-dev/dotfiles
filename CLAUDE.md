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
  trap. Records go in `docs/decisions/` as `NNNN-kebab-title.md`, numbered append-only. Read
  [`docs/decisions/README.md`](docs/decisions/README.md) first — the existing records already cover
  the delivery model, every destination mechanism in use, and the precedence traps, so a new
  decision is often a *supersede* rather than a fresh number. Add a row to the index with the
  record.

## Working style here

- **Plan before touching the install model.** Anything that changes what lands in `$HOME`, how a
  stub is generated, or precedence between the repo and a stub gets planned and approved first.
  These failures are silent, and they land on a machine the user depends on daily.
- **Verify against the tool, not against memory.** When a doc claims how a tool loads its config —
  which files, in which order, who wins — check it against the tool's own documentation or a test
  run in a scratch `$HOME` before relying on it. The traps recorded here were found that way, and
  reconstructing behaviour from the config alone loses them.
- **Never `git commit`** unless the current request asks for one. This restates the rule in
  `AGENTS.md` so that it binds Claude Code specifically, whatever a harness default says.
