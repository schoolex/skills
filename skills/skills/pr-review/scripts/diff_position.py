#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


VALID_PREFIXES = {"+", "-", " "}


@dataclass(frozen=True)
class DiffLine:
    path: str
    position: int
    prefix: str
    text: str
    old_line: int | None
    new_line: int | None

    @property
    def side(self) -> str:
        return "LEFT" if self.prefix == "-" else "RIGHT"

    @property
    def line(self) -> int | None:
        return self.old_line if self.prefix == "-" else self.new_line

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "position": self.position,
            "prefix": self.prefix,
            "text": self.text,
            "old_line": self.old_line,
            "new_line": self.new_line,
            "line": self.line,
            "side": self.side,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve stable GitHub PR review locations from a unified diff. "
            "By default the script prints the diff position for backwards compatibility, "
            "but it can also emit line/side metadata and context."
        )
    )
    parser.add_argument(
        "pr",
        nargs="?",
        help="PR number, URL, or branch accepted by gh pr diff",
    )
    parser.add_argument("path", help="Repository-relative file path to inspect")
    parser.add_argument(
        "needle",
        nargs="?",
        help="Line content to match, without the diff prefix",
    )
    parser.add_argument(
        "--needle",
        dest="needle_option",
        help="Line content to match, as an explicit flag",
    )
    parser.add_argument(
        "--repo",
        help="Optional owner/repo for gh commands when outside the repository",
    )
    parser.add_argument(
        "--diff-file",
        help="Read diff text from a file instead of calling gh pr diff (use '-' for stdin)",
    )
    parser.add_argument(
        "--new-line",
        type=int,
        help="Match a line number on the RIGHT side of the diff",
    )
    parser.add_argument(
        "--old-line",
        type=int,
        help="Match a line number on the LEFT side of the diff",
    )
    parser.add_argument(
        "--occurrence",
        type=int,
        default=1,
        help="1-based occurrence among matches after filtering",
    )
    parser.add_argument(
        "--prefix",
        choices=["+", "-", " ", "any"],
        default="any",
        help="Restrict matches to added, removed, context, or any diff line",
    )
    parser.add_argument(
        "--match-mode",
        choices=["exact", "contains", "regex"],
        default="exact",
        help="How to compare the needle against diff lines",
    )
    parser.add_argument(
        "--format",
        choices=["position", "json", "text"],
        default="position",
        help="Output format",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Return every match instead of a single occurrence",
    )
    parser.add_argument(
        "--context",
        type=int,
        default=0,
        help="Show N surrounding diff lines for text/json output",
    )
    return parser.parse_args()


def read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def load_diff(pr: str | None, repo: str | None, diff_file: str | None) -> str:
    if diff_file:
        return read_text(diff_file)
    if not pr:
        raise ValueError("provide a PR target or --diff-file")

    command = ["gh", "pr", "diff", pr, "--patch", "--color", "never"]
    if repo:
        command.extend(["--repo", repo])

    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def normalize_patch_path(value: str) -> str | None:
    token = value.strip()
    if token == "/dev/null":
        return None
    if token.startswith('"') and token.endswith('"') and len(token) >= 2:
        token = token[1:-1].replace(r'\"', '"')
    if token.startswith(("a/", "b/")):
        return token[2:]
    return token


def parse_hunk_header(line: str) -> tuple[int, int]:
    match = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
    if not match:
        raise ValueError(f"unsupported hunk header: {line!r}")
    return int(match.group(1)), int(match.group(2))


def parse_diff(diff_text: str) -> list[DiffLine]:
    entries: list[DiffLine] = []
    current_file: str | None = None
    old_path: str | None = None
    new_path: str | None = None
    old_line_number: int | None = None
    new_line_number: int | None = None
    position = 0
    in_hunk = False

    for raw_line in diff_text.splitlines():
        if raw_line.startswith("diff --git "):
            current_file = None
            old_path = None
            new_path = None
            old_line_number = None
            new_line_number = None
            position = 0
            in_hunk = False
            continue

        if raw_line.startswith("--- "):
            old_path = normalize_patch_path(raw_line[4:])
            current_file = new_path or old_path
            continue

        if raw_line.startswith("+++ "):
            new_path = normalize_patch_path(raw_line[4:])
            current_file = new_path or old_path
            continue

        if raw_line.startswith("@@ "):
            if current_file is None:
                raise ValueError("encountered a hunk before the file path was known")
            old_line_number, new_line_number = parse_hunk_header(raw_line)
            in_hunk = True
            continue

        if not in_hunk or current_file is None:
            continue

        if raw_line.startswith("\\ No newline at end of file"):
            continue

        prefix = raw_line[:1]
        if prefix not in VALID_PREFIXES:
            continue

        position += 1
        old_line = old_line_number if prefix in (" ", "-") else None
        new_line = new_line_number if prefix in (" ", "+") else None
        entries.append(
            DiffLine(
                path=current_file,
                position=position,
                prefix=prefix,
                text=raw_line[1:],
                old_line=old_line,
                new_line=new_line,
            )
        )

        if prefix in (" ", "-"):
            assert old_line_number is not None
            old_line_number += 1
        if prefix in (" ", "+"):
            assert new_line_number is not None
            new_line_number += 1

    return entries


def matches_text(candidate: str, needle: str, match_mode: str) -> bool:
    if match_mode == "exact":
        return candidate == needle
    if match_mode == "contains":
        return needle in candidate
    return re.search(needle, candidate) is not None


def find_matches(
    entries: list[DiffLine],
    *,
    path: str,
    needle: str | None,
    prefix: str,
    match_mode: str,
    new_line: int | None,
    old_line: int | None,
) -> list[DiffLine]:
    filtered = [entry for entry in entries if entry.path == path]
    if prefix != "any":
        filtered = [entry for entry in filtered if entry.prefix == prefix]

    if new_line is not None:
        return [entry for entry in filtered if entry.new_line == new_line]

    if old_line is not None:
        return [entry for entry in filtered if entry.old_line == old_line]

    if needle is None:
        raise ValueError("provide a needle, --new-line, or --old-line")

    return [
        entry
        for entry in filtered
        if matches_text(entry.text, needle, match_mode)
    ]


def format_text_match(match: DiffLine, file_entries: list[DiffLine], context: int) -> str:
    index = file_entries.index(match)
    start = max(0, index - context)
    stop = min(len(file_entries), index + context + 1)
    lines = [
        (
            f"path={match.path} position={match.position} side={match.side} "
            f"line={match.line} prefix={match.prefix!r}"
        )
    ]
    for entry in file_entries[start:stop]:
        marker = ">" if entry == match else " "
        old_display = "-" if entry.old_line is None else str(entry.old_line)
        new_display = "-" if entry.new_line is None else str(entry.new_line)
        lines.append(
            f"{marker} pos={entry.position:>4} old={old_display:>4} new={new_display:>4} "
            f"side={entry.side:<5} prefix={entry.prefix!r} {entry.text}"
        )
    return "\n".join(lines)


def json_match(match: DiffLine, file_entries: list[DiffLine], context: int) -> dict[str, object]:
    payload = match.as_dict()
    if context > 0:
        index = file_entries.index(match)
        start = max(0, index - context)
        stop = min(len(file_entries), index + context + 1)
        payload["context"] = [entry.as_dict() for entry in file_entries[start:stop]]
    return payload


def validate_args(args: argparse.Namespace) -> None:
    if args.occurrence < 1:
        raise ValueError("--occurrence must be >= 1")
    if args.context < 0:
        raise ValueError("--context must be >= 0")
    if args.needle is not None and args.needle_option is not None:
        raise ValueError("use either the positional needle or --needle, not both")
    if args.new_line is not None and args.old_line is not None:
        raise ValueError("use either --new-line or --old-line, not both")
    effective_needle = args.needle_option if args.needle_option is not None else args.needle
    if args.new_line is None and args.old_line is None and effective_needle is None:
        raise ValueError("provide a needle, --new-line, or --old-line")


def main() -> int:
    args = parse_args()

    try:
        validate_args(args)
        needle = args.needle_option if args.needle_option is not None else args.needle
        diff_text = load_diff(args.pr, args.repo, args.diff_file)
        entries = parse_diff(diff_text)
        file_entries = [entry for entry in entries if entry.path == args.path]
        matches = find_matches(
            entries,
            path=args.path,
            needle=needle,
            prefix=args.prefix,
            match_mode=args.match_mode,
            new_line=args.new_line,
            old_line=args.old_line,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else str(exc)
        print(stderr, file=sys.stderr)
        return exc.returncode or 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not matches:
        target = (
            f"new line {args.new_line}"
            if args.new_line is not None
            else f"old line {args.old_line}"
            if args.old_line is not None
            else f"needle {needle!r}"
        )
        print(
            f"No review location found for {args.path!r} using {target}.",
            file=sys.stderr,
        )
        return 1

    selected = matches if args.all else [matches[args.occurrence - 1]] if len(matches) >= args.occurrence else []
    if not selected:
        print(
            f"Only found {len(matches)} match(es) for {args.path!r}; occurrence {args.occurrence} is unavailable.",
            file=sys.stderr,
        )
        return 1

    if args.format == "position":
        for match in selected:
            print(match.position)
        return 0

    if args.format == "json":
        payload = [json_match(match, file_entries, args.context) for match in selected]
        if not args.all:
            payload = payload[0]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    for index, match in enumerate(selected, start=1):
        if index > 1:
            print()
        print(format_text_match(match, file_entries, args.context))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
