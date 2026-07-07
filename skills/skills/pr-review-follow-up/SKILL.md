---
name: pr-review-follow-up
description: Give a follow-up review on a pull request after the author has responded or pushed updates. Use when revisiting earlier findings, closing review threads, or deciding whether the PR is now ready to approve.
---

Use this skill after an earlier review already happened and the author has replied or pushed follow-up commits.

## Goal

Verify what is still outstanding, avoid repeating closed points, and approve when the PR is ready.

## Workflow

1. Read `../pr-review/REFERENCE.md`, then read prior reviews, inline threads, issue comments, and the latest diff before replying.
2. Separate findings into: fixed, intentionally deferred, and still blocking this PR.
3. Prefer replying in the existing thread with `in_reply_to` when acknowledging resolution or scope changes.
4. If the author said an issue will be tracked separately, and that split is reasonable, treat that thread as non-blocking and move on.
5. Only leave fresh comments for issues that still need action in this PR.
6. For each thread that is confirmed fixed, resolve it individually via GraphQL — but **only resolve threads you opened**. Determine your own login from the Bot Identity source in `../pr-review/REFERENCE.md` (it resolves to `schoolex` by default), then resolve a thread only when its first comment's author matches that login. Never resolve threads opened by other reviewers.
   ```sh
   gh api graphql -f query='mutation { resolveReviewThread(input: {threadId: "THREAD_ID"}) { thread { isResolved } } }'
   ```
   Thread IDs come from `review_threads.py --format json` (the `id` field; check `comments.nodes[0].author.login` to confirm ownership). Resolve threads as you triage them — do not batch all resolutions to the end.
7. If no other blocking issues remain, submit an `APPROVE` review.

## Output Rules

- Be polite and empathetic. Acknowledge the author's effort when closing out findings or approving.
- Keep the follow-up body short and explicit about the remaining status.
- Do not restate resolved concerns as open findings.
- Append the required bot signature to every review body and comment.
- Use `COMMENT` if discussion is still open; use `APPROVE` when the PR is ready.

## Tools

The shared commands, helper scripts, comment JSON shapes, formatting rules, and validation commands live in `../pr-review/REFERENCE.md`. Read it before submitting a follow-up. Beyond those, this mode relies on `review_threads.py --format json` for thread state and ownership, and the `resolveReviewThread` GraphQL mutation above.

If the PR touches React/MUI frontend code (`.tsx` components, `sx` props, `styled()` calls, inline `style` props), also read `../pr-review/FRONTEND.md` and check whether any hardcoded magic value findings from the initial review are resolved or still open.
