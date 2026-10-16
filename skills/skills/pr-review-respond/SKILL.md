---
name: pr-review-respond
description: Read PR review comments on your own PR, address every finding in code, push, reply to the reviewer, and re-request their review. Use when a reviewer has left comments on a pull request and the author needs to respond, fix the code, and request a re-review.
---

# Skill: pr-review-respond

Read the review comments, address each finding, push, reply in the threads, and re-request review.

```sh
PRR=~/.config/opencode/skills/skills/pr-review/scripts
N=<pr>; REPO=<owner/repo>
```

## Workflow

### 1. Fetch comments

```sh
python3 $PRR/review_threads.py --repo $REPO --pr $N --format json > /tmp/threads-$N.json
gh api --paginate "repos/$REPO/issues/$N/comments?per_page=100"   # top-level comments
```

Collect every **unresolved** thread from every reviewer, human or bot. Note each reviewer's login and each thread's first-comment `databaseId`. When there are several reviewers (for example Junwei and Fangshan), handle all of them unless the user narrows the scope.

### 2. Evaluate, then check with the user

For each finding, check the codebase to confirm whether it's valid. Then show a numbered table in chat:

| # | Reviewer | Finding | Verdict (fix / rebut / ask) | Proposed change |

Where there's a real design choice, give options (A/B) and a recommendation. **Wait for the user** before editing, unless they already said "address them all" or similar. The user often accepts some findings, rejects others, or picks an option.

### 3. Apply fixes

- Make the smallest targeted edit for each accepted finding.
- After removing a symbol, grep the whole repo to confirm nothing still references it.
- For tcs-ui, verify with Playwright (`yarn workspace @tcs-ui/core-app playwright test --project=integration-chromium --grep "<spec>"`). There are no unit tests, and Cypress is gone. Run `yarn lint` on the files you changed.

### 4. Commit and push

```sh
git add <changed files>
git commit -S -m "chore(<scope>): address PR review - <short summary>"
git push origin HEAD && git push gitlab HEAD   # tcs-ui/tcs-core: push to both remotes
```

- Make one signed commit per review round. If GitHub reports "Commits must have verified signatures", re-sign them (`git rebase --exec 'git commit --amend --no-edit -S' <base>`) and force-push with `--force-with-lease`, but only after the user agrees.
- Use `--no-verify` only when a hook fails for an unrelated environment reason, such as the Docker daemon being down. Say so in the reply.
- If a push to `origin` fails with `Permission denied (publickey)`, run `ssh-add --apple-use-keychain ~/.ssh/id_ed25519`, then retry once. If that fails too, tell the user.

### 5. Reply in each thread (one batch call)

Write `/tmp/replies-$N.json`:

```json
[{"in_reply_to": 4089869812, "body": "Fixed in abc1234 — <one or two factual sentences>."}]
```

`in_reply_to` is the integer `databaseId` of the first comment in the thread. Then run:

```sh
python3 $PRR/submit_review.py --repo $REPO --pr $N --replies-only --comments-file /tmp/replies-$N.json \
  --signoff "${PR_REVIEW_SIGNOFF:-[addressed by ${PR_REVIEW_BOT_LOGIN:-schoolex}'s bot]}"
```

- Don't call `pulls/{n}/comments` with `-f in_reply_to=...` by hand. GitHub rejects the string type.
- Name the commit SHA and confirm it's pushed before replying. Never reply "fixed" about code that hasn't been pushed.
- Don't resolve reviewers' threads. Let them resolve.
- Don't cite unit tests as verification. Mention the Playwright run, a manual check, or a dev-environment run.

### 6. Summary comment (only if asked, or if there are more than 3 findings)

```sh
gh pr comment $N --repo $REPO --body-file /tmp/summary-$N.md
```

Write one bullet per finding, giving what changed or why it wasn't changed. Put the same signature at the end. Use a body file, never `--body` with escaped `\n`.

### 7. Re-request review

```sh
gh pr edit $N --repo $REPO --add-reviewer <login>[,<login2>]
```

### 8. Update the PR description if the scope changed

If the fixes change what the PR does, update the body with `gh pr edit $N --body-file`. Keep it concise.

## Rules

- Handle every finding: fix it, or give a short factual reason why it doesn't apply.
- Never close a finding silently.
