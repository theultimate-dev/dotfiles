# 0006. Manage shared destinations with named delimited blocks

## Status

Accepted

## Context

Configuration delivery requires injecting stubs into user configuration files in `$HOME` (such as
`~/.config/git/config`). This repository is installed on machines with existing hand-written
configuration, and often with another tool already maintaining lines in the same files.

Overwriting destination files wholesale clobbers user settings. Symlinks destroy pre-existing files
and prevent multiple managers from contributing settings to the same tool. Single-sentinel schemes
(such as regenerating everything above a line) fail to compose: two installers that each rewrite
one partition silently delete each other's configuration.

The installer needs a safe, repeatable method to inject and maintain its stubs in shared files
without disturbing pre-existing contents, while supporting dry-run inspection, drift detection,
and atomic file operations.

## Decision

The installer owns a named, delimited block (`# BEGIN dotfiles (public)` ...
`# END dotfiles (public)`) inside shared destination files, and preserves every byte outside that
block.

The installer contract enforces:

1. **Delimited ownership:** Only lines between `# BEGIN dotfiles (public)` and
   `# END dotfiles (public)` are managed. Content outside the markers is preserved byte-for-byte.
2. **Atomic writes:** Target files are never modified in-place. The new content is rendered to a
   temporary file in the target directory (`<target>.tmp.<pid>`) and atomically renamed via `mv`.
3. **Pre-modification backups:** Before the installer modifies an existing file for the first time,
   it copies the file into `~/.dotfiles-backup/` and records the copy, with a timestamp, in a
   manifest.
4. **Inspectability without mutation:** `--dry-run` displays planned changes without writing to
   disk; `--check` verifies drift against expected stubs and exits non-zero if anything differs.
5. **No symlinks and no network:** The installer refuses symlinked destinations and operates
   strictly offline, depending only on macOS system bash 3.2 and coreutils.

## Consequences

- Re-running `./install.sh` on an up-to-date system is a true no-op.
- Multiple managers can coexist in the same file provided each uses distinct delimited markers.
- Updates to include paths (for instance, when a repository clone is relocated) update the block in
  place without touching surrounding user configuration.
- Applicable only to formats that support comment syntax. File formats without comments (such as
  JSON) cannot carry delimited markers and remain unmanaged per
  [0005](0005-install-agent-tooling-without-managing-its-config.md).

## Alternatives Considered

- Single sentinel line ("everything above this line is managed") — two managers each owning
  everything above a separator erase each other's block on alternating runs.
- Wholesale file generation — destroys all pre-existing user settings.
- Symlinks via `ln -sf` — clobbers real files silently, breaks multiple-repo composition, and
  hardcodes clone paths into `$HOME`.
