# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-10-31

### Added

- Herdr configuration in `herdr/`, kept here and applied by hand or by a coding agent — never by a
  script, because Herdr's config file is also written by Herdr itself and by its plugins (see
  [ADR 0013](docs/decisions/0013-apply-the-herdr-config-by-hand.md)). It carries the notification
  setup, `prefix+g` to the pane behind a notification, and
  [herdr-radar](https://github.com/hhdebb/herdr-radar): a sidebar that shows which agents are
  working and which are waiting on you, grouped by project, with `prefix+a` to flip its order and
  `prefix+comma` for its settings. `setup.sh` installs the plugin at the release pinned in
  `herdr/plugins.txt`, and Renovate opens a pull request for each new one. The plugin needs Node 18
  or newer, which this repository does not install yet. It also maps its icon font in every Ghostty
  config file that already exists; one in `~/Library/Application Support/com.mitchellh.ghostty/`
  makes `./install.sh --check` warn that the file is non-empty, which is harmless, and
  [Herdr plugins](docs/agent-tooling.md#herdr-plugins) says how to silence it. **Upgrade steps:**
  run `./setup.sh`, then [step 3 of the manual setup](docs/manual-setup.md#3-configure-herdr),
  which copies the files onto a Mac with no Herdr config yet, says what to merge into one that has,
  and writes the plugin's sidebar into Herdr's config. Step 3 also has a prompt to hand the whole
  step to an agent.

### Changed

- Herdr notifications, step 4 of the manual setup in 0.3.0, is now step 3, "Configure Herdr". It
  applies the tracked `herdr/config.toml` instead of appending four tables to your Herdr config by
  hand. A config set up from the old step already holds those tables; merge the rest of the file
  into it as step 3 describes.

### Removed

- T3 Code. It is no longer in the `Brewfile`, `setup.sh` neither installs it nor reports a copy
  you installed by hand, and its step in the manual setup is gone, so the later steps there move
  up one number: the Herdr step is now step 3 and Colima step 7. An existing installation is left
  alone; to remove it, run `brew uninstall --cask t3-code`, and revoke any provider API keys you
  issued for it.

## [0.3.0] - 2026-10-29

### Added

- Colima with the Docker CLI and its Compose and Buildx plugins in the `Brewfile`: Docker's engine
  in a Linux VM on Apple's Virtualization.framework, with no Docker Desktop. The VM runs only when
  you start it. [docs/colima.md](docs/colima.md) explains the flags for Apple silicon, how to size
  the CPUs, memory and disk for several Compose stacks at once, and four traps, including file
  watchers in containers that never see your edits without `--mount-inotify`. **Upgrade steps:**
  run `./setup.sh`, then
  [step 8 of the manual setup](docs/manual-setup.md#8-run-containers-with-colima), which lists
  Homebrew's plugin directory in `~/.docker/config.json` and creates the VM.

## [0.2.0] - 2026-09-19

### Added

- Security policy (`SECURITY.md`): what counts as a security issue for a repository that writes
  into `$HOME` — a write outside the documented destinations, a silent clobber, a symlink, or
  leaked identity — and where to report one privately through GitHub's vulnerability reporting
  form, so no contact address lives in the repository.

### Changed

- Clarified versioning around the installation and configuration model: tool additions and
  replacements are minor releases, even when a routine setup or dependency installation is
  required. Incompatible changes to the model remain major releases, before and after 1.0.

- Replaced Glow with Leaf for Yazi's Markdown reader and preview pane, using the dark Ocean
  theme in both. Leaf adds terminal Mermaid diagrams, math rendering, a table of contents, and
  `Ctrl+E` to edit in micro. **Migration required:** install Homebrew's `leaf-markdown-viewer`
  formula before restarting Yazi; existing config stubs need no reinstall. See
  [the migration steps](docs/manual-setup.md#switch-an-existing-installation-from-glow-to-leaf).
  Glow is no longer in the Brewfile, but an existing installation is left available for comparison.

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
- Release workflow (`.github/workflows/release.yml`): a pushed `vX.Y.Z` tag on `main` becomes a
  GitHub Release whose notes are that version's section of this file. It refuses a tag that is not
  on `main` or has no changelog section, and uses only `actions/checkout` and the GitHub CLI.
- `.ignore` file that keeps the untracked `spec/` directory readable by search tools, so
  implementation specs stay out of version control without becoming invisible to coding agents.
- MIT licence, covering the configuration and documentation in this repository. The third-party
  tools shown here remain under their own licences.

[Unreleased]: https://github.com/theultimate-dev/dotfiles/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/theultimate-dev/dotfiles/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/theultimate-dev/dotfiles/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/theultimate-dev/dotfiles/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/theultimate-dev/dotfiles/releases/tag/v0.1.0
