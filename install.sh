#!/usr/bin/env bash
# clamp installer.
#
# Verifies dependencies, symlinks `clamp` onto your PATH, and installs the
# read-thread skill into ~/.claude/skills.
#
# Usage:
#     ./install.sh                     # default install dir: ~/.local/bin
#     ./install.sh /usr/local/bin      # custom install dir
#     PREFIX=~/bin ./install.sh        # via env var
#     ./install.sh --skip-skill        # don't symlink the skill
#
# It's idempotent — re-running upgrades the symlinks in place.

set -euo pipefail

# Resolve the repo root (this file's directory).
SOURCE="${BASH_SOURCE[0]}"
while [[ -L "$SOURCE" ]]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
REPO="$(cd -P "$(dirname "$SOURCE")" && pwd)"

# --- args ---
PREFIX="${PREFIX:-$HOME/.local/bin}"
INSTALL_SKILL=1
for arg in "$@"; do
    case "$arg" in
        --skip-skill) INSTALL_SKILL=0 ;;
        --help|-h)
            sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        -*)
            echo "unknown flag: $arg" >&2; exit 1 ;;
        *)
            PREFIX="$arg" ;;
    esac
done

bold()   { printf '\033[1m%s\033[0m' "$*"; }
green()  { printf '\033[32m%s\033[0m' "$*"; }
yellow() { printf '\033[33m%s\033[0m' "$*"; }
red()    { printf '\033[31m%s\033[0m' "$*"; }

step() { printf '%s %s\n' "$(bold '▶')" "$*"; }
ok()   { printf '  %s %s\n' "$(green '✓')" "$*"; }
warn() { printf '  %s %s\n' "$(yellow '!')" "$*"; }
err()  { printf '  %s %s\n' "$(red '✗')" "$*"; }

# --- dep check ---
step "checking dependencies"
missing=()
for bin in tmux fzf python3 bash; do
    if command -v "$bin" >/dev/null 2>&1; then
        ok "$bin   $(command -v "$bin")"
    else
        err "$bin   not found"
        missing+=("$bin")
    fi
done

# claude is recommended but not strictly required for installation.
if command -v claude >/dev/null 2>&1; then
    ok "claude $(command -v claude)"
else
    warn "claude not on PATH — install Claude Code before using clamp."
    warn "  see https://docs.claude.com/en/docs/claude-code"
fi

if (( ${#missing[@]} )); then
    err "missing required tools: ${missing[*]}"
    err "install them and re-run: $0"
    exit 1
fi

# tmux version check (display-popup needs ≥3.2)
tmux_ver="$(tmux -V | awk '{print $2}')"
if ! awk -v v="$tmux_ver" 'BEGIN{
    split(v, a, "."); major=a[1]+0; minor=a[2]+0;
    exit !(major > 3 || (major==3 && minor>=2))
}'; then
    err "tmux $tmux_ver is too old; clamp needs ≥3.2 (display-popup)"
    exit 1
fi
ok "tmux $tmux_ver supports display-popup"

# --- symlink the binary ---
step "installing clamp into $PREFIX"
mkdir -p "$PREFIX"

dst="$PREFIX/clamp"
src="$REPO/bin/clamp"

if [[ -L "$dst" ]]; then
    rm -f "$dst"
elif [[ -e "$dst" ]]; then
    err "$dst exists and is not a symlink — refusing to overwrite."
    err "remove it manually first, then re-run."
    exit 1
fi

ln -s "$src" "$dst"
ok "$dst -> $src"

# --- PATH check ---
case ":$PATH:" in
    *":$PREFIX:"*) ok "$PREFIX is on your PATH" ;;
    *)
        warn "$PREFIX is NOT on your PATH yet."
        warn "  add this to ~/.zshrc / ~/.bashrc:"
        warn "      export PATH=\"$PREFIX:\$PATH\""
        ;;
esac

# --- skill install ---
if (( INSTALL_SKILL )); then
    step "installing read-thread skill into ~/.claude/skills"
    "$src" install-skill | sed 's/^/  /'
else
    warn "--skip-skill: not installing read-thread skill."
    warn "  run \`clamp install-skill\` later if you want @@<uuid> resolution."
fi

# --- done ---
echo
echo "$(bold "All set.") To start:"
echo "    $(green 'clamp')                   # in current dir"
echo "    $(green 'clamp ~/dev/myproject')   # in a specific dir"
echo
echo "Inside, press $(bold "C-f") for the command palette (switch / reference / handoff / new thread)."
