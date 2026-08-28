#!/usr/bin/env python3
"""Inspect Git repository state using only read-only Git commands."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )


def inspect(root: Path) -> tuple[dict, int]:
    try:
        probe = git(root, "rev-parse", "--is-inside-work-tree")
    except FileNotFoundError:
        return {"schema_version": 1, "root": str(root), "is_git_repository": False, "errors": ["git executable not found"]}, 1
    is_repo = probe.returncode == 0 and probe.stdout.strip() == "true"
    if not is_repo:
        detail = probe.stderr.strip() or "not a Git working tree"
        return {"schema_version": 1, "root": str(root), "is_git_repository": False, "errors": [detail]}, 0

    top = git(root, "rev-parse", "--show-toplevel")
    branch = git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    status = git(root, "status", "--porcelain=v1", "--untracked-files=all")
    commit = git(root, "log", "-1", "--date=iso-strict", "--format=%H%x1f%h%x1f%an%x1f%ae%x1f%ad%x1f%s")
    remotes = git(root, "remote", "-v")
    errors = []
    for label, result in (("top-level", top), ("status", status), ("recent commit", commit), ("remotes", remotes)):
        if result.returncode != 0:
            errors.append(f"{label}: {result.stderr.strip() or 'command failed'}")

    changes = []
    if status.returncode == 0:
        for line in status.stdout.splitlines():
            if len(line) < 3:
                continue
            changes.append({"index": line[0], "worktree": line[1], "path": line[3:]})

    recent_commit = None
    if commit.returncode == 0 and commit.stdout.strip():
        parts = commit.stdout.strip().split("\x1f", 5)
        if len(parts) == 6:
            recent_commit = dict(zip(("hash", "short_hash", "author_name", "author_email", "date", "subject"), parts))

    remote_entries = []
    if remotes.returncode == 0:
        for line in remotes.stdout.splitlines():
            fields = line.split()
            if len(fields) >= 3:
                # Do not emit URLs: authenticated remotes may contain embedded credentials.
                remote_entries.append({"name": fields[0], "direction": fields[2].strip("()")})

    detached = branch.returncode != 0
    return {
        "schema_version": 1,
        "root": str(root),
        "repository_root": top.stdout.strip() if top.returncode == 0 else None,
        "is_git_repository": True,
        "branch": None if detached else branch.stdout.strip(),
        "detached_head": detached,
        "working_tree_clean": status.returncode == 0 and not changes,
        "uncommitted_files": changes,
        "recent_commit": recent_commit,
        "remote_present": bool(remote_entries),
        "remotes": remote_entries,
        "errors": errors,
    }, 0 if not errors else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=".", help="repository path (default: current directory)")
    args = parser.parse_args()
    root = Path(args.path).expanduser().resolve()
    if not root.is_dir():
        print(json.dumps({"schema_version": 1, "root": str(root), "is_git_repository": False, "errors": ["path is not a directory"]}, indent=2))
        return 2
    result, code = inspect(root)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
