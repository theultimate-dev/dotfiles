#!/usr/bin/env bash
#
# setup.sh — install the tools the configs assume (macOS).
#
# Run this once on a new machine, then run ./install.sh to place the configs.
# Everything here is idempotent: re-running is safe and converges to current.
#
# setup.sh may use the network and Homebrew. install.sh may not — keep the
# split, so config delivery stays debuggable on a half-broken machine.

set -euo pipefail

if [[ "$(uname)" != "Darwin" ]]; then
  echo "This script is for macOS only." >&2
  exit 1
fi

DOTFILES="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"

step() { echo; echo "==> $*"; }
warn() { echo "warning: $*" >&2; }

# ── Homebrew ──────────────────────────────────────────────────────────────
step "Homebrew"
if ! command -v brew &>/dev/null; then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # A fresh install is not on PATH yet in this shell.
  for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    [ -x "$candidate" ] && eval "$("$candidate" shellenv)" && break
  done
else
  echo "already installed: $(brew --version | head -1)"
fi

# ── Packages ──────────────────────────────────────────────────────────────
step "Brewfile"
# NOTE: no --no-lock. Homebrew removed Brewfile.lock.json generation and the
# flag along with it; passing it makes this script fail outright.
# brew bundle appends --adopt automatically for casks, absorbing direct downloads
# of applications like Ghostty.app or Zed.app without CaskError.
brew bundle install --file="$DOTFILES/Brewfile"

# ── python3 check ─────────────────────────────────────────────────────────
step "python3 check"
if ! command -v python3 >/dev/null 2>&1; then
  warn "python3 not found on PATH. Herdr agent integrations require python3 at runtime to execute their hooks."
else
  echo "python3 found ($(python3 --version))"
fi

# ── Herdr integrations ───────────────────────────────────────────────────
step "Herdr integrations"
if command -v herdr >/dev/null 2>&1; then
  HERDR_STATUS="$(herdr integration status 2>/dev/null || true)"
  HERDR_INTEGRATIONS="claude:.claude codex:.codex copilot:.copilot antigravity-cli:.gemini/config grok:.grok"

  for entry in $HERDR_INTEGRATIONS; do
    id="${entry%%:*}"
    dir="${entry#*:}"

    if [ ! -d "$HOME/$dir" ]; then
      echo "$id: skipped (~/$dir does not exist; launch $id once, then re-run setup.sh)"
      continue
    fi

    if echo "$HERDR_STATUS" | grep -q "^${id}: current"; then
      echo "$id: already current"
    else
      echo "$id: installing integration"
      herdr integration install "$id" || warn "failed to install integration: $id"
    fi
  done
else
  warn "herdr not found on PATH — skipping integrations"
fi

# ── Post-install notes ────────────────────────────────────────────────────
step "Post-install notes"
# The steps themselves are not listed here. They live in one file, with a check and
# an undo for each -- and a list duplicated into echo lines is a list nothing can
# verify against the real one.
echo "The tools are installed. Several still need you: agent logins, provider API"
echo "keys, and the configs this repo ships. Every remaining step, in order:"
echo
echo "  $DOTFILES/docs/manual-setup.md"

if [ -e "$HOME/.local/bin/agy" ]; then
  echo
  warn "~/.local/bin/agy shadows Homebrew's agy"
  echo "  A standalone installer placed an agy binary in ~/.local/bin."
  echo "  Because ~/.local/bin precedes Homebrew on PATH, the standalone binary"
  echo "  will be executed instead of the cask-managed version."
  echo "  To use the cask version, remove ~/.local/bin/agy manually."
fi

echo
echo "Setup complete."
