# 0011. Copy the hunk config and report drift

## Status

Accepted

## Context

`hunk diff --watch` redraws the working tree as an agent writes it, which is the review pane this
stack wants beside a running agent. hunk reads `~/.config/hunk/config.toml`, overridden per project
by `.hunk/config.toml` at a repository root. It offers no include directive, no config-path flag
and no config-directory variable, so neither the stub of
[0001](0001-deliver-configs-as-include-stubs-not-symlinks.md) nor the export of
[0010](0010-export-a-config-directory-variable-from-zshenv.md) applies. TOML forbids a repeated
key, so a named block under [0006](0006-manage-shared-destinations-with-delimited-blocks.md) cannot
share the destination: a `theme` inside the block and a `theme` a user typed outside it fails with
`TOML Parse error: Cannot redefine key 'theme'`, a hard error rather than an override. hunk also
offers, on quit, to persist changed view preferences into that same file.

## Decision

We copy `hunk/config.toml` to `~/.config/hunk/config.toml` and report the drift between them.

## Consequences

- The repository is not the live source of truth here; an edit lands on the next `./install.sh`.
- `./install.sh --check` reports that gap and cannot prevent it.
- `install.sh` gains `apply_copy` beside `apply_block`, and its first byte-copy destination.
- Anything already at the destination is backed up before the first overwrite.
- The shipped config sets `prompt_save_view_preferences = false`; without it hunk rewrites a file
  the installer owns, and `--check` reports drift nobody caused.
- There is no machine-local override layer, only a per-project `.hunk/config.toml`.
- A second manager of this destination would lose silently; none shares it today.
- The byte-copy fallback named in [0001] now has a worked case, ahead of `~/.tool-versions`.

## Alternatives Considered

- A delimited block under [0006] — a repeated key is a TOML parse error, not an override.
- An include stub under [0001] — hunk has no include directive to write.
- A config-directory export under [0010] — hunk reads no such variable.
- Shipping no config at all — loses the narrow-pane layout and the save-prompt guard.
- A per-project `.hunk/config.toml` in each repository — multiplies the file instead of placing it once.
