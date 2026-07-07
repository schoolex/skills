#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys


QUERY = """
query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          startLine
          comments(first: 100) {
            nodes {
              databaseId
              author { login }
              body
              createdAt
              updatedAt
              url
              path
              line
              diffHunk
              pullRequestReview {
                state
                submittedAt
                author { login }
              }
            }
          }
        }
      }
    }
  }
}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch GitHub PR review threads, including resolved and outdated state."
    )
    parser.add_argument("--repo", required=True, help="owner/repo")
    parser.add_argument("--pr", required=True, type=int, help="Pull request number")
    parser.add_argument(
        "--format",
        choices=["summary", "json"],
        default="summary",
        help="Output raw thread JSON or a compact summary",
    )
    return parser.parse_args()


def parse_repo(repo: str) -> tuple[str, str]:
    owner, separator, name = repo.partition("/")
    if not separator or not owner or not name or "/" in name:
        raise ValueError("--repo must use the form owner/repo")
    return owner, name


def fetch_page(owner: str, name: str, number: int, cursor: str | None) -> dict[str, object]:
    command = [
        "gh",
        "api",
        "graphql",
        "-f",
        f"query={QUERY}",
        "-F",
        f"owner={owner}",
        "-F",
        f"name={name}",
        "-F",
        f"number={number}",
    ]
    if cursor:
        command.extend(["-f", f"cursor={cursor}"])

    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def fetch_threads(repo: str, pr: int) -> list[dict[str, object]]:
    owner, name = parse_repo(repo)
    threads: list[dict[str, object]] = []
    cursor: str | None = None

    while True:
        page = fetch_page(owner, name, pr, cursor)
        pull_request = page["data"]["repository"]["pullRequest"]
        review_threads = pull_request["reviewThreads"]
        threads.extend(review_threads["nodes"])
        page_info = review_threads["pageInfo"]
        if not page_info["hasNextPage"]:
            return threads
        cursor = page_info["endCursor"]


def print_summary(threads: list[dict[str, object]]) -> None:
    for index, thread in enumerate(threads, start=1):
        comments = thread.get("comments", {}).get("nodes", [])
        first_comment = comments[0] if comments else {}
        last_comment = comments[-1] if comments else {}
        first_author = first_comment.get("author") or {}
        last_author = last_comment.get("author") or {}
        status = []
        status.append("resolved" if thread.get("isResolved") else "unresolved")
        if thread.get("isOutdated"):
            status.append("outdated")
        print(
            f"{index}. {', '.join(status)} "
            f"path={thread.get('path')} line={thread.get('line')} "
            f"comments={len(comments)} first={first_author.get('login')} last={last_author.get('login')}"
        )
        if last_comment.get("url"):
            print(f"   {last_comment['url']}")


def main() -> int:
    args = parse_args()
    try:
        threads = fetch_threads(args.repo, args.pr)
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else str(exc)
        print(stderr, file=sys.stderr)
        return exc.returncode or 1

    if args.format == "json":
        print(json.dumps(threads, indent=2, ensure_ascii=False))
    else:
        print_summary(threads)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
