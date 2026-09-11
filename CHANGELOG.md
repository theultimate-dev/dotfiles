# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Yazi configuration (`yazi/`), the third managed config: files open in micro, a `.md` file opens
  in glow's pager with micro one pick-menu entry away, the preview pane renders Markdown through
  glow, and a git status mark sits next to every changed file and directory. Yazi is reached
  through `YAZI_CONFIG_HOME`, which `install.sh` exports from a block appended to `~/.zshenv`; the
  repo directory is Yazi's config directory, so there is no machine-local override file for it.
  Re-run `./setup.sh` (installs Yazi and restores its two plugins) then `./install.sh`, and open a
  new shell. Yazi 25 or newer is required for the opener syntax.
- Decision record `docs/decisions/0010-export-a-config-directory-variable-from-zshenv.md`,
  recording why Yazi is pointed at the repo through an environment variable in `~/.zshenv` rather
  than an include stub or a byte copy, and what that costs.
- `Brewfile`: `yazi` and `glow`, the tools Yazi previews through (`fd`, `ripgrep`, `fzf`,
  `zoxide`, `poppler`, `ffmpeg`, `imagemagick`, `jq`, `sevenzip`, `resvg`), and the
  `font-symbols-only-nerd-font` cask that Zed's terminal needs for Yazi's icons; Ghostty has them
  built in.
- `setup.sh`: restores Yazi's plugins from the tracked `yazi/package.toml` lockfile with `ya pkg
  install`, after the Brewfile step.
- `docs/yazi.md`, the deep dive on the Yazi setup, and step 7 in `docs/manual-setup.md` for the
  Zed font fallback.
- Ghostty configuration (`ghostty/config.ghostty`), the second managed config: font, a theme that
  follows the macOS appearance, window and clipboard behaviour, shell integration, and the
  notification settings that turn an agent's escape sequences into macOS notifications.
  `install.sh` reaches it through a `config-file` block placed at the top of
  `~/.config/ghostty/config.ghostty`; machine-local overrides go in
  `~/.config/ghostty/local.ghostty`, which that block includes last. Re-run `./install.sh` to get
  it; Ghostty 1.2.3 or newer is required for the file name.
- Decision record `docs/decisions/0008-keep-one-agent-notification-channel-across-hosts.md`,
  recording why `iterm2_with_bell` stays the only Claude Code notification setting across Zed,
  Ghostty and Herdr, why persistence is left to the macOS alert style, and which alternatives lost.
- Decision record `docs/decisions/0009-insert-the-ghostty-block-first.md`, recording why the
  Ghostty include block goes first in the destination file: Ghostty applies every `config-file`
  after the whole file, in order, later file wins.
- The `micro` terminal editor, installed through `Brewfile`, for quick edits next to a running
  coding agent in Herdr or a plain terminal. Nothing sets `$EDITOR` to it yet; that arrives with
  the zsh port.
- `install.sh`: automated, offline configuration placement script depending strictly on macOS system
  bash 3.2 and coreutils. Manages destination include stubs using named delimited blocks (`# BEGIN
  dotfiles (public)` ... `# END dotfiles (public)`), with atomic temp-file writes, pre-modification
  backups in `~/.dotfiles-backup/`, an empty `~/.gitconfig` creation guard, and non-destructive
  `--dry-run` and `--check` drift detection.
- Decision record `docs/decisions/0006-manage-shared-destinations-with-delimited-blocks.md`,
  documenting why shared destination files are managed through named delimited blocks rather than
  symlinks, wholesale rewrites, or single-sentinel schemes.
- `Brewfile` and `setup.sh` to install daily macOS development tools and coding agents via Homebrew
  (Ghostty, Zed, Herdr, T3 Code, OpenAI Codex, GitHub Copilot CLI, Google Antigravity CLI, and xAI
  Grok Build), plus automated installation for Herdr session identity integrations. An app
  already in `/Applications` that Homebrew did not install is listed and skipped;
  `./setup.sh --adopt` hands it to Homebrew after checking the macOS App Management permission.
- Decision record `docs/decisions/0007-leave-pre-existing-apps-unadopted-by-default.md`,
  recording why `setup.sh` never adopts an app you installed by hand unless asked: adoption can
  trigger a macOS permission dialog and a `sudo` prompt, and a refused dialog makes Homebrew's
  rollback delete the app.
- Decision records in `docs/decisions/`, in Michael Nygard's five-section ADR format, recording why
  the delivery model is what it is: include stubs instead of symlinks, git included from
  `~/.config/git/config`, Homebrew as the single install channel, auto-updating casks left to manage
  themselves, and agent configuration deliberately unmanaged — each with the alternative that lost.
- Git push defaults (`git/.gitconfig`), the first managed configuration in this repo: pushing a
  new local branch now creates the matching remote branch and tracks it, instead of failing with a
  name mismatch or pushing to the branch you started from. Requires git 2.37 or newer. Nothing
  installs it automatically yet — `docs/manual-setup.md` has the one-line include that turns it on.
- Guide to agent tooling (`docs/agent-tooling.md`), detailing package management decisions,
  `auto_updates` cask behavior, and Herdr integration requirements and traps.
- Guide to git push defaults (`docs/git-push-defaults.md`), covering why `push.autoSetupRemote`
  alone does not create the remote branch, why the popular `push.default = current` workaround
  leaves the upstream pointing at the wrong branch, and a git worktree branch-naming trap.
- `.ignore` file that keeps the untracked `spec/` directory readable by search tools, so
  implementation specs stay out of version control without becoming invisible to coding agents.
- Initial public documentation: the no-symlink delivery model, what is in scope for this repo and
  what deliberately stays private, and a guide to getting reliable "agent finished" notifications
  when running coding agents inside Herdr on macOS — with a Claude Code channel
  (`iterm2_with_bell`) that also reaches terminals that only listen for the bell, such as Zed's
  Terminal Threads.
- Manual setup guide (`docs/manual-setup.md`), the single place to look after cloning: every step
  that has to be done by hand, in order, each with a command to verify it worked and a command to
  undo it. It covers the steps no installer will ever take over — agent logins, provider API keys,
  and the macOS notification permission — as well as the ones `install.sh` will absorb when it
  lands.
- MIT licence, covering the configuration and documentation in this repository. The third-party
  tools shown here remain under their own licences.

### Changed

- `install.sh` matches its block markers as whole lines, refuses a destination that carries only
  one of the two markers instead of appending a second block, and keeps a destination's file
  permissions when it updates a block in place.
- The Herdr notifications guide and the manual setup now cover making a notification stay on
  screen (the per-app Persistent alert style in System Settings, which no installer can set), what
  the number on Ghostty's Dock icon is, and how the same Claude Code setting reaches Zed's
  Terminal Threads with no Zed-side setup. The manual setup's live test no longer points at the
  wrong step when nothing appears.
- `setup.sh` no longer lets Homebrew adopt an app you installed by hand. Such apps are listed and
  skipped; `./setup.sh --adopt` opts in, names the macOS App Management dialog and the possible
  password prompt first, and stops before `brew bundle` if the permission is refused, so
  Homebrew's rollback can no longer delete the app.
- `setup.sh` keeps going when `brew bundle` reports a failure: the python3 check, the Herdr
  integrations and the post-install notes still run for what did install, and the script exits
  non-zero at the end instead of stopping at the failed package.
- `setup.sh` silences Homebrew's environment hints for its own run, so its output is shorter.
- `README.md` now opens with a Quick Start — clone, `./setup.sh`, `./install.sh`, and a pointer
  to the manual steps — and documents `install.sh` with its `--dry-run` and `--check` flags now
  that it has landed.
- `docs/manual-setup.md` pruned temporary step 4 (Git push defaults), as it is now automated by
  `install.sh`, and updated subsequent step numbering and verification commands.
- `docs/git-push-defaults.md` updated activation instructions to run `./install.sh`.
- `AGENTS.md` no longer describes git configuration as a shared `~/.gitconfig` owned through
  BEGIN/END sentinel blocks. That scheme was superseded when the repo moved to including from
  `~/.config/git/config`, and the invariant, the precedence table and the machine-local override
  column now match what the installer will actually do.
- The Herdr notifications guide and the README no longer carry setup commands; they explain the
  reasoning and link to `docs/manual-setup.md` for the steps, so any command that writes to your
  home directory now appears in exactly one place in this repository.
- README now describes the git delivery model as include-only into `~/.config/git/config`: this
  repo never writes `~/.gitconfig`, so anything you have set there overrides everything it ships.
  The previous description — both dotfiles repos composing into a single `~/.gitconfig` — was
  wrong, and is corrected rather than reworded.
- README installation section and repository layout updated to introduce `setup.sh` and `Brewfile`.
- README expanded from a placeholder into a project overview: what is in scope, why there are no
  symlinks, that macOS is the only supported platform, and what installation will look like once
  the installer lands.

[Unreleased]: https://github.com/theultimate-dev/dotfiles/commits/main
