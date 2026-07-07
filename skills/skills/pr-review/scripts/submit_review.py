#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import diff_position
from review_common import (
    DEFAULT_SIGNOFF,
    VALID_EVENTS,
    build_review_payload,
    fetch_pr_head_sha,
    load_comments,
    load_optional_comments,
    read_text,
    submit_replies,
    submit_review_and_replies,
    validate_repo,
    validate_review_anchors,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Submit a consolidated GitHub PR review from files. Supports stable line/side "
            "comments, diff-position comments, file-level comments, and threaded replies."
        )
    )
    parser.add_argument("--repo", required=True, help="owner/repo")
    parser.add_argument("--pr", required=True, help="Pull request number or URL accepted by gh")
    parser.add_argument(
        "--event",
        default="COMMENT",
        choices=sorted(VALID_EVENTS),
        help="Review event",
    )
    parser.add_argument("--body-file", help="Path to the overall review body")
    parser.add_argument(
        "--comments-file",
        help=(
            "Path to a JSON array of review comments or replies. Review comments may use "
            "{path, line, side, body}, {path, position, body}, or {path, subject_type, body}. "
            "Replies use {in_reply_to, body}. Defaults to an empty array."
        ),
    )
    parser.add_argument(
        "--diff-file",
        help="Read diff text from a file for --validate instead of calling gh pr diff",
    )
    parser.add_argument(
        "--commit-id",
        help="Explicit head commit SHA for the review payload",
    )
    parser.add_argument(
        "--no-auto-commit-id",
        action="store_true",
        help="Do not fetch the PR head SHA automatically before submission",
    )
    parser.add_argument(
        "--signoff",
        default=DEFAULT_SIGNOFF,
        help="Sign-off appended to the body and comments if missing",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the normalized payload and reply plan instead of submitting",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate review comment anchors against the current PR diff before submitting",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate review comment anchors and exit without submitting",
    )
    parser.add_argument(
        "--replies-only",
        action="store_true",
        help="Post only threaded replies from --comments-file without creating a review",
    )
    return parser.parse_args()


def validate_mode_args(args: argparse.Namespace) -> None:
    if args.replies_only and not args.comments_file:
        raise ValueError("--replies-only requires --comments-file with at least one reply")
    if not args.replies_only and not args.body_file:
        raise ValueError("--body-file is required unless --replies-only is used")
    if args.validate_only:
        args.validate = True


def main() -> int:
    args = parse_args()

    try:
        validate_repo(args.repo)
        validate_mode_args(args)
        review_comments, reply_comments = load_optional_comments(args.comments_file, args.signoff)
        if args.replies_only:
            if review_comments:
                raise ValueError("--replies-only comments file must contain only {in_reply_to, body} replies")
            if not reply_comments:
                raise ValueError("--replies-only requires at least one reply")

        if args.validate:
            diff_text = diff_position.load_diff(args.pr, args.repo, args.diff_file)
            validate_review_anchors(review_comments, diff_position.parse_diff(diff_text))

        body_text = "" if args.replies_only else read_text(args.body_file)
        commit_id = args.commit_id
        should_submit_review = not args.dry_run and not args.validate_only and not args.replies_only
        if not commit_id and not args.no_auto_commit_id and should_submit_review:
            commit_id = fetch_pr_head_sha(args.repo, args.pr)

        payload = build_review_payload(
            body_text=body_text,
            event=args.event,
            review_comments=review_comments,
            signoff=args.signoff,
            commit_id=commit_id,
        )
    except (ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else str(exc)
        print(stderr, file=sys.stderr)
        return exc.returncode or 1

    plan = {
        "review": payload,
        "replies": reply_comments,
    }
    if args.validate_only:
        print(json.dumps({"valid": True, **plan}, indent=2, ensure_ascii=False))
        return 0
    if args.dry_run:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return 0

    try:
        if args.replies_only:
            submit_replies(
                repo=args.repo,
                pr=args.pr,
                reply_comments=reply_comments,
            )
            print(f"Posted {len(reply_comments)} threaded repl{'y' if len(reply_comments) == 1 else 'ies'} to {args.repo}#{args.pr}.")
            return 0
        review_response = submit_review_and_replies(
            repo=args.repo,
            pr=args.pr,
            review_payload=payload,
            reply_comments=reply_comments,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else str(exc)
        print(stderr, file=sys.stderr)
        return exc.returncode or 1

    review_id = review_response.get("id")
    review_url = review_response.get("html_url") or review_response.get("pull_request_url")
    summary = f"Submitted review to {args.repo}#{args.pr}"
    if review_id:
        summary += f" (id={review_id})"
    print(summary)
    if review_url:
        print(review_url)
    if reply_comments:
        print(f"Posted {len(reply_comments)} threaded repl{'y' if len(reply_comments) == 1 else 'ies'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
