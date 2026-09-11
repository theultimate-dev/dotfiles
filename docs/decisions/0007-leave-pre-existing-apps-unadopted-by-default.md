# 0007. Leave pre-existing apps unadopted by default

## Status

Accepted

## Context

`brew bundle` passes `--adopt` to every cask install, and
[0003](0003-install-daily-tools-through-homebrew.md) relied on that to absorb apps installed by
direct download. Adoption is not inert. A cask with an artifact inside the bundle — Zed's `binary`
stanza — modifies the bundle, and since macOS 13 that requires the App Management permission for
the terminal running Homebrew. The attempt that triggers the permission dialog is refused whatever
the answer. Homebrew treats the refusal as an install failure and rolls back: it copies the app into
the Caskroom, removes it from `/Applications`, then purges that Caskroom version, backup included.
When the bundle belongs to another user, Homebrew also escalates to `sudo`. A first run on a second
machine did exactly this to a hand-installed Zed.

The repository's invariants forbid silent clobbering and make ambiguity an error, never a guess.

## Decision

`setup.sh` skips every app already in `/Applications` that Homebrew did not install, and adopts
one only when run with `--adopt` after probing the App Management permission.

## Consequences

- The default run shows no permission dialog, asks for no password, and cannot delete an app.
- A skipped app stays off Homebrew's books: `brew bundle check` reports it missing, its `binary`
  link is absent.
- `--adopt` runs Homebrew's own write test before `brew bundle`, so a refusal stops before rollback.
- A bundle owned by another user stops `--adopt`; `sudo` does not bypass the permission.
- Detection relies on a token-to-bundle list in `setup.sh` that must track the `Brewfile`.
- The `--adopt` consequence in 0003 no longer describes the default; 0003 otherwise stands.

Mechanics and the failure transcript live in
[the agent tooling guide](../agent-tooling.md#apps-you-installed-before-homebrew-did).

## Alternatives Considered

- Keep automatic adoption and document the dialog — a refused dialog still deletes the app.
- Probe the permission and adopt automatically when granted — every newcomer with a pre-installed
  app still meets the dialog on first run, for a change they did not ask for.
- Install the cask without `--adopt` beside the existing app — Homebrew refuses with `CaskError`.
