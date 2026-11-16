#!/usr/bin/env python3
"""SubagentStop hook: block a sub-agent from finishing while tests fail.

Skips the test-runner agent (its job is to report failures), events with an
empty agent_type (ordinary turns and /btw), and re-entries where
stop_hook_active is true, so a read-only agent is never blocked in a loop.
"""
import json
import os
import subprocess
import sys


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0

    agent_type = payload.get("agent_type") or ""
    if not agent_type or agent_type == "test-runner":
        return 0
    if payload.get("stop_hook_active"):
        return 0

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") \
        or os.getcwd()
    python = sys.executable
    for candidate in (("venv", "bin", "python"),
                      ("venv", "Scripts", "python.exe")):
        path = os.path.join(project_dir, *candidate)
        if os.path.exists(path):
            python = path
            break
    result = subprocess.run(
        [python, "-m", "unittest", "tests"],
        cwd=project_dir, capture_output=True, text=True,
    )
    if result.returncode != 0:
        json.dump({
            "decision": "block",
            "reason": "Tests are failing. Fix them before you finish:\n"
                      + result.stderr[-3000:],
        }, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
