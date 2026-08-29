# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `Brewfile` and `setup.sh` to install daily macOS development tools and coding agents via Homebrew
  (Ghostty, Zed, Herdr, T3 Code, OpenAI Codex, GitHub Copilot CLI, Google Antigravity CLI, and xAI
  Grok Build), plus automated installation for Herdr session identity integrations.
- Guide to agent tooling (`docs/agent-tooling.md`), detailing package management decisions,
  `auto_updates` cask behavior, and Herdr integration requirements and traps.
- Initial public documentation: the no-symlink delivery model, what is in scope for this repo and
  what deliberately stays private, and a guide to getting reliable "agent finished" notifications
  when running coding agents inside Herdr on macOS.
- MIT licence, covering the configuration and documentation in this repository. The third-party
  tools shown here remain under their own licences.

### Changed

- README expanded from a placeholder into a project overview: what is in scope, why there are no
  symlinks, that macOS is the only supported platform, and what installation will look like once
  the installer lands.

[Unreleased]: https://github.com/theultimate-dev/dotfiles/commits/main
