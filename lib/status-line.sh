#!/usr/bin/env bash
# clamp status-line helper.
#
# Prints, for the given working directory, a compact line for tmux's
# status-right:
#
#   <short-cwd>  <branch>  <status>
#
# Where:
#   short-cwd is $HOME collapsed to ~.
#   branch is the current git branch (or @<sha> for detached HEAD).
#   status is one of:
#     ✓                  — clean working tree
#     +N ~M ?K           — N staged, M unstaged-modified, K untracked
#
# Output uses tmux #[fg=...] color escapes (tmux re-interprets format
# directives in the output of #(...)).
#
# Usage: status-line.sh <pane_current_path>
#
# Designed to be cheap: runs every status-interval (5s by default). Uses
# git porcelain v1, which is fast even on large repos.

cwd="${1:-$PWD}"
[[ -d "$cwd" ]] || cwd="$PWD"

# tokyo-night-ish palette to match tmux.conf
CYAN='#[fg=#7dcfff]'
GREEN='#[fg=#9ece6a]'
YELLOW='#[fg=#e0af68]'
RED='#[fg=#f7768e]'
MAGENTA='#[fg=#bb9af7]'
DIM='#[fg=#565f89]'
RESET='#[default]'

# Collapse $HOME to ~. Use parameter expansion to avoid spawning sed.
short="${cwd/#$HOME/~}"

out="${CYAN}${short}${RESET}"

# Are we in a git repo?
if branch="$(git -C "$cwd" symbolic-ref --short HEAD 2>/dev/null)"; then
    porcelain="$(git -C "$cwd" status --porcelain=v1 2>/dev/null)"
    if [[ -z "$porcelain" ]]; then
        status="${GREEN}✓${RESET}"
    else
        # grep -c prints "0" on no match (exits 1, which we ignore — we are
        # not under `set -e`). Don't add a `|| echo 0` fallback: that would
        # double-print the count and break the arithmetic comparison below.
        staged=$(grep -cE '^[MARCDU]' <<<"$porcelain")
        unstaged=$(grep -cE '^.[MD]'  <<<"$porcelain")
        untracked=$(grep -cE '^\?\?'  <<<"$porcelain")
        parts=()
        (( staged    > 0 )) && parts+=("${GREEN}+${staged}${RESET}")
        (( unstaged  > 0 )) && parts+=("${YELLOW}~${unstaged}${RESET}")
        (( untracked > 0 )) && parts+=("${RED}?${untracked}${RESET}")
        # Join with spaces.
        status="${parts[*]}"
    fi
    out="${out}  ${MAGENTA}${branch}${RESET}  ${status}"
elif sha="$(git -C "$cwd" rev-parse --short HEAD 2>/dev/null)"; then
    # Detached HEAD: show short sha.
    out="${out}  ${MAGENTA}@${sha}${RESET}"
fi

printf '%s' "$out"
