#!/usr/bin/env python3
"""Report active Spec Kit task state; checkbox state is not a semantic verdict."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def count_tasks(text):
    tasks = {}
    fence = None
    for line in text.splitlines():
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if marker:
            token, suffix = marker.groups()
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and not suffix.strip():
                fence = None
            continue
        if fence is not None:
            continue
        task = re.match(r"^\s*- \[([ xX])\] (T\d{3,})\s+\S", line)
        if task:
            checked, task_id = task.groups()
            if task_id in tasks:
                raise ValueError(f"Duplicate task ID: {task_id}")
            tasks[task_id] = checked.lower() == "x"
        elif re.match(r"^\s*-\s+\[", line):
            raise ValueError("Malformed task entry")
    if fence is not None:
        raise ValueError("Unclosed code fence in tasks.md")
    if not tasks:
        raise ValueError("No tasks in tasks.md")
    return len(tasks), sum(not checked for checked in tasks.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    try:
        result = subprocess.run(
            ["bash", ".specify/scripts/bash/check-prerequisites.sh", "--json",
             "--require-spec", "--require-tasks", "--include-tasks"],
            cwd=ROOT, text=True, capture_output=True, check=True,
        )
        feature = Path(json.loads(result.stdout)["FEATURE_DIR"])
        total, remaining = count_tasks((feature / "tasks.md").read_text(encoding="utf-8"))
    except subprocess.CalledProcessError as error:
        print(error.stderr.strip() or "Spec Kit prerequisite check failed", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError) as error:
        print(f"Cannot determine task state: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"total": total, "remaining": remaining}))
    return int(args.require_complete and remaining > 0)


if __name__ == "__main__":
    sys.exit(main())
