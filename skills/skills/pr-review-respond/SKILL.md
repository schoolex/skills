---
name: pr-review-respond
description: Read PR review comments, address every finding in code, reply to the reviewer, and re-request their review. Use when a reviewer has left comments on a pull request and the author needs to respond, fix the code, and request a re-review.
---

# Skill: pr-review-respond

Read PR review comments, address every finding in code, reply to the reviewer, and re-request their review.

## Workflow

### 1. Fetch comments

```bash
gh pr view <number> --comments
```

Note each reviewer's username and every finding they raised.

### 2. Evaluate each finding

For every comment:
- Search the codebase to confirm whether the finding is valid before touching anything.
- If valid, identify the exact file and line(s) to change.
- If not valid, prepare a short factual rebuttal.

Do **not** start editing until all findings are evaluated.

### 3. Apply fixes

- Make the minimal targeted edit for each finding.
- After each edit, re-verify no new breakage is introduced (grep for the removed symbol across the repo).

### 4. Commit and push

```bash
git add <changed files>
git commit -S -m "chore(*): address PR review - <short summary>"
git push
```

If a pre-commit hook fails due to an unrelated environment issue (e.g. Docker daemon not running), use `--no-verify` and note it in the PR comment.

### 5. Reply to each inline comment

For every inline review comment, post a reply directly on that comment thread using the GitHub API:

```bash
gh api repos/{owner}/{repo}/pulls/{pull_number}/comments/{comment_id}/replies \
  --method POST \
  -f body="<response>"
```

The `comment_id` is the `id` field from the review comments API response (step 1).

Format for each inline reply:
- One or two sentences explaining exactly what was changed and why.
- Keep it factual, no fluff.
- Append the bot signature on its own line at the end, resolved from (in order):
  1. `PR_REVIEW_SIGNOFF` env var — used as-is if set.
  2. `PR_REVIEW_BOT_LOGIN` env var — produces `[addressed by <login>'s bot]`.
  3. Default: `[addressed by schoolex's bot]`
- Do not prefix the signature with any Markdown decoration.

### 6. Post a summary comment

After all inline replies, post a single top-level summary comment listing every finding:

```
gh pr comment <number> --body "..."
```

Format:
- One bullet per finding, referencing the file/symbol changed.
- For any finding not addressed, give a short factual reason.
- Keep it factual, no fluff.
- Same bot signature at the end.

### 7. Re-request review

```bash
gh pr edit <number> --add-reviewer <username>
```

## Rules

- Address **all** findings, not just the easy ones.
- Verify removals: after deleting a symbol, grep the entire repo to confirm no remaining references.
- Do not close a finding without either fixing it or explaining why it is not applicable.
- One commit per review round — group all fixes from the same reviewer together.
