# 0013. Apply the Herdr config by hand

## Status

Accepted

## Context

Herdr is the multiplexer the coding agents run in, used here on more than one Mac, and its
configuration — notification delivery, key bindings, and the settings of the herdr-radar sidebar
plugin — is worth carrying from one to the next.
[0005](0005-install-agent-tooling-without-managing-its-config.md) kept agent tooling's
configuration out of the repository and said that revisiting a tool takes a new record; this is
that record for Herdr.

Herdr reads `~/.config/herdr/config.toml`. It has no include directive, so the stub of
[0001](0001-deliver-configs-as-include-stubs-not-symlinks.md) has nothing to hook into. It does
honour `HERDR_CONFIG_PATH`, which [0010](0010-export-a-config-directory-variable-from-zshenv.md)
could export, but herdr-radar ignores that variable: it keeps writing its blocks into
`~/.config/herdr/config.toml`, a file Herdr would then no longer read, and the sidebar stays as
broken as it is with no config at all.

The destination also has two writers besides this repository. Herdr writes it from its first-run
flow and its settings panel, and `herdr config reset-keys` removes tables from it. herdr-radar keeps
three marker-fenced blocks in it, one inserted directly below the `[ui]` header line and two
appended at the end, and rewrites `name` and `auto_switch` under `[theme]` whenever the desktop
turns light or dark. A byte copy under [0011](0011-copy-the-hunk-config-and-report-drift.md)
erases all of that on every run. A delimited block under
[0006](0006-manage-shared-destinations-with-delimited-blocks.md) cannot hold `[ui]` without the
plugin writing inside it, and TOML forbids defining the table a second time outside it.

## Decision

We keep Herdr's configuration, its plugin pins and the plugins' settings in `herdr/`, and apply
them by hand or through a coding agent following step 3 of `docs/manual-setup.md`; no script in
this repository writes them. `setup.sh` installs the pinned plugins with `herdr plugin install`, as
it already installs Herdr's agent integrations with Herdr's own CLI.

## Consequences

- A new Mac takes one guarded copy per file. A Mac with a Herdr config of its own takes a merge,
  which step 3 spells out and an agent can follow.
- The repository is not the live source of truth here, nor a copy that converges: an edit to
  `herdr/` reaches a machine only when someone merges it there.
- Nothing reports drift. Step 3's `diff`, which leaves out herdr-radar's blocks and its two
  `[theme]` keys, is the manual equivalent.
- Nothing here can overwrite a setting Herdr's panel saved or a block herdr-radar wrote, and hunk
  stays the only file `install.sh` copies.
- The tracked file is never refreshed from a machine: herdr-radar's tab-bar block embeds an
  absolute path into the home directory.
- herdr-radar writes its blocks only on its first start, and skips them for good if `[ui]` is
  missing then. Step 3 runs its `configure` action once to cover a plugin installed before the
  config.
- Plugin versions are pinned in `herdr/plugins.txt` and bumped by Renovate, because Dependabot
  cannot read a pin in a plain file.
- [0005](0005-install-agent-tooling-without-managing-its-config.md) still holds for every other
  agent tool.

## Alternatives Considered

- An include stub under [0001](0001-deliver-configs-as-include-stubs-not-symlinks.md) — Herdr has
  no include directive.
- Exporting `HERDR_CONFIG_PATH` under
  [0010](0010-export-a-config-directory-variable-from-zshenv.md) — herdr-radar ignores it and
  writes to a file Herdr would no longer read.
- A byte copy under [0011](0011-copy-the-hunk-config-and-report-drift.md) — erases herdr-radar's
  blocks and whatever Herdr's settings panel saved, on every run.
- A delimited block under [0006](0006-manage-shared-destinations-with-delimited-blocks.md) —
  herdr-radar inserts its tab-bar block directly below `[ui]`, inside the managed block, and TOML
  forbids a second `[ui]` outside it.
- `install.sh` creating the files where they are absent and reporting drift elsewhere — it puts an
  installer into a file two other programs write, where a mistake overrides someone's
  configuration, and a drift check there would have to track herdr-radar's block layout to mean
  anything.
- Leaving Herdr unmanaged under [0005](0005-install-agent-tooling-without-managing-its-config.md)
  — the configuration would not follow from one Mac to the next.
