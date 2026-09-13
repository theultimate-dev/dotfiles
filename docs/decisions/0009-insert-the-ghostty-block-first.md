# 0009. Insert the Ghostty block first in the destination file

## Status

Accepted

## Context

Ghostty reads `~/.config/ghostty/config.ghostty` and its sibling files first, then every
`config-file` include in the order encountered, and the later file wins. A path included twice is
skipped with a "cycle detected" diagnostic. `install.sh` writes a named block
([0006](0006-manage-shared-destinations-with-delimited-blocks.md)) holding two includes: the repo
config, then the optional `local.ghostty`. Appending that block after another manager's
`config-file` lines would make this repo override that manager and its override file, while the
README promises a defaults layer. Git's escape, a separate file read earlier
([0002](0002-include-git-config-from-xdg-never-gitconfig.md)), does not exist here: both XDG files
load before any include.

## Decision

We insert the Ghostty block at the top of an existing `config.ghostty` and update it in place
afterwards.

## Consequences

- Another manager's later includes keep beating this repo; `local.ghostty`, included last in the
  block, beats both.
- Keys typed directly into `config.ghostty` lose to every include; the destination file cannot hold
  overrides.
- `--check` ignores block position: converging it would ping-pong with a second manager applying
  the same rule.
- A second manager that also includes `local.ghostty` triggers the cycle diagnostic; only one may
  include it.
- Ghostty older than 1.2.3 never reads `config.ghostty` and ignores the stub silently.
- Git keeps appending its block; the two destinations follow opposite rules on purpose.

## Alternatives Considered

- A separate destination, `~/.config/ghostty/config` — loads before any include as well, so it
  isolates nothing.
- Regenerating the file wholesale — cannot compose with a second manager, or with a line the user
  typed.
- Appending like git — puts this repo's include after everyone else's, so it overrides instead of
  defaulting.
