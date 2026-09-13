# 0003. Install daily tools through Homebrew

## Status

Accepted

## Context

Nine daily tools need installing on macOS: Ghostty, Zed, T3 Code, Herdr, `terminal-notifier`, and
the Codex, Copilot, Antigravity and Grok Build agent CLIs. Seven document Homebrew as a supported
channel. Two — `antigravity-cli` and `grok-build` — document only a vendor curl installer.

Those installers assume ownership of the machine. They append export blocks to `~/.zshrc`,
outside any block an installer could verify, and leave `~/.zshrc.bak.<epoch>` behind. They
`ln -sf` binaries into `~/.local/bin`, breaching
[0001](0001-deliver-configs-as-include-stubs-not-symlinks.md) by proxy.
OpenAI's prompts interactively to `brew uninstall` an existing cask. Google's exits 0 without
upgrading when `~/.local/bin/agy` already exists. Zed's is documented for Linux only and, on macOS,
runs `rm -rf /Applications/Zed.app` before repopulating it.

## Decision

We install every daily tool from the `Brewfile`, including the two casks their vendors do not
endorse.

## Consequences

- One entry point, `brew bundle install`. The only `curl | bash` in `setup.sh` is Homebrew's own
  bootstrap, run once when `brew` is absent; no vendor script is ever piped to a shell.
- No vendor installer mutates `~/.zshrc` or creates symlinks in `$HOME`.
- `brew bundle` passes `--adopt` for casks, so it absorbs apps already installed by direct download
  instead of failing with `CaskError`.
- Two casks are community-packaged. They fetch the vendors' own signed artifacts, pinned by SHA-256
  in `homebrew-cask`, so provenance holds but the packaging is unendorsed.
- Those two lag the vendor channel whenever `homebrew-cask` metadata is slow to follow a release.
- Installation does not finish setup: every agent CLI still needs an interactive login.

Mechanics and traps live in [the agent tooling guide](../agent-tooling.md).

## Alternatives Considered

- Vendor curl installers — rewrite `~/.zshrc` and symlink into `$HOME`.
- npm global installs — asdf-managed Node scopes the global prefix per runtime version, so the
  binaries vanish on the next runtime bump.
