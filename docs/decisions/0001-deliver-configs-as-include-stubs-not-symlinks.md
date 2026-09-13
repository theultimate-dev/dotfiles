# 0001. Deliver configs as include stubs, not symlinks

## Status

Accepted

## Context

Dotfiles have to reach `$HOME` somehow. The obvious mechanism is a symlink farm: one `ln -sf` per
destination. `ln -sf` overwrites a pre-existing real file with no warning and no backup, so a
hand-written `~/.zshrc` is destroyed the first time such an installer runs on a machine that already
has one. A symlink farm also hardcodes the
repository location: cloned anywhere other than the expected path it produces dangling links, no
error, and a shell that quietly loses half its configuration. Some backup and sync agents mishandle
symlinked dotfiles. The repository must stay clone-anywhere, and `git diff` must audit the whole
configuration.

## Decision

We install a small real file at each destination that redirects into the repository using the target
tool's own native include directive.

## Consequences

- The repository stays the live source of truth; an edit takes effect with no reinstall.
- Clone location is free — the installer resolves its own path and generates absolute paths into
  the stubs.
- No tracked file may contain a machine-specific absolute path. This becomes an invariant.
- Include semantics differ per tool and must be learned per destination.
- git and Ghostty have opposite precedence: the git stub beats the repository, Ghostty's repository
  beats the stub. See [the delivery model in the README](../../README.md#how-configs-are-delivered).
- A tool with no include mechanism needs a byte copy, where drift is reported rather than prevented.

## Alternatives Considered

- Symlink farm via `ln -sf` — clobbers real files silently and hardcodes the repository path.
- Copying configs into `$HOME` at install time — the repository stops being live; every edit needs
  a reinstall, and local edits are lost on the next run.
