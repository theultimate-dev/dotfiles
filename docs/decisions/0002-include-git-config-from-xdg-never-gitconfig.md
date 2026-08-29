# 0002. Include git config from `~/.config/git/config`, never `~/.gitconfig`

## Status

Accepted

## Context

This public repository is installed alongside a second, private dotfiles repository on the same
machine, and both supply git configuration. `AGENTS.md` originally anticipated a shared
`~/.gitconfig` owned through named BEGIN/END sentinel blocks. That scheme does not compose: two
installers each regenerating their own region of one file silently erase each other's block, and
whichever ran last appears to work — which is what makes it expensive to diagnose.

`~/.gitconfig` is also where essentially every user keeps identity, aliases, and years of
accumulated settings. git reads `~/.config/git/config` *before* `~/.gitconfig`, and the later value
wins.

## Decision

We own `~/.config/git/config` and never write `~/.gitconfig`.

## Consequences

- Everything in the user's own `~/.gitconfig` overrides everything this repository ships, by
  construction rather than by line ordering.
- The private repository keeps `~/.gitconfig`; neither installer reads or writes the other's
  destination. No sentinel to agree on, no install-order dependency.
- `git config --global …` keeps writing to `~/.gitconfig`, so those edits never appear in
  `git status` here. That is intended: it is the machine-local override layer.
- The installer must create an empty `~/.gitconfig` when none exists. Without it, git's `--global`
  write target becomes the XDG file, and the next `git config --global` would put the user's
  identity inside a file this repository manages.
- This repository is a defaults layer only. It cannot force a setting.
- Supersedes the single-file sentinel-block scheme described in `AGENTS.md`, which that document
  still describes for other destinations.

## Alternatives Considered

- Shared `~/.gitconfig` with BEGIN/END markers — two installers silently erase each other's block.
- Symlinking `~/.gitconfig` into the repository — there is only one such file, so whichever repo
  installs second wins all of it.
