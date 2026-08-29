# 0005. Install agent tooling without managing its config

## Status

Accepted

## Context

`setup.sh` installs editors and coding-agent CLIs, which raises the question of whether their
configuration should also become managed configuration under
[0001](0001-deliver-configs-as-include-stubs-not-symlinks.md).

None of them supports an include directive, so a byte copy is the only mechanism available. Two of
them rewrite their own settings during ordinary use: Zed's settings editor is its primary
configuration surface and saves automatically, and T3 Code writes its built-in defaults into
`keybindings.json` on first run and adds new ones on later startups. A byte copy of a file the tool
edits itself reports drift constantly and means nothing.

`~/.claude/settings.json` is worse. `herdr integration install claude` merges a `SessionStart` hook
into it, and the entry embeds an absolute `$HOME` path — which no tracked file here may contain. The
named-block convention used for other destinations cannot be reused, because JSON has no comment
syntax to carry the markers.

## Decision

We install agent tooling and editors without managing any of their configuration files.

## Consequences

- `setup.sh` installs; the settings stay the user's own, and the repository never fights a tool that
  edits its own config.
- Editor and agent preferences are not portable to a new machine through this repository.
- The Herdr agent integrations stay the only thing written on the agents' behalf, and they are
  written by Herdr's own CLI rather than by this repository.
- Nothing here writes machine-absolute paths into a tracked file.
- `AGENTS.md` already permits a tool to be installed and documented without a managed config, so
  this needs no exception.
- Revisiting a specific tool later means a new ADR, not a quiet change of practice.

## Alternatives Considered

- Byte-copy `settings.json` for Zed and T3 Code — both rewrite it themselves, so drift would be
  permanent noise.
- A named block inside `~/.claude/settings.json` — JSON has no comment syntax to delimit one.
