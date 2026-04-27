#!/usr/bin/env python3
"""
Render a Claude Code thread .jsonl as a human-readable, scrollable transcript
suitable for fzf's preview pane.

Usage:
    render-thread.py <session-id> [cwd]
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
BLUE = "\x1b[34m"
CYAN = "\x1b[36m"
GREEN = "\x1b[32m"
MAGENTA = "\x1b[35m"
YELLOW = "\x1b[33m"
RED = "\x1b[31m"


def project_dir_for_cwd(cwd: str) -> Path:
    return CLAUDE_PROJECTS / cwd.replace("/", "-")


def find_jsonl(session_id: str, cwd: str) -> Path | None:
    direct = project_dir_for_cwd(cwd) / f"{session_id}.jsonl"
    if direct.exists():
        return direct
    # Fallback: scan all project dirs (cheap-ish; user has few)
    if CLAUDE_PROJECTS.is_dir():
        for pdir in CLAUDE_PROJECTS.iterdir():
            cand = pdir / f"{session_id}.jsonl"
            if cand.exists():
                return cand
    return None


def extract_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if not isinstance(item, dict):
                if isinstance(item, str):
                    parts.append(item)
                continue
            t = item.get("type")
            if t == "text":
                parts.append(item.get("text", ""))
            elif t == "tool_use":
                name = item.get("name", "tool")
                inp = item.get("input", {})
                summary = _summarize_tool_input(name, inp)
                parts.append(f"{MAGENTA}⚙ {name}{RESET} {DIM}{summary}{RESET}")
            elif t == "tool_result":
                txt = item.get("content")
                if isinstance(txt, list):
                    sub = []
                    for c in txt:
                        if isinstance(c, dict) and c.get("type") == "text":
                            sub.append(c.get("text", ""))
                    txt = "\n".join(sub)
                if not isinstance(txt, str):
                    txt = json.dumps(txt) if txt is not None else ""
                txt = txt.strip()
                if len(txt) > 500:
                    txt = txt[:500] + f" {DIM}…(truncated){RESET}"
                if txt:
                    parts.append(f"{DIM}↳ {txt}{RESET}")
            elif t == "thinking":
                think = item.get("thinking", "")
                if think:
                    parts.append(f"{DIM}{YELLOW}💭 {think}{RESET}")
        return "\n".join(p for p in parts if p)
    return str(content)


def _summarize_tool_input(name: str, inp) -> str:
    if not isinstance(inp, dict):
        return ""
    if name in ("Bash", "bash"):
        cmd = inp.get("cmd") or inp.get("command", "")
        return _one_line(cmd, 120)
    if name in ("Read", "read"):
        return inp.get("path", "")
    if name in ("edit_file", "create_file"):
        return inp.get("path", "")
    if name in ("Grep", "grep"):
        return f"{inp.get('pattern', '')} {inp.get('path', '')}".strip()
    # Generic
    keys = list(inp.keys())[:2]
    return ", ".join(f"{k}={_one_line(str(inp.get(k)), 60)}" for k in keys)


def _one_line(s: str, n: int) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


def format_time(iso_or_epoch) -> str:
    if isinstance(iso_or_epoch, (int, float)):
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(iso_or_epoch))
    if isinstance(iso_or_epoch, str):
        try:
            t = time.strptime(iso_or_epoch[:19], "%Y-%m-%dT%H:%M:%S")
            return time.strftime("%Y-%m-%d %H:%M", t)
        except ValueError:
            return iso_or_epoch
    return ""


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: render-thread.py <session-id> [cwd]", file=sys.stderr)
        return 2
    session_id = sys.argv[1]
    cwd = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()

    path = find_jsonl(session_id, cwd)
    if path is None:
        print(f"{RED}No transcript found for {session_id}{RESET}")
        return 1

    try:
        st = path.stat()
        header = (
            f"{BOLD}{CYAN}thread{RESET} {session_id}\n"
            f"{DIM}{path}{RESET}\n"
            f"{DIM}modified {format_time(st.st_mtime)} • {st.st_size} bytes{RESET}\n"
        )
        print(header)
    except OSError:
        pass

    first_msg = True
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = obj.get("type")
            if t not in ("user", "assistant"):
                continue
            msg = obj.get("message") or {}
            role = msg.get("role") or t
            text = extract_text(msg.get("content"))
            if not text.strip():
                continue
            if not first_msg:
                print()
            first_msg = False
            ts = format_time(obj.get("timestamp", ""))
            if role == "user":
                print(f"{BOLD}{BLUE}▌ user{RESET} {DIM}{ts}{RESET}")
            else:
                print(f"{BOLD}{GREEN}▌ assistant{RESET} {DIM}{ts}{RESET}")
            print(text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
