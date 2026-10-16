---
name: pr-review-follow-up
description: Give a follow-up review on a pull request after the author has responded or pushed updates. Use when revisiting earlier findings, closing review threads, checking "is it approved / what's blocking", or deciding whether the PR is now ready to approve.
---

Use this skill after an earlier review, when the author has replied or pushed follow-up commits.

Read `~/.config/opencode/skills/skills/pr-review/REFERENCE.md` first, in particular the Posting Gate, Anchoring and Project Facts sections. Scripts:

```sh
PRR=~/.config/opencode/skills/skills/pr-review/scripts
```

Use that path verbatim. Our login is `${PR_REVIEW_BOT_LOGIN:-schoolex}`. Don't probe for it with Python.

## Goal

Work out what is still outstanding, don't repeat points that are already closed, and approve when the PR is ready.

## Workflow

1. Gather state in one batch:
   ```sh
   N=<pr>; REPO=<owner/repo>
   gh pr view $N --repo $REPO --json number,title,author,headRefOid,reviews,commits,url,state,reviewDecision
   python3 $PRR/review_threads.py --repo $REPO --pr $N --format json > /tmp/threads-$N.json
   gh pr diff $N --repo $REPO --patch > /tmp/pr-$N.patch
   ```
   `review_threads.py --format json` writes pure JSON to stdout. Load it with `json.load(open(...))`, and never slice it at `[`.
   Find the commits added since our last review: compare the `submittedAt` of our latest review with the commit dates. Focus on what those commits change.
2. Sort every thread we opened into one of three groups:
   - **fixed**
   - **deferred**: the author will track it separately and that split is reasonable, so it's non-blocking
   - **still open**

   Threads opened by other reviewers are out of scope. You may mention them, but never resolve them.
3. Show the user a short status table in chat (thread, status, one-line evidence) with a recommendation: `Recommend: APPROVE` if nothing blocking is left, otherwise `Recommend: COMMENT`. Then follow the Posting Gate. If the request was pre-approved ("approve if non-blocking", "just approve"), carry on without waiting.
4. Once the user has decided, act in this order:
   - Resolve each **fixed** thread that we opened (the first comment's author equals our login):
     ```sh
     gh api graphql -f query='mutation { resolveReviewThread(input: {threadId: "THREAD_ID"}) { thread { isResolved } } }'
     ```
     If the user says "let the reviewer resolve them", skip this step.
   - Post the thread replies the user asked for in one call, with no new review:
     ```sh
     python3 $PRR/submit_review.py --repo $REPO --pr $N --replies-only --comments-file /tmp/replies-$N.json
     # [{"in_reply_to": <databaseId of the thread's first comment>, "body": "..."}]
     ```
   - Submit **one** review at most: `--event APPROVE` (with any new comments the user approved) or `--event COMMENT`. Never submit a review only to say "acknowledged". Thread replies cover that.
5. When nothing is left to post (the user is the author, or `internal` was requested), stop after the status table.

## Output Rules

- Be polite. Acknowledge the author's work when closing findings.
- Don't present resolved concerns as open findings.
- Keep the body short and state the remaining status explicitly.
- Only raise new comments for issues that still need action in this PR.
- If the PR touches React/MUI, check whether any hard-coded magic-value findings are still open, using `../pr-review/FRONTEND.md`.
