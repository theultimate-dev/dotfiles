# Agent tooling and installation on macOS

How developer tools, terminal emulators, and coding agent CLIs are installed and wired together
under this dotfiles repository.

This covers the rationale behind package management choices in `Brewfile`, the mechanics of
`setup.sh`, and the integration layer with [Herdr](https://herdr.dev).

## The delivery model: Homebrew as the single installer

Every daily tool in this repository is delivered via Homebrew:

- **Terminal emulator & GUI editors:** [Ghostty](https://ghostty.org), [Zed](https://zed.dev),
  and [T3 Code](https://t3.codes).
- **Terminal multiplexer & notifier:** [Herdr](https://herdr.dev) and
  [`terminal-notifier`](https://github.com/julienXX/terminal-notifier).
- **Coding agent CLIs:** [OpenAI Codex](https://github.com/openai/codex),
  [GitHub Copilot CLI](https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli),
  [Google Antigravity CLI](https://antigravity.google/product/antigravity-cli), and
  [xAI Grok Build](https://x.ai/build).

This covers tool *installation* only. Configuration placement belongs to `install.sh` and is kept
strictly separated per `AGENTS.md`. Shell add-ons (Oh My Zsh, plugins) and versioned runtimes
(asdf, pnpm) will arrive alongside their respective config ports.

### Two intentional deviations from vendor install channels

Six of the eight tools explicitly document Homebrew as a supported or primary installation
channel. Two do not:

1. **`antigravity-cli` (Google Antigravity CLI):** Vendor documentation promotes an interactive
   curl-to-sh script.
2. **`grok-build` (xAI Grok Build):** Vendor documentation provides a curl download command for a
   tarball or standalone binary.

We deliberately install both via their Homebrew casks (`cask "antigravity-cli"` and
`cask "grok-build"`). The casks download the vendors' own signed artifacts directly from official
vendor releases, pinned by cryptographic SHA-256 digests in `homebrew-cask`.

### Why vendor curl installers were rejected

Vendors increasingly distribute interactive curl scripts that assume ownership of the user's
machine. In a principled dotfiles environment, those scripts introduce severe failure modes:

- **Rewriting `~/.zshrc`:** Vendor installers append export blocks and shell hooks directly to
  `~/.zshrc`, dropping timestamped artefacts like `~/.zshrc.bak.<epoch>`. In this repository,
  `~/.zshrc` is a generated redirect stub that points into version-controlled repository files.
  Uncoordinated vendor installer mutations corrupt that delivery model.
- **Symlinking into `$HOME`:** Scripts commonly symlink binaries into `~/.local/bin` using `ln -sf`,
  violating **Rule #1** (*No symlinks in `$HOME`*) by proxy.
- **Aggressive or broken uninstallation logic:**
  - **OpenAI Codex:** The standalone script interactively prompts to execute `brew uninstall`
    against any existing cask version.
  - **Google Antigravity:** The installer inspects `~/.local/bin/agy` and unconditionally exits 0
    without upgrading if a file is already present.
  - **Zed:** Upstream's `install.sh` is documented exclusively for Linux; on macOS, running it
    blindly executes `rm -rf /Applications/Zed.app` before repopulating it.

Homebrew casks avoid these pathologies by isolating downloads, staging applications cleanly into
`/Applications` or `/opt/homebrew`, and managing `$PATH` binaries without mutating user dotfiles.

### Specific tools deliberately handled differently

- **T3 Code (`cask "t3-code"`):** Ships in the `Brewfile` following the macOS installation
  instructions in its upstream repository. Note that T3 Code is an **alpha GUI control plane**, not
  a command-line interface. It lives in `/Applications/T3 Code (Alpha).app` and requires interactive
  provider setup.
- **No Claude Code in `Brewfile`:** Anthropic distributes [Claude Code](https://claude.ai/code) via
  its native installer into `~/.local/bin/claude`. The Homebrew cask `claude-code` installs an
  older binary to `/opt/homebrew/bin/claude`. Because `~/.zprofile` places `~/.local/bin` first on
  `$PATH`, a Homebrew cask would introduce a second binary that is silently shadowed and
  indefinitely stale. Claude Code is therefore kept out of `Brewfile` entirely.

---

## Rule #1 is intact: casks and symlinks

Rule #1 states: **Nothing in this repo ever creates a symlink in `$HOME`.**

While the `ghostty`, `zed`, and CLI casks internally make extensive use of symbolic links, **none
of those links reside in `$HOME`**:

- Applications reside in `/Applications/Ghostty.app` and `/Applications/Zed.app`.
- CLI binaries link into `/opt/homebrew/bin/` (e.g., `ghostty`, `zed`, `codex`, `copilot`, `agy`,
  `grok`, `terminal-notifier`).
- Manual pages link into `/opt/homebrew/share/man/`.
- Shell completions link into Homebrew's shared site-functions (within `/opt/homebrew/share/zsh`).
- Caskroom versions link under `/opt/homebrew/Caskroom/`.

Homebrew's internal hierarchy remains strictly contained outside `$HOME`. No symlink touches your
user profile.

---

## `auto_updates` casks: installer-of-record, not version manager

Five casks declared in `Brewfile` (`ghostty`, `zed`, `t3-code`, `copilot-cli`, `antigravity-cli`)
are declared with `auto_updates true` in Homebrew Cask.

For these packages, **Homebrew serves as the installer-of-record, not the ongoing version
manager**.

By design, `brew upgrade --cask` and `brew outdated` permanently skip `auto_updates` casks. The
application or binary manages its own updates via Sparkle or background self-updating routines.
This divergence is visible on a healthy system:

- GitHub Copilot CLI: the Caskroom directory records `0.0.396`, while `copilot --version` reports
  `1.0.80`.
- Zed: the Caskroom directory records `0.121.7`, while `Zed.app` reports `1.16.2`.

### Why we do not use `--greedy`

Homebrew provides `--greedy`, `HOMEBREW_UPGRADE_GREEDY`, and `HOMEBREW_UPGRADE_GREEDY_CASKS` to
force upgrades on `auto_updates` casks.

**We deliberately do not set or recommend `--greedy`.**

Explicitly forcing a cask upgrade bypasses Homebrew's downgrade protection. If Homebrew Cask's
upstream metadata lags behind a vendor's rapidly shipping in-app update channel, a greedy upgrade
will overwrite a newer, working app bundle with an older release from Homebrew's repository,
damaging local application state.

### `setup.sh` is convergent, not inert

`brew bundle install` upgrades outdated formulae (`brew` entries) and non-`auto_updates` casks by
default (unless `--no-upgrade` or `HOMEBREW_BUNDLE_NO_UPGRADE` is set).

Therefore, running `setup.sh` again on an existing installation is **convergent, not inert**. It
ensures new tools added to `Brewfile` are pulled down, verifies that Herdr integrations remain
current, and adopts pre-existing applications without error.

---

## Herdr agent integrations

[Herdr](https://herdr.dev) provides deeper multiplexer support for running coding agents.
`setup.sh` configures native integrations for the supported toolset:

```bash
HERDR_INTEGRATIONS="claude:.claude codex:.codex copilot:.copilot antigravity-cli:.gemini/config grok:.grok"
```

| Agent | Herdr Id | Precondition Directory | What Herdr Writes |
|---|---|---|---|
| Claude Code | `claude` | `~/.claude/` | `~/.claude/hooks/herdr-agent-state.sh`, `~/.claude/settings.json` |
| OpenAI Codex | `codex` | `~/.codex/` | `~/.codex/herdr-agent-state.sh`, `~/.codex/hooks.json` |
| GitHub Copilot | `copilot` | `~/.copilot/` | `~/.copilot/hooks/herdr-agent-state.sh`, `~/.copilot/settings.json` |
| Google Antigravity | `antigravity-cli` | `~/.gemini/config/` | `~/.gemini/config/hooks/herdr-agent-state.sh` |
| xAI Grok Build | `grok` | `~/.grok/` | `~/.grok/hooks/herdr-agent-state.sh` |

### Scope of the integration promise

It is vital to understand what these integrations provide and what they do not:

- **What they provide:** **Session identity.** The hook scripts emit session metadata (`session_id`,
  session resume tokens, and directory context), allowing Herdr to maintain pane continuity across
  server restarts and power commands like `grok --resume <id>`.
- **What they do NOT provide:** **Lifecycle state.** Whether an agent is actively working, idle, or
  waiting for user confirmation is still derived from Herdr's own terminal screen detection and PTY
  heuristics.

### Prerequisites and idempotency

- **Config directory precondition:** Herdr requires the agent's configuration directory to exist
  before installing hooks; it does not recursively create missing parent directories. If an agent
  has never been run (e.g. `~/.grok` on a fresh setup), `setup.sh` skips the integration and prints
  a notice to launch the agent once and re-run.
- **Idempotency against shared JSON:** Upstream Herdr does not guarantee deduplicated insertion
  when merging hooks into shared configuration files (`~/.claude/settings.json`,
  `~/.codex/hooks.json`, `~/.copilot/settings.json`). `setup.sh` guards updates by checking whether
  the agent is already marked `current` in `herdr integration status`. If current, the install step
  is skipped entirely.
- **No background service side-effect:** `setup.sh` does not run `brew services start herdr`.
  Herdr spawns its own server on invocation; running launchd daemons behind the scenes is an
  unwanted side-effect for an installation script.

---

## Two integration traps

### 1. The `python3` runtime gate

Every Herdr hook script begins with:

```sh
command -v python3 >/dev/null 2>&1 || exit 0
```

The `herdr` Homebrew formula has **zero dependencies** and does not declare a dependency on Python.
If `python3` is not on `$PATH`, the hook exits 0 immediately. `herdr integration status` will report
`current`, yet no identity payloads will ever reach the multiplexer at runtime.

`setup.sh` performs an explicit `python3` presence check and warns if it is missing.

### 2. Grok's Claude compatibility hook collision

Grok Build incorporates Claude Code compatibility by reading `~/.claude/settings.json` as an
always-on hook source.

Once Herdr's `claude` integration is installed, a Grok pane running inside Herdr parses Claude's
hook configuration and fires Claude's hook script in addition to its own. This leads to duplicate or
conflicting agent events.

The mitigation is to disable Claude hook compatibility in Grok's machine configuration:

```toml
# ~/.grok/config.toml
[compat.claude]
hooks = false
```

Because `~/.grok/config.toml` holds machine-local state and is not managed by this repo, this
must be applied manually once Grok has been initialized.

---

## Machine-state collisions to expect

`setup.sh` detects machine-state collisions and warns without removing user files:

- **`~/.local/bin/agy` shadows Homebrew:** If Google's standalone installer was previously run, it
  placed a binary in `~/.local/bin/agy`. When `~/.zprofile` places `~/.local/bin` before Homebrew
  locations on `$PATH`, the standalone binary will shadow `/opt/homebrew/bin/agy`. `setup.sh`
  warns of this condition but will never delete the file.
- **Existing application bundles:** If `/Applications/Ghostty.app` or `/Applications/Zed.app` was
  installed via standalone downloads, `brew bundle` leverages `bundle/cask.rb`'s `--adopt` handling
  to absorb existing bundles safely. A raw `brew install --cask` would otherwise abort with
  `CaskError`.
