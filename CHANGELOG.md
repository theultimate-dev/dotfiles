# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-09-13

The first release: the installer, the tool list, and four managed configurations, with the
reasoning behind each recorded in `docs/` and `docs/decisions/`.

### Added

- `install.sh`: offline configuration placement depending strictly on macOS system bash 3.2 and
  coreutils. It writes native include stubs inside named delimited blocks (`# BEGIN dotfiles
  (public)` ... `# END dotfiles (public)`), preserving every byte outside the block, with atomic
  temp-file writes, pre-modification backups in `~/.dotfiles-backup/` with a manifest, and an empty
  `~/.gitconfig` creation guard so `git config --global` never targets a managed file. Markers are
  matched as whole lines, a destination carrying only one of the two markers is refused rather than
  guessed at, and file permissions survive an in-place update. `--dry-run` previews and `--check`
  reports drift with a non-zero exit. A second primitive, `apply_copy`, places the one config whose
  tool has no include mechanism at all and reports drift instead of preventing it. The installer
  warns when the classic `~/.config/ghostty/config` is non-empty, since Ghostty loads it too and the
  repo's `config-file` include beats every key in it; `local.ghostty` is where those settings win
  again.
- `Brewfile` and `setup.sh`: Homebrew-based installation of the daily tool set — Ghostty, Zed, T3
  Code, Herdr and `terminal-notifier`, micro, hunk and the GitHub CLI, figlet for banner text in
  screenshots and demos, Yazi and glow with the tools Yazi previews through (`fd`, `ripgrep`, `fzf`,
  `zoxide`, `poppler`, `ffmpeg`, `imagemagick`, `jq`, `sevenzip`, `resvg`), the
  `font-symbols-only-nerd-font` cask for Yazi's icons in Zed's terminal, and the OpenAI Codex,
  GitHub Copilot, Google Antigravity and xAI Grok Build agent CLIs — plus Herdr's session-identity
  integration for every agent whose config directory exists, and Yazi's plugins restored from the
  tracked lockfile. Re-running is safe and convergent. An app already in `/Applications` that
  Homebrew did not install is listed and skipped; `./setup.sh --adopt` hands it to Homebrew after
  checking the macOS App Management permission, so a refused dialog can no longer make Homebrew's
  rollback delete the app. A failed `brew bundle` no longer stops the script: the remaining steps
  run for what did install and the exit code is non-zero at the end.
- Git push defaults (`git/.gitconfig`), included from `~/.config/git/config`: pushing a new local
  branch creates the matching remote branch and tracks it, instead of failing with a name mismatch
  or pushing to the branch you started from. Requires git 2.37 or newer. Three aliases open a
  review in hunk beside the git commands they mirror — `git hdiff`, `git hshow`, `git hlog` — and
  keep a relative pathspec working from a subdirectory. Nothing sets `core.pager`.
- Ghostty configuration (`ghostty/config.ghostty`): font, a theme that follows the macOS
  appearance, window and clipboard behaviour, shell integration, and the notification settings
  that turn an agent's escape sequences into macOS notifications. Reached through a `config-file`
  block placed at the top of `~/.config/ghostty/config.ghostty`; machine-local overrides go in
  `~/.config/ghostty/local.ghostty`, which that block includes last. Ghostty 1.2.3 or newer is
  required for the file name.
- Yazi configuration (`yazi/`): files open in micro, a `.md` file opens in glow's pager with micro
  one pick-menu entry away, the preview pane renders Markdown through glow, and a git status mark
  sits next to every changed file and directory. Reached through `YAZI_CONFIG_HOME`, exported from
  a block appended to `~/.zshenv`; the repo directory is Yazi's config directory, so there is no
  machine-local override file. Open a new shell after installing. Yazi 25 or newer is required.
- hunk configuration (`hunk/config.toml`): a live diff pane for agent work — `hunk diff --watch`
  renders the whole working tree, untracked files included, and redraws as a coding agent edits.
  Unlike every other config here it is **copied** to `~/.config/hunk/config.toml`, because hunk
  has no include directive or config variable and a repeated TOML key is a parse error. Editing
  the repo file needs a `./install.sh` re-run, and `./install.sh --check` reports when the two have
  drifted. Anything already at the destination is backed up first.
- The `micro` terminal editor, for quick edits next to a running coding agent. Nothing sets
  `$EDITOR` to it yet; that arrives with the zsh configuration.
- Manual setup guide (`docs/manual-setup.md`), the single place to look after cloning: every step
  that has to be done by hand, in order, each with a command to verify it and a command to undo it —
  agent installs and logins, Claude Code through its native installer, provider API keys, Herdr's
  notification settings, the macOS notification permission and alert style, two known collisions,
  and Zed's font fallback for Yazi's icons.
- Guides in `docs/`: agent tooling and installation (why Homebrew for everything, how
  `auto_updates` casks behave, the Herdr integration lifecycle and its traps); git push defaults
  (why `push.autoSetupRemote` alone does not create the remote branch, and why the popular
  `push.default = current` workaround is worse than the problem); Herdr notifications on macOS
  (why a multiplexer silences the terminal-side setup, which delivery mode to use, how to make a
  notification stay on screen, and the one Claude Code setting that reaches Ghostty, Herdr and
  Zed's Terminal Threads); Yazi (the delivery through `YAZI_CONFIG_HOME`, the first-run trap, and
  why Markdown is matched by name); and hunk (the live pane, reviewing a commit, a branch or a pull
  request, and why this config is copied).
- Decision records `docs/decisions/0001` to `0011`, in Michael Nygard's five-section format,
  recording why the delivery model is what it is: include stubs instead of symlinks; git included
  from `~/.config/git/config` and never `~/.gitconfig`; Homebrew as the single install channel;
  auto-updating casks left to manage themselves; agent configuration deliberately unmanaged; shared
  destinations owned through named delimited blocks; pre-existing apps left unadopted; one agent
  notification channel across hosts; the Ghostty block inserted first; a config directory exported
  from `~/.zshenv`; and the hunk config copied with drift reported — each with the alternative that
  lost — and an index (`docs/decisions/README.md`) that states each decision in a sentence.
- `.ignore` file that keeps the untracked `spec/` directory readable by search tools, so
  implementation specs stay out of version control without becoming invisible to coding agents.
- MIT licence, covering the configuration and documentation in this repository. The third-party
  tools shown here remain under their own licences.

[Unreleased]: https://github.com/theultimate-dev/dotfiles/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/theultimate-dev/dotfiles/releases/tag/v0.1.0
