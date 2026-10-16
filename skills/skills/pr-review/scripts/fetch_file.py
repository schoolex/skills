#!/usr/bin/env python3
"""Print a file's raw content at a given ref via the GitHub API.

Avoids the zsh `no matches found` failure that unquoted `contents/...?ref=` URLs hit.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from urllib.parse import quote


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="owner/repo")
    parser.add_argument("--ref", required=True, help="commit SHA, branch, or tag (e.g. PR headRefOid)")
    parser.add_argument("paths", nargs="+", help="repository-relative file paths")
    args = parser.parse_args()

    status = 0
    for i, path in enumerate(args.paths):
        if len(args.paths) > 1:
            print(f"{'' if i == 0 else chr(10)}===== {path} =====")
        endpoint = f"repos/{args.repo}/contents/{quote(path)}?ref={quote(args.ref)}"
        result = subprocess.run(
            ["gh", "api", endpoint, "-H", "Accept: application/vnd.github.raw+json"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"error fetching {path}: {result.stderr.strip()}", file=sys.stderr)
            status = 1
            continue
        sys.stdout.write(result.stdout)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
