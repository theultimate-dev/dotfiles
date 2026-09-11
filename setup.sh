#!/usr/bin/env bash
#
# setup.sh — install the tools the configs assume (macOS).
#
# Run this once on a new machine, then run ./install.sh to place the configs.
# Everything here is idempotent: re-running is safe and converges to current.
#
# setup.sh may use the network and Homebrew. install.sh may not — keep the
# split, so config delivery stays debuggable on a half-broken machine.
#
# Usage:
#   ./setup.sh           install what is missing; an app you installed by hand
#                        is left alone and reported
#   ./setup.sh --adopt   also hand those apps over to Homebrew, after checking
#                        the macOS permission that needs

set -euo pipefail

if [[ "$(uname)" != "Darwin" ]]; then
  echo "This script is for macOS only." >&2
  exit 1
fi

DOTFILES="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"

step() { echo; echo "==> $*"; }
warn() { echo "warning: $*" >&2; }

ADOPT=0
for arg in "$@"; do
  case "$arg" in
    --adopt) ADOPT=1 ;;
    -h|--help)
      sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "unknown option: $arg (try --help)" >&2
      exit 2
      ;;
  esac
done

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

# ── Apps installed outside Homebrew ───────────────────────────────────────
# Every cask in the Brewfile that installs an application bundle, paired with
# the bundle name. One per line rather than one per word: one name has spaces.
#
# An app is "pre-existing and unmanaged" when the bundle is in /Applications
# but Homebrew has no Caskroom entry for it -- Homebrew's own definition of
# installed. brew bundle would adopt it, and adoption is not the harmless
# no-op it looks like: a cask with an artifact inside the bundle (Zed's cli)
# modifies the bundle, which macOS gates behind the App Management permission
# for the terminal, may need sudo when the files belong to another user, and
# on a refused permission ends with Homebrew deleting the app while rolling
# back. So the default is to skip such apps and say so; --adopt opts in after
# probing the permission, before brew bundle can reach the destructive path.
# See docs/agent-tooling.md, "Apps you installed before Homebrew did".
CASK_APPS='ghostty:Ghostty.app
zed:Zed.app
t3-code:T3 Code (Alpha).app'

CASKROOM="$(brew --prefix)/Caskroom"
UNMANAGED_TOKENS=""
UNMANAGED_APPS=""
while IFS=: read -r token app; do
  [ -n "$token" ] || continue
  if [ -d "/Applications/$app" ] && [ ! -d "$CASKROOM/$token" ]; then
    UNMANAGED_TOKENS="${UNMANAGED_TOKENS:+$UNMANAGED_TOKENS }$token"
    UNMANAGED_APPS="${UNMANAGED_APPS:+$UNMANAGED_APPS
}  /Applications/$app"
  fi
done <<EOF
$CASK_APPS
EOF

# The probe Homebrew itself uses: creating a file inside a bundle this terminal
# did not install is what makes macOS show the App Management prompt, and the
# attempt that triggers the prompt is refused whatever the answer.
probe_app_management() {
  local probe="$1/.dotfiles-write-test"
  if ( : > "$probe" ) 2>/dev/null; then
    rm -f -- "$probe"
    return 0
  fi
  return 1
}

if [ -n "$UNMANAGED_TOKENS" ]; then
  step "Apps installed outside Homebrew"
  echo "$UNMANAGED_APPS"
  if [ "$ADOPT" -eq 1 ]; then
    echo
    echo "Handing these to Homebrew. Two prompts can follow:"
    echo "  - macOS asks to let your terminal update or delete other apps. Allow it."
    echo "    If the dialog appears now, this run stops; run ./setup.sh --adopt again."
    echo "  - A password prompt, if an app's files belong to another user."
    echo
    while IFS=: read -r token app; do
      [ -n "$token" ] || continue
      case " $UNMANAGED_TOKENS " in *" $token "*) ;; *) continue ;; esac
      bundle="/Applications/$app"
      if [ ! -w "$bundle" ]; then
        echo "$bundle is owned by $(stat -f %Su "$bundle"), not by you." >&2
        echo "Homebrew would fall back to sudo, and macOS still requires the permission" >&2
        echo "below. Fix the ownership or move the app aside, then re-run." >&2
        exit 1
      fi
      if ! probe_app_management "$bundle"; then
        echo "macOS refused a write inside $bundle." >&2
        echo "Allow your terminal under System Settings > Privacy & Security > App Management," >&2
        echo "then run ./setup.sh --adopt again. Nothing has been changed." >&2
        exit 1
      fi
    done <<EOF
$CASK_APPS
EOF
    echo "permission granted; adopting"
  else
    export HOMEBREW_BUNDLE_CASK_SKIP="$UNMANAGED_TOKENS"
    echo
    echo "Left untouched: Homebrew did not install these, so it will not take them over."
    echo "Taking them over asks macOS to let your terminal modify other apps, may ask for"
    echo "your password, and deletes the app if that permission is refused mid-way."
    echo "To hand them to Homebrew deliberately:  ./setup.sh --adopt"
  fi
elif [ "$ADOPT" -eq 1 ]; then
  step "Apps installed outside Homebrew"
  echo "none; every app in the Brewfile is already Homebrew-managed or absent"
fi

# ── Packages ──────────────────────────────────────────────────────────────
step "Brewfile"
# NOTE: no --no-lock. Homebrew removed Brewfile.lock.json generation and the
# flag along with it; passing it makes this script fail outright.
# brew bundle is one command for the whole list and honours the skip list set
# above; it also appends --adopt for casks, which is exactly why unmanaged apps
# are skipped rather than passed through.
export HOMEBREW_NO_ENV_HINTS=1
BUNDLE_FAILED=0
brew bundle install --file="$DOTFILES/Brewfile" || BUNDLE_FAILED=1
if [ "$BUNDLE_FAILED" -eq 1 ]; then
  warn "brew bundle reported failures; continuing with what did install"
fi

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
if [ "$BUNDLE_FAILED" -eq 1 ]; then
  warn "Homebrew reported failures above. Fix them and re-run ./setup.sh; it converges."
  exit 1
fi
echo "Setup complete."
