# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `Brewfile` and `setup.sh` to install daily macOS development tools and coding agents via Homebrew
  (Ghostty, Zed, Herdr, T3 Code, OpenAI Codex, GitHub Copilot CLI, Google Antigravity CLI, and xAI
  Grok Build), plus automated installation for Herdr session identity integrations.
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
  when running coding agents inside Herdr on macOS.
- Manual setup guide (`docs/manual-setup.md`), the single place to look after cloning: every step
  that has to be done by hand, in order, each with a command to verify it worked and a command to
  undo it. It covers the steps no installer will ever take over — agent logins, provider API keys,
  and the macOS notification permission — as well as the ones `install.sh` will absorb when it
  lands.
- MIT licence, covering the configuration and documentation in this repository. The third-party
  tools shown here remain under their own licences.

### Changed

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
