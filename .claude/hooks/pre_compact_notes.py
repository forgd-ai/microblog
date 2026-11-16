#!/usr/bin/env python3
"""PreCompact hook: save working state to NOTES.md before compaction.

Appends git diff --stat, the open questions or decisions in spec.md, and the
steps in plan.md, copied as they are. Files that don't exist yet are skipped,
and spec.md and plan.md are never changed.
"""
import datetime
import json
import os
import re
import subprocess
import sys


def section(text, pattern):
    """Return the markdown section whose heading matches pattern, or ''."""
    match = re.search(r"^(#+)\s*.*(" + pattern + r").*$", text,
                      re.IGNORECASE | re.MULTILINE)
    if not match:
        return ""
    level = len(match.group(1))
    rest = text[match.end():]
    end = re.search(r"^#{1,%d}\s" % level, rest, re.MULTILINE)
    return (match.group(0) + rest[:end.start() if end else len(rest)]).strip()


def read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ""


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        payload = {}
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") \
        or os.getcwd()

    diff = subprocess.run(["git", "diff", "--stat"], cwd=project_dir,
                          capture_output=True, text=True).stdout.strip()
    spec = section(read(os.path.join(project_dir, "spec.md")),
                   "open question|decision")
    plan = read(os.path.join(project_dir, "plan.md")).strip()

    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    parts = ["\n## Before compaction, " + stamp,
             "### git diff --stat\n\n```\n" + (diff or "(no changes)") + "\n```"]
    if spec:
        parts.append("### From spec.md\n\n" + spec)
    if plan:
        parts.append("### From plan.md\n\n" + plan)
    with open(os.path.join(project_dir, "NOTES.md"), "a") as f:
        f.write("\n\n".join(parts) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
