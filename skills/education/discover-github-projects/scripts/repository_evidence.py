#!/usr/bin/env python3
"""Produce a bounded, read-only evidence manifest from a Git checkout."""

import argparse
import json
import subprocess
from pathlib import Path


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", type=Path)
    parser.add_argument("--max-files", type=int, default=400)
    args = parser.parse_args()
    root = args.repository.resolve()
    files = git(root, "ls-files").splitlines()
    interesting = tuple(
        name
        for name in files
        if Path(name).name.lower()
        in {
            "readme.md",
            "security.md",
            "docker-compose.yml",
            "compose.yml",
            "dockerfile",
            "cargo.toml",
            "package.json",
            "pyproject.toml",
            "go.mod",
        }
        or name.startswith(("docs/", ".github/workflows/"))
    )
    payload = {
        "revision": git(root, "rev-parse", "HEAD"),
        "remote": git(root, "remote", "get-url", "origin"),
        "tracked_files": len(files),
        "files_truncated": len(files) > args.max_files,
        "structure": files[: args.max_files],
        "evidence_candidates": interesting[:100],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
