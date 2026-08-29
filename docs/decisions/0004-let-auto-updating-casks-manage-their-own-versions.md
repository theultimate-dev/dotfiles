# 0004. Let auto-updating casks manage their own versions

## Status

Accepted

## Context

Five casks in the `Brewfile` — `ghostty`, `zed`, `t3-code`, `copilot-cli` and `antigravity-cli` —
declare `auto_updates true`. Homebrew skips those permanently: `brew upgrade --cask` and
`brew outdated` pass over them, and each app updates itself through Sparkle or its own routine.

The resulting drift is observable on a healthy machine. Copilot CLI's Caskroom entry records
`0.0.396` while the binary reports `1.0.80`; Zed's records `0.121.7` while `Zed.app` reports
`1.16.2`. Homebrew offers `--greedy`, `HOMEBREW_UPGRADE_GREEDY` and `HOMEBREW_UPGRADE_GREEDY_CASKS`
to force these upgrades anyway.

## Decision

We let auto-updating casks manage their own versions and never pass `--greedy` or set the
`HOMEBREW_UPGRADE_GREEDY*` variables.

## Consequences

- Homebrew is the installer-of-record for these five, not their version manager.
- Recorded Caskroom versions are unreliable. Any future drift check must not read them as truth.
- Naming a cask explicitly bypasses Homebrew's downgrade protection, so a forced upgrade can
  overwrite a newer self-updated app with older cask metadata. Avoiding `--greedy` avoids that.
- Updates arrive on each vendor's schedule rather than on `brew upgrade`, security fixes included.
- `setup.sh` is convergent, not inert: a re-run still upgrades formulae and non-`auto_updates`
  casks.
- Homebrew-generated shell completions are produced once at install time and go stale as the tool
  updates itself.

Detail and current observed versions live in [the agent tooling guide](../agent-tooling.md).

## Alternatives Considered

- Pin versions by disabling each tool's in-app updater and upgrading greedily — fights the tools,
  delays security updates, and re-arms the downgrade path above.
