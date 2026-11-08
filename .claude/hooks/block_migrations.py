#!/usr/bin/env python3
"""PreToolUse hook: block Edit and Write on files under migrations/.

Reads the hook payload from stdin. If the target file is inside
<project>/migrations/, prints a "deny" decision; otherwise prints nothing.
"""
import json
import os
import sys

MESSAGE = "migrations/ is frozen; ask the user before changing a migration."


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0

    file_path = (payload.get("tool_input") or {}).get("file_path")
    if not file_path:
        return 0

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") \
        or os.getcwd()
    migrations = os.path.realpath(os.path.join(project_dir, "migrations"))
    target = os.path.realpath(os.path.join(project_dir, file_path))

    if os.path.commonpath([migrations, target]) == migrations:
        json.dump({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": MESSAGE,
            }
        }, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
