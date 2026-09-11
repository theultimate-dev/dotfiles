#!/usr/bin/env bash
#
# install.sh — place configuration stubs into destination files (macOS).
#
# Composes with existing configs by writing native include stubs inside
# named delimited blocks. Never creates symlinks. Never touches the network.
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
      cat <<'EOF'
Usage: ./install.sh [OPTIONS]

Place configuration stubs into destination files without symlinks.

Options:
  --dry-run   Show what would be changed without touching any files
  --check     Report drift and exit non-zero if anything is missing or changed
  -h, --help  Show this help message
EOF
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

# ── 1. Git configuration ───────────────────────────────────────────────────
step "Git configuration"

GLOBAL_GIT_CONFIG="$HOME/.gitconfig"
XDG_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}"
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

GIT_BLOCK_CONTENT="$(cat <<EOF
$BEGIN_MARKER
[include]
	path = $DOTFILES/git/.gitconfig
$END_MARKER
EOF
)"

apply_block() {
  local target="$1"
  local expected_block="$2"
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

  # Target exists: extract current block if present
  local current_block=""
  if grep -qF "$BEGIN_MARKER" "$target" && grep -qF "$END_MARKER" "$target"; then
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
    if [[ -z "$current_block" ]]; then
      echo "drift: $target is missing managed block"
    else
      echo "drift: $target managed block differs from expected include path"
    fi
    DRIFT=1
    return
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    if [[ -z "$current_block" ]]; then
      echo "would append managed block to $target:"
    else
      echo "would update managed block in $target:"
    fi
    printf '%s\n' "$expected_block"
    return
  fi

  # Apply change atomically
  backup_file "$target"
  local tmp_file="${target}.tmp.$$"
  local tmp_block="${target_dir}/.block.tmp.$$"
  printf '%s\n' "$expected_block" > "$tmp_block"

  if grep -qF "$BEGIN_MARKER" "$target" && grep -qF "$END_MARKER" "$target"; then
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
  else
    rm -f "$tmp_block"
    cp -p "$target" "$tmp_file"
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

apply_block "$XDG_GIT_CONFIG" "$GIT_BLOCK_CONTENT"

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
