#!/usr/bin/env python3
"""
List Claude Code threads for a given working directory, sorted by mtime desc.

Output: TSV lines of <session-id>\t<mtime-epoch>\t<relative-time>\t<title>

The Claude project dir is derived from the cwd by replacing every '/' with '-'.
e.g. /Users/justin/dev/clamp -> -Users-justin-dev-clamp
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"


def project_dir_for_cwd(cwd: str) -> Path:
    encoded = cwd.replace("/", "-")
    return CLAUDE_PROJECTS / encoded


def first_user_message(jsonl_path: Path) -> str:
    """Find the first user-typed message and return a one-line title."""
    try:
        with jsonl_path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") != "user":
                    continue
                msg = obj.get("message") or {}
                if msg.get("role") != "user":
                    continue
                content = msg.get("content")
                text = _extract_text(content)
                if not text:
                    continue
                # Skip tool_result and meta-ish messages
                if text.startswith("<command-") or text.startswith("[Request interrupted"):
                    continue
                return _flatten(text)[:200]
    except OSError:
        pass
    return "(no user message)"


def _extract_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif item.get("type") == "tool_result":
                    # skip tool results in title
                    continue
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(content)


def _flatten(s: str) -> str:
    return " ".join(s.split())


def relative_time(epoch: float) -> str:
    delta = max(0, int(time.time() - epoch))
    if delta < 60:
        return f"{delta}s ago"
    if delta < 3600:
        return f"{delta // 60}m ago"
    if delta < 86400:
        return f"{delta // 3600}h ago"
    if delta < 86400 * 30:
        return f"{delta // 86400}d ago"
    if delta < 86400 * 365:
        return f"{delta // (86400 * 30)}mo ago"
    return f"{delta // (86400 * 365)}y ago"


def main() -> int:
    cwd = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    pdir = project_dir_for_cwd(cwd)
    if not pdir.is_dir():
        return 0

    files = []
    for p in pdir.iterdir():
        if p.is_file() and p.suffix == ".jsonl":
            try:
                files.append((p, p.stat().st_mtime))
            except OSError:
                continue

    files.sort(key=lambda t: t[1], reverse=True)

    for path, mtime in files:
        sid = path.stem
        title = first_user_message(path)
        rel = relative_time(mtime)
        # TAB-separated, no embedded tabs in title
        title = title.replace("\t", " ")
        print(f"{sid}\t{int(mtime)}\t{rel}\t{title}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
