---
name: pr-review-initial
description: Give the initial review for a pull request (someone else's PR, or an "internal review" of your own) with concise, actionable findings, drafted in chat before anything is posted. Use when a PR needs its first substantive review. If the user wants findings fixed and re-reviewed in a loop, use pr-review-fix-loop instead; if a prior review exists and the author has responded, use pr-review-follow-up.
---

Use this skill for the first substantive review on a PR.

Shared helpers and standards: read `~/.config/opencode/skills/skills/pr-review/REFERENCE.md` (posture, lens, **Posting Gate**, anchoring, project facts). Scripts live at:

```sh
PRR=~/.config/opencode/skills/skills/pr-review/scripts
```

Use that path verbatim. Do not guess other locations.

## Pick the right skill first

- Prior review by us exists and the author replied or pushed → **pr-review-follow-up**.
- "fix the findings", "loop it", "review fix review" → **pr-review-fix-loop**.
- "what is this PR trying to do", "is there a better way to do X" → answer directly; no formal review.

## Review Mode

- **`draft`** (default): run the review, show numbered findings in chat, then follow the Posting Gate in REFERENCE.md. Submit only what the user picks.
- **`internal`**: triggered by "internal review", "don't post", "my own PR", or when the user is the PR author. Show findings in chat only, and never submit. Don't write the `/tmp` review files.
- **Pre-approved posting**: when the request already says "post it", "approve if non-blocking", or similar, skip the wait and submit per that instruction.

In chat, group findings by file with severity badges (`🔴 blocking`, `🟡 notable`, `⚪ nit`) and number them globally so the user can say "post 1,3".

## Workflow

### Step 1: Gather shared context (orchestrator)

Do REFERENCE.md's Branch Setup first if a local checkout exists. Then run:

```sh
N=<pr-number>; REPO=<owner/repo>
gh pr view $N --repo $REPO \
  --json number,title,body,author,baseRefName,headRefName,headRefOid,files,commits,reviews,comments,url
gh pr diff $N --repo $REPO --patch > /tmp/pr-$N.patch && wc -l /tmp/pr-$N.patch
python3 $PRR/review_threads.py --repo $REPO --pr $N
```

Record the repo, PR number, head SHA, PR body, file list, patch path, and total changed lines (additions plus deletions).

Read file content at the head SHA from the local checkout when it is on the PR branch. Otherwise use `python3 $PRR/fetch_file.py --repo $REPO --ref <headSha> <path>...`.

#### Classify the PR

`prMode`:
- **`runbook`**: most changed files are under `notebooks/`, `scripts/`, or are standalone `.py`/`.sh` migrations or pipelines that run once or on a schedule.
- **`application`**: everything else.

`reviewDepth`:
- **`single`**: up to 150 changed lines, docs, config, or mechanical changes, or the user said "quick", "lenient", or "don't use subagents". Do the review yourself in one pass, covering both lenses below. Don't spawn agents.
- **`dual`**: everything else. Spawn Reviewer A and Reviewer B in parallel.

For `runbook` mode:
- Reviewer A prioritises operational risk: idempotency, rerun safety, partial failure, sequencing, and dry-run defaults.
- Reviewer B checks only evidence: destructive operations are gated, and steps are documented.
- Phrase findings as "before you run this".
- If the PR body or comments describe an offline-review or uncomment-at-runtime convention, a missing `DRY_RUN` is a **nit**.
- Do not flag f-string query injection, because inputs are keyed in by the author.
- Do not flag Databricks widget-state persistence or a commented-out `restartPython()`. The user has dismissed both before.

### Step 2: Review

Each reviewer only researches and returns findings. Reviewers never submit anything to GitHub.

Pass the **patch file path**, not the patch text. Reviewers `Read` `/tmp/pr-{id}.patch` themselves, so the diff isn't duplicated in every prompt.

Shared prompt header for both reviewers:

```
Shared context:
- Repo: {owner}/{repo}   PR: {id}   Head SHA: {headSha}   PR mode: {prMode}
- PR body: {prBody}
- Files changed: {fileList}
- Patch: read /tmp/pr-{id}.patch
- Local checkout at head: {path or "none — use python3 ~/.config/opencode/skills/skills/pr-review/scripts/fetch_file.py --repo {owner}/{repo} --ref {headSha} <paths>"}

Read ~/.config/opencode/skills/skills/pr-review/REFERENCE.md (sections: Project Facts, Anchoring Inline Comments, Review Lens, Risk Map, Patterns From Addressed Reviews).
Respect the PR's stated intent and any deferrals in the PR body. A behaviour the author explicitly calls out as intended or pre-existing is not blocking.

Return ONLY a JSON array. Each element:
{
  "severity": "blocking" | "notable" | "nit",
  "category": "<one of your categories>",
  "path": "src/foo.ts",   // omit for PR-level findings
  "line": 42,             // RIGHT-side line number taken from the patch hunk; must be inside a hunk
  "body": "**[<category>]** <short title>\n\n**Problem:**\n1. ...\n\n**Suggested Fix:**\n..."
}
For nits use **Nit:** instead of **Problem:**.
Exact-naming rule: every Suggested Fix names the exact variable, function, token, or line. "Use a theme token" is not acceptable; "Use `palette.pill_pending.primary` instead of `#74550F`" is.
Do not submit anything to GitHub.
```

**Reviewer A: correctness, security and operational risk.** Categories: `correctness`, `security`, `contract`, `async`, `performance`, `lifecycle`, `operational`.
- Logic bugs and edge cases (empty, null, duplicate, stale, partial, rerun, unexpected enum).
- Security: auth scope drift, secret exposure, injection, unsafe deserialisation, path traversal, SSRF, missing validation, trust boundaries.
- Contract drift across API, schema, client, server and persistence boundaries.
- Async ordering: stale closures, duplicate side effects, missed events, retry races.
- Performance: N+1 queries, repeated expensive work, unbounded loops, blocking calls.
- Lifecycle and bounds: cleanup, cancellation, output caps, unbounded growth.
- Operational: observability, swallowed errors, retries, partial-failure recovery.
- Skip style and maintainability.

**Reviewer B: maintainability, structure and evidence.** Categories: `structure`, `maintainability`, `evidence`.
- If the PR touches React/MUI (`.tsx`, `sx`, `styled()`, `style`), also read `~/.config/opencode/skills/skills/pr-review/FRONTEND.md`.
- Structural quality gate: ad-hoc branches, hidden coupling, duplication (two copies alone is not blocking), wrong layer, files growing past 1,000 lines, needless wrappers.
- Maintainability: naming, hard-coded behaviour, magic values or missing theme tokens, `style` used instead of `sx`.
- Evidence: tests prove the risky invariant, mock fidelity, negative tests. tcs-ui uses **Playwright only**, so never ask for Cypress or unit tests there.
- Skip correctness, security and performance.

Spawn both agents in the same message. Before you consolidate, read their output with a sceptical eye.

### Step 3: Triage and consolidate (orchestrator)

1. Drop findings that contradict the stated PR intent, or that flag pre-existing behaviour the author already called out.
2. De-duplicate. When two reviewers flagged the same issue independently, raise its severity.
3. Merge findings that share a root cause into one comment that lists the sibling sites.
4. Sort by severity: blocking, then notable, then nit.
5. Make `**Suggested Fix:**` easy to scan:
   - Use a bullet per branch for conditional fixes (`- **If X:** ...`).
   - Put code changes in a fenced block.
   - One-line fixes can stay inline.
6. **Present the numbered draft in chat, and stop at the Posting Gate.** Skip this stop only when posting was pre-approved, or in `internal` mode (which stops here for good).

### Step 4: Submit (external only, after the user picks)

Write only the selected findings. Keep `severity` and `category` in the JSON; `submit_review.py` strips them.

- `/tmp/review-body-{id}.txt`: a short top-level body with themes, overall risk and blocking items. End it with `---`, then the footnote and the legend below.
- `/tmp/review-comments-{id}.json`: the selected inline comments.

Footnote. Use the second sentence only for `dual` depth:

> This review was produced by two independent specialist agents (correctness/security and maintainability/evidence) whose findings were de-duplicated and consolidated by an orchestrator.

Legend. Include only the tags that are actually used:

```markdown
<details>
<summary>Category legend</summary>

- `[correctness]` — logic bugs & edge cases
- `[security]` — auth, secrets, injection
- `[contract]` — API/schema drift
- `[async]` — ordering & race conditions
- `[performance]` — N+1, blocking, unbounded loops
- `[lifecycle]` — resource cleanup & bounds
- `[operational]` — idempotency, partial-failure, observability
- `[structure]` — coupling & abstraction
- `[maintainability]` — naming, hard-coded behavior
- `[evidence]` — proof that the change works

</details>
```

Validate, then submit **once**:

```sh
python3 $PRR/submit_review.py --repo $REPO --pr $N --validate-only \
  --diff-file /tmp/pr-$N.patch \
  --body-file /tmp/review-body-$N.txt --comments-file /tmp/review-comments-$N.json
# fix any anchor errors (see REFERENCE.md "Anchoring Inline Comments"), then:
python3 $PRR/submit_review.py --repo $REPO --pr $N --validate --event {COMMENT|APPROVE} \
  --diff-file /tmp/pr-$N.patch \
  --body-file /tmp/review-body-$N.txt --comments-file /tmp/review-comments-$N.json
```

For an approval with no comments, use `--event APPROVE --body-file ...` only.

If the user later asks to change a comment that's already posted, edit it in place rather than posting a new one:

```sh
gh api -X PATCH "repos/$REPO/pulls/comments/<id>" -F body=@/tmp/comment.md
```

## Output Rules

- Be polite and collaborative. Keep the top-level body short.
- Every inline comment opens with `**[category]** short title`, then a blank line, then `**Problem:**` (or `**Nit:**`), then `**Suggested Fix:**`.
- `submit_review.py` appends the bot signature automatically.
- Never use `REQUEST_CHANGES` unless asked. Use `APPROVE` when nothing is blocking and the user agrees (or pre-approved). Otherwise use `COMMENT`.
