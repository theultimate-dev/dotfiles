# Security policy

## Supported versions

Only the latest release is supported. There are no backports: a fix ships as a new release, and
the changelog says what to re-run.

## What counts as a security issue here

This repository writes real files into `$HOME` on a machine someone depends on daily, so the
threat model is narrower than for a service but still real. Please report any of these:

- A tracked file, script, or workflow that writes outside the destinations documented in
  `AGENTS.md`, clobbers a file without backing it up, or creates a symlink.
- Anything tracked that leaks identity: an email address, a key ID, a token, a hostname, or a
  home-directory path.
- A command in the docs that does something other than what the surrounding text says it does.
- A supply-chain problem in the installer, `setup.sh`, the `Brewfile`, or a GitHub Actions
  workflow.

Bugs that are not one of these belong in a normal issue.

## How to report

Use GitHub's private vulnerability reporting for this repository:

<https://github.com/theultimate-dev/dotfiles/security/advisories/new>

Reports stay private until a fix is released. Please do not open a public issue for something that
could expose a user before a fix exists. Expect an acknowledgement within a week; this is a
volunteer-maintained project, so fixes follow as time allows.
