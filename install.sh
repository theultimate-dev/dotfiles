#!/usr/bin/env bash
#
# install.sh — place configuration stubs into destination files (macOS).
#
# Composes with existing configs by writing native include stubs inside
# named delimited blocks. Never creates symlinks. Never touches the network.
#
# Destinations:
#   ~/.config/git/config              [include] path = <repo>/git/.gitconfig
#   ~/.config/ghostty/config.ghostty  config-file = <repo>/ghostty/config.ghostty
#
# Flags:
#   --dry-run   Show planned actions without modifying any files.
#   --check     Report drift; exit 0 if up to date, 1 if drifted/missing.
#   -h, --help  Show this help message.
#
# Depends strictly on macOS bash 3.2 and coreutils.

set -euo pipefail

if [[ "$(uname)" != "Darwin" ]]; then
  echo "error: this script is for macOS only." >&2
  exit 1
fi

DOTFILES="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"

DRY_RUN=0
CHECK=0
DRIFT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --check)
      CHECK=1
      shift
      ;;
    -h|--help)
      cat <<'HELP'
Usage: ./install.sh [OPTIONS]

Place configuration stubs into destination files without symlinks.

Destinations:
  ~/.config/git/config              include of <repo>/git/.gitconfig
  ~/.config/ghostty/config.ghostty  include of <repo>/ghostty/config.ghostty

Options:
  --dry-run   Show what would be changed without touching any files
  --check     Report drift and exit non-zero if anything is missing or changed
  -h, --help  Show this help message
HELP
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

step() { echo; echo "==> $*"; }
warn() { echo "warning: $*" >&2; }
err()  { echo "error: $*" >&2; }

BACKUP_DIR="$HOME/.dotfiles-backup"
MANIFEST="$BACKUP_DIR/manifest.log"

record_manifest() {
  local action="$1"
  local path="$2"
  local note="${3:-}"
  if [[ "$DRY_RUN" -eq 1 || "$CHECK" -eq 1 ]]; then
    return
  fi
  mkdir -p "$BACKUP_DIR"
  local timestamp
  timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "$timestamp | $action | $path | $note" >> "$MANIFEST"
}

backup_file() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    return
  fi
  if [[ "$DRY_RUN" -eq 1 || "$CHECK" -eq 1 ]]; then
    return
  fi
  mkdir -p "$BACKUP_DIR"
  local rel_name
  rel_name="$(printf '%s' "${file#$HOME/.}" | tr / -)"
  local backup_path="$BACKUP_DIR/$rel_name"
  if [[ ! -e "$backup_path" ]]; then
    cp -p "$file" "$backup_path"
    record_manifest "BACKUP" "$file" "$backup_path"
  fi
}

BEGIN_MARKER="# BEGIN dotfiles (public)"
END_MARKER="# END dotfiles (public)"

# apply_block TARGET EXPECTED_BLOCK [append|prepend]
#
# Owns exactly one named block in TARGET and preserves every byte outside it.
# The position argument is consulted only when TARGET exists and has no block
# yet: `append` (default) puts the block at the end, `prepend` at the top.
# An existing block is updated in place wherever it sits, and --check never
# treats position as drift: a second manager applying the opposite rule would
# otherwise move the block back and forth on alternating runs.
apply_block() {
  local target="$1"
  local expected_block="$2"
  local position="${3:-append}"
  local target_dir
  target_dir="$(dirname "$target")"

  if [[ ! -f "$target" ]]; then
    if [[ "$CHECK" -eq 1 ]]; then
      echo "drift: $target does not exist"
      DRIFT=1
      return
    elif [[ "$DRY_RUN" -eq 1 ]]; then
      echo "would create $target with managed block:"
      printf '%s\n' "$expected_block"
      return
    else
      mkdir -p "$target_dir"
      local tmp_file="${target}.tmp.$$"
      printf '%s\n' "$expected_block" > "$tmp_file"
      mv "$tmp_file" "$target"
      record_manifest "CREATE" "$target" "managed include block"
      echo "created $target with managed include block"
      return
    fi
  fi

  # Target exists. Markers are matched as whole lines (-x): a neighbouring
  # line that merely contains the marker text belongs to someone else.
  local has_begin=0
  local has_end=0
  if grep -qxF "$BEGIN_MARKER" "$target"; then has_begin=1; fi
  if grep -qxF "$END_MARKER" "$target"; then has_end=1; fi
  if [[ "$has_begin" -ne "$has_end" ]]; then
    err "$target contains only one of the two block markers. Refusing to guess; repair it by hand."
    exit 1
  fi

  local current_block=""
  if [[ "$has_begin" -eq 1 ]]; then
    current_block="$(awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
      $0 == begin { in_b=1; print; next }
      $0 == end   { in_b=0; print; next }
      in_b        { print }
    ' "$target")"
  fi

  if [[ "$current_block" == "$expected_block" ]]; then
    if [[ "$CHECK" -eq 0 && "$DRY_RUN" -eq 0 ]]; then
      echo "ok: $target block is up to date"
    fi
    return
  fi

  # Block is either missing or outdated
  if [[ "$CHECK" -eq 1 ]]; then
    if [[ "$has_begin" -eq 0 ]]; then
      echo "drift: $target is missing managed block"
    else
      echo "drift: $target managed block differs from expected include path"
    fi
    DRIFT=1
    return
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    if [[ "$has_begin" -eq 0 ]]; then
      echo "would $position managed block to $target:"
    else
      echo "would update managed block in $target:"
    fi
    printf '%s\n' "$expected_block"
    return
  fi

  # Apply change atomically. cp -p first so the temp file carries the
  # destination's mode; every path below then overwrites its contents.
  backup_file "$target"
  local tmp_file="${target}.tmp.$$"
  cp -p "$target" "$tmp_file"

  if [[ "$has_begin" -eq 1 ]]; then
    local tmp_block="${target_dir}/.block.tmp.$$"
    printf '%s\n' "$expected_block" > "$tmp_block"
    awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" -v block_file="$tmp_block" '
      $0 == begin {
        in_b=1
        while ((getline line < block_file) > 0) print line
        close(block_file)
        next
      }
      $0 == end { in_b=0; next }
      !in_b     { print }
    ' "$target" > "$tmp_file"
    rm -f "$tmp_block"
    mv "$tmp_file" "$target"
    record_manifest "UPDATE" "$target" "updated managed include block"
    echo "updated managed block in $target"
  elif [[ "$position" == "prepend" ]]; then
    # The original bytes follow the block verbatim, so a missing trailing
    # newline stays missing. An empty file gets the block and nothing else.
    if [[ -s "$target" ]]; then
      { printf '%s\n\n' "$expected_block"; cat "$target"; } > "$tmp_file"
    else
      printf '%s\n' "$expected_block" > "$tmp_file"
    fi
    mv "$tmp_file" "$target"
    record_manifest "PREPEND" "$target" "prepended managed include block"
    echo "prepended managed block to $target"
  else
    # Ensure newline separation before appending
    if [[ -s "$tmp_file" && -n "$(tail -c 1 "$tmp_file")" ]]; then
      printf '\n' >> "$tmp_file"
    fi
    printf '\n%s\n' "$expected_block" >> "$tmp_file"
    mv "$tmp_file" "$target"
    record_manifest "APPEND" "$target" "appended managed include block"
    echo "appended managed block to $target"
  fi
}

XDG_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}"

# ── 1. Git configuration ───────────────────────────────────────────────────
step "Git configuration"

GLOBAL_GIT_CONFIG="$HOME/.gitconfig"
XDG_GIT_CONFIG="$XDG_CONFIG_DIR/git/config"

# Guard: Ensure ~/.gitconfig exists so git config --global never writes to XDG
if [[ ! -e "$GLOBAL_GIT_CONFIG" ]]; then
  if [[ "$CHECK" -eq 1 ]]; then
    echo "drift: $GLOBAL_GIT_CONFIG is absent (needed so git config --global never targets XDG)"
    DRIFT=1
  elif [[ "$DRY_RUN" -eq 1 ]]; then
    echo "would create empty $GLOBAL_GIT_CONFIG (so git config --global never targets XDG)"
  else
    touch "$GLOBAL_GIT_CONFIG"
    record_manifest "CREATE_EMPTY" "$GLOBAL_GIT_CONFIG" "guarantees git --global targets ~/.gitconfig"
    echo "created empty $GLOBAL_GIT_CONFIG"
  fi
else
  if [[ "$CHECK" -eq 0 && "$DRY_RUN" -eq 0 ]]; then
    echo "ok: $GLOBAL_GIT_CONFIG exists"
  fi
fi

# Symlink checks: refuse to write through a symlink
if [[ -L "$XDG_GIT_CONFIG" ]]; then
  err "$XDG_GIT_CONFIG is a symlink. Refusing to modify."
  exit 1
fi
if [[ -L "$XDG_CONFIG_DIR/git" ]]; then
  err "$XDG_CONFIG_DIR/git is a symlink. Refusing to modify."
  exit 1
fi

# Environment checks
if [[ -n "${GIT_CONFIG_GLOBAL:-}" ]]; then
  warn "GIT_CONFIG_GLOBAL is set ($GIT_CONFIG_GLOBAL); it overrides XDG and makes this layer inert."
fi

# System-scope shadow check (informational)
if command -v git >/dev/null 2>&1; then
  for key in push.autoSetupRemote push.default branch.autoSetupMerge; do
    if git config --system --get "$key" >/dev/null 2>&1; then
      warn "system-scope git config defines $key; this layer will shadow it"
    fi
  done
fi

GIT_BLOCK_CONTENT="$(cat <<EOT
$BEGIN_MARKER
[include]
	path = $DOTFILES/git/.gitconfig
$END_MARKER
EOT
)"

apply_block "$XDG_GIT_CONFIG" "$GIT_BLOCK_CONTENT" append

# ── 2. Ghostty configuration ───────────────────────────────────────────────
step "Ghostty configuration"

GHOSTTY_DIR="$XDG_CONFIG_DIR/ghostty"
GHOSTTY_CONFIG="$GHOSTTY_DIR/config.ghostty"
GHOSTTY_LOCAL="$GHOSTTY_DIR/local.ghostty"

# Symlink checks: refuse to write through a symlink
if [[ -L "$GHOSTTY_CONFIG" ]]; then
  err "$GHOSTTY_CONFIG is a symlink. Refusing to modify."
  exit 1
fi
if [[ -L "$GHOSTTY_DIR" ]]; then
  err "$GHOSTTY_DIR is a symlink. Refusing to modify."
  exit 1
fi

# Both paths land unquoted in a config-file value. Ghostty offers no escaping
# this script can rely on for these characters, so refuse rather than guess.
# A mid-path '#' is fine: Ghostty accepts it inside a value.
NL=$'\n'
for p in "$DOTFILES" "$GHOSTTY_LOCAL"; do
  case "$p" in
    *'"'*|*'\'*|*"$NL"*|[[:space:]]*|*[[:space:]])
      err "cannot embed '$p' in a Ghostty config-file value (quote, backslash, newline, or edge whitespace). Move the clone."
      exit 1
      ;;
  esac
done

# Ghostty also reads its Application Support directory, after the XDG files.
# Keys there lose to every config-file include anyway, but a config-file line
# there that repeats one of ours makes Ghostty report "cycle detected".
for f in "$HOME/Library/Application Support/com.mitchellh.ghostty/config" \
         "$HOME/Library/Application Support/com.mitchellh.ghostty/config.ghostty"; do
  if [[ -s "$f" ]]; then
    warn "$f is non-empty; Ghostty loads it too. Do not repeat a config-file line there."
  fi
done

# Ghostty processes every config-file after the whole top-level file, in the
# order written, later file wins. The block therefore goes FIRST when the
# file already exists, so that another manager's includes keep beating this
# repo, and the optional local file comes last so that it beats everything.
GHOSTTY_BLOCK_CONTENT="$(cat <<EOT
$BEGIN_MARKER
# Ghostty applies every config-file after this whole file, later file wins;
# keys typed here are overridden by the repo. Overrides go in local.ghostty.
# No '?' on the repo line: a missing repo must be a loud config error.
config-file = $DOTFILES/ghostty/config.ghostty
config-file = ?$GHOSTTY_LOCAL
$END_MARKER
EOT
)"

apply_block "$GHOSTTY_CONFIG" "$GHOSTTY_BLOCK_CONTENT" prepend

# ── Summary ────────────────────────────────────────────────────────────────
if [[ "$CHECK" -eq 1 ]]; then
  if [[ "$DRIFT" -eq 1 ]]; then
    echo
    echo "Check failed: drift detected. Run ./install.sh to converge." >&2
    exit 1
  else
    echo
    echo "Check passed: all managed stubs are current."
    exit 0
  fi
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo
  echo "Dry run complete. No files were modified."
else
  echo
  echo "Installation complete."
fi
