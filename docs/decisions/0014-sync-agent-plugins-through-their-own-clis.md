# 0014. Sync agent plugins through their own CLIs and copy skills only for agy

## Status

Accepted

## Context

Coding work goes to Claude Code, Codex and Antigravity (agy), and each should have the same
skills. Claude Code and Codex both install plugins from the same Claude-format marketplace
catalogs, each through its own CLI. agy has no command to add a third-party marketplace, so its
skills have to arrive as folders in its personal skills directory. Keeping the three in step by
hand had already drifted: flat copies of plugin skills, made by a skills CLI into the directory
Codex reads, shadowed the plugins and had fallen behind them.

[0005](0005-install-agent-tooling-without-managing-its-config.md) keeps every agent tool's
configuration files out of this repository, and says that revisiting a tool takes a new record.
It also names the Herdr integrations as the only thing written on the agents' behalf, by Herdr's
own CLI. [0013](0013-apply-the-herdr-config-by-hand.md) revisited it for Herdr.

Which marketplaces and plugins a person uses, and where their local checkouts are, is personal and
names paths on one machine, so the list cannot be tracked here.

## Decision

We ship `scripts/agent-sync`, a standard-library Python command run by hand, that installs and
updates the plugins a per-machine manifest lists, through `claude plugin` and `codex plugin`
alone, and copies the skills the manifest selects for agy into agy's personal skills directory,
owning only the folders it records there.

## Consequences

- No harness settings file is written by this repository; the harnesses' own CLIs record
  marketplaces and plugins, as Herdr's CLI records its hooks. 0005 still holds for every settings
  file.
- Codex's `config.toml` is read for a marketplace's ref, which no Codex command reports, and never
  written.
- The Herdr integrations are no longer the only thing written on the agents' behalf.
- The manifest lives untracked in `~/.config/agent-sync/`; the repository ships a generic example
  only, and the selection does not follow from one Mac to the next by itself.
- A marketplace either enrols the plugins listed for it or, with `plugins = "all"`, every plugin
  its catalog declares — meant for a catalog you own.
- The caller's environment reaches every harness command unchanged, except one variable on
  Claude's two list calls that keeps them from writing telemetry or connecting out.
- agy's skills are copies: an edit reaches agy on the next run, not live. A source containing a
  symbolic link is refused, so no copy creates one in `$HOME`.
- A folder in agy's skills directory that agent-sync did not create is never replaced without
  `--adopt`, which archives it first; nothing is deleted.
- Claude Code and Codex receive no flat skill copies from this repository, so a plugin skill
  appears once in each. Duplicates already present are reported, not removed, outside a separate
  confirmed cleanup.
- Neither `install.sh` nor `setup.sh` calls it: it needs Python 3.11, git, the network and signed-in
  harnesses, and it can stop for a person's confirmation.
- Codex has no plugin update verb and skips an unmoved ref, so a stale Codex cache is reported, and
  reinstalled in place only when a person passes `--repair`.
- Codex's refresh works per marketplace, so it also refreshes the plugins of a managed marketplace
  that the manifest leaves unmanaged.
- A plugin a catalog declares a command for is held until a person accepts that command's hash;
  the script never passes `-y`.

## Alternatives Considered

- A skills CLI targeting every agent — its default links skills into place, it writes the flat
  roots that shadow plugins, and its global updater skips local sources.
- Flat copies into every harness — a second invocation path for each plugin skill in Claude Code
  and Codex, the drift this replaces.
- Pointing agy's `skills.json` at local checkouts — writes a settings file agy may own, cannot
  select single skills from a catalog, and remote catalogs would need checkouts anyway.
- `agy plugin install` or `agy plugin import` — imports hooks and server declarations written for
  another harness, and reinstall semantics are unverified.
- A tracked manifest — names accounts and machine paths.
- Running it from `install.sh` — breaks the offline, bash 3.2 contract.
- A shell script — TOML, JSON, tree digests and staged swaps exceed what bash 3.2 does safely.
- A compiled binary or a separate repository — packaging cost for a command one machine runs.

The mechanism, the traps and the contract-test evidence are in [agent-sync](../agent-sync.md).
