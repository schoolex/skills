from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath


# Single source of truth for reviewer identity. Override per-environment with
# PR_REVIEW_BOT_LOGIN (the GitHub login) or PR_REVIEW_SIGNOFF (the full string).
# The literal fallback below is the only place the default login should appear.
DEFAULT_BOT_LOGIN = os.environ.get("PR_REVIEW_BOT_LOGIN", "schoolex")
DEFAULT_SIGNOFF = os.environ.get("PR_REVIEW_SIGNOFF") or f"[Reviewed by {DEFAULT_BOT_LOGIN}'s bot]"
VALID_EVENTS = {"COMMENT", "APPROVE"}
VALID_SIDES = {"LEFT", "RIGHT"}
VALID_SUBJECT_TYPES = {"file", "line"}
SUGGESTION_FENCE = "```suggestion"


def read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def with_signoff(text: str, signoff: str) -> str:
    stripped = text.rstrip()
    if not signoff:
        return stripped
    if stripped.endswith(signoff):
        return stripped
    if not stripped:
        return signoff
    return f"{stripped}\n\n{signoff}"


def normalize_path(raw_path: object) -> str:
    path = PurePosixPath(str(raw_path))
    if path.is_absolute():
        raise ValueError("comment paths must be repository-relative")
    if any(part == ".." for part in path.parts):
        raise ValueError("comment paths must not traverse parent directories")
    normalized = path.as_posix()
    if normalized in {"", "."}:
        raise ValueError("comment path must not be empty")
    return normalized


def positive_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"{field_name} must be an integer")
    parsed = int(value)
    if parsed < 1:
        raise ValueError(f"{field_name} must be >= 1")
    return parsed


def normalize_side(value: object, field_name: str) -> str:
    side = str(value).upper()
    if side not in VALID_SIDES:
        raise ValueError(f"{field_name} must be one of {sorted(VALID_SIDES)}")
    return side


def contains_suggestion(body: str) -> bool:
    return SUGGESTION_FENCE in body


def normalize_review_comment(comment: dict, signoff: str, index: int) -> dict[str, object]:
    allowed = {
        "body",
        "line",
        "path",
        "position",
        "side",
        "start_line",
        "start_side",
        "subject_type",
    }
    unknown = set(comment) - allowed
    if unknown:
        raise ValueError(f"comment #{index} has unsupported keys: {sorted(unknown)}")

    if "body" not in comment or "path" not in comment:
        raise ValueError(f"comment #{index} must include 'path' and 'body'")

    body = with_signoff(str(comment["body"]), signoff)
    path = normalize_path(comment["path"])
    subject_type = str(comment.get("subject_type", "line")).lower()
    if subject_type not in VALID_SUBJECT_TYPES:
        raise ValueError(
            f"comment #{index} subject_type must be one of {sorted(VALID_SUBJECT_TYPES)}"
        )

    has_position = "position" in comment
    has_line = "line" in comment or "side" in comment or "start_line" in comment or "start_side" in comment
    is_file_comment = subject_type == "file"

    modes = sum((has_position, has_line, is_file_comment))
    if modes != 1:
        raise ValueError(
            f"comment #{index} must use exactly one location mode: position, line/side, or subject_type=file"
        )

    normalized: dict[str, object] = {
        "path": path,
        "body": body,
    }

    if has_position:
        normalized["position"] = positive_int(comment["position"], f"comment #{index} position")
        if contains_suggestion(body):
            raise ValueError(
                f"comment #{index} uses a suggestion block; use line/side instead of diff position for stable suggestions"
            )
        return normalized

    if is_file_comment:
        normalized["subject_type"] = "file"
        if contains_suggestion(body):
            raise ValueError(
                f"comment #{index} uses a suggestion block; suggestions must target a concrete RIGHT-side line"
            )
        return normalized

    if "line" not in comment or "side" not in comment:
        raise ValueError(f"comment #{index} line comments must include 'line' and 'side'")

    line = positive_int(comment["line"], f"comment #{index} line")
    side = normalize_side(comment["side"], f"comment #{index} side")
    normalized["line"] = line
    normalized["side"] = side

    has_start_line = "start_line" in comment
    has_start_side = "start_side" in comment
    if has_start_line != has_start_side:
        raise ValueError(
            f"comment #{index} multi-line comments must include both 'start_line' and 'start_side'"
        )
    if has_start_line:
        start_line = positive_int(comment["start_line"], f"comment #{index} start_line")
        start_side = normalize_side(comment["start_side"], f"comment #{index} start_side")
        normalized["start_line"] = start_line
        normalized["start_side"] = start_side
        if start_line > line:
            raise ValueError(f"comment #{index} start_line must be <= line")

    if contains_suggestion(body):
        if side != "RIGHT":
            raise ValueError(
                f"comment #{index} uses a suggestion block on the LEFT side; suggestions must target the RIGHT side"
            )
        if has_start_side and normalized.get("start_side", "RIGHT") != "RIGHT":
            raise ValueError(
                f"comment #{index} uses a suggestion block with a LEFT-side range; suggestions must target the RIGHT side"
            )

    return normalized


def normalize_reply(comment: dict, signoff: str, index: int) -> dict[str, object]:
    allowed = {"body", "in_reply_to"}
    unknown = set(comment) - allowed
    if unknown:
        raise ValueError(f"reply #{index} has unsupported keys: {sorted(unknown)}")
    if "body" not in comment:
        raise ValueError(f"reply #{index} missing key: 'body'")
    return {
        "in_reply_to": positive_int(comment["in_reply_to"], f"reply #{index} in_reply_to"),
        "body": with_signoff(str(comment["body"]), signoff),
    }


def review_comment_sort_key(comment: dict[str, object]) -> tuple[object, ...]:
    if "line" in comment:
        return (
            comment["path"],
            0,
            comment.get("start_line", comment["line"]),
            comment["line"],
            comment["side"],
        )
    if "position" in comment:
        return (comment["path"], 1, comment["position"], comment["position"], "")
    return (comment["path"], 2, 0, 0, "")


def load_comments(path: str, signoff: str) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    comments = json.loads(read_text(path))
    if not isinstance(comments, list):
        raise ValueError("comments file must contain a JSON array")

    review_comments: list[dict[str, object]] = []
    reply_comments: list[dict[str, object]] = []

    for index, comment in enumerate(comments, start=1):
        if not isinstance(comment, dict):
            raise ValueError(f"comment #{index} must be an object")
        if "in_reply_to" in comment:
            reply_comments.append(normalize_reply(comment, signoff, index))
        else:
            review_comments.append(normalize_review_comment(comment, signoff, index))

    review_comments.sort(key=review_comment_sort_key)
    return review_comments, reply_comments


def load_optional_comments(
    path: str | None,
    signoff: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if not path:
        return [], []
    return load_comments(path, signoff)


def validate_review_anchors(review_comments: list[dict[str, object]], diff_entries: list[object]) -> None:
    by_path: dict[str, list[object]] = {}
    for entry in diff_entries:
        by_path.setdefault(str(getattr(entry, "path")), []).append(entry)

    changed_paths = set(by_path)
    for index, comment in enumerate(review_comments, start=1):
        path = str(comment["path"])
        file_entries = by_path.get(path, [])
        if not file_entries:
            raise ValueError(f"comment #{index} targets {path!r}, which is not present in the PR diff")

        if comment.get("subject_type") == "file":
            continue

        if "position" in comment:
            position = comment["position"]
            if not any(getattr(entry, "position") == position for entry in file_entries):
                raise ValueError(
                    f"comment #{index} targets position {position} in {path!r}, "
                    "but that position is not present in the PR diff"
                )
            continue

        line = comment["line"]
        side = comment["side"]
        if not any(getattr(entry, "line") == line and getattr(entry, "side") == side for entry in file_entries):
            raise ValueError(
                f"comment #{index} targets {path!r} line {line} side {side}, "
                "but that anchor is not present in the PR diff"
            )

        if "start_line" in comment:
            start_line = comment["start_line"]
            start_side = comment["start_side"]
            if not any(
                getattr(entry, "line") == start_line and getattr(entry, "side") == start_side
                for entry in file_entries
            ):
                raise ValueError(
                    f"comment #{index} targets start {path!r} line {start_line} side {start_side}, "
                    "but that anchor is not present in the PR diff"
                )

    if review_comments and not changed_paths:
        raise ValueError("PR diff has no changed paths to validate against")


def build_review_payload(
    body_text: str,
    event: str,
    review_comments: list[dict[str, object]],
    signoff: str,
    commit_id: str | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "body": with_signoff(body_text, signoff),
        "event": event,
        "comments": review_comments,
    }
    if commit_id:
        payload["commit_id"] = commit_id
    return payload


def validate_repo(repo: str) -> None:
    owner, separator, name = repo.partition("/")
    if not separator or not owner or not name or "/" in name:
        raise ValueError("--repo must use the form owner/repo")


def fetch_pr_head_sha(repo: str, pr: str) -> str:
    result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            pr,
            "--repo",
            repo,
            "--json",
            "headRefOid",
            "--jq",
            ".headRefOid",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    sha = result.stdout.strip()
    if not sha:
        raise ValueError(f"unable to resolve head SHA for {repo}#{pr}")
    return sha


def write_json_file(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def run_gh_api_input(endpoint: str, input_path: Path) -> dict[str, object]:
    result = subprocess.run(
        ["gh", "api", "-X", "POST", endpoint, "--input", str(input_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    stdout = result.stdout.strip()
    return json.loads(stdout) if stdout else {}


def submit_review_and_replies(
    repo: str,
    pr: str,
    review_payload: dict[str, object],
    reply_comments: list[dict[str, object]],
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="pr-review-") as temp_dir:
        temp_root = Path(temp_dir)
        review_path = temp_root / "review.json"
        write_json_file(review_path, review_payload)
        review_response = run_gh_api_input(
            f"repos/{repo}/pulls/{pr}/reviews",
            review_path,
        )

        for index, reply in enumerate(reply_comments, start=1):
            reply_path = temp_root / f"reply-{index}.json"
            write_json_file(reply_path, {"body": reply["body"]})
            run_gh_api_input(
                f"repos/{repo}/pulls/{pr}/comments/{reply['in_reply_to']}/replies",
                reply_path,
            )

    return review_response


def submit_replies(
    repo: str,
    pr: str,
    reply_comments: list[dict[str, object]],
) -> None:
    with tempfile.TemporaryDirectory(prefix="pr-review-") as temp_dir:
        temp_root = Path(temp_dir)
        for index, reply in enumerate(reply_comments, start=1):
            reply_path = temp_root / f"reply-{index}.json"
            write_json_file(reply_path, {"body": reply["body"]})
            run_gh_api_input(
                f"repos/{repo}/pulls/{pr}/comments/{reply['in_reply_to']}/replies",
                reply_path,
            )
