---
name: pr-review-initial
description: Give the initial review for a pull request with concise, actionable findings. Use when a PR needs its first substantive review or when the user asks for an initial review pass.
---

Use this skill for the first substantive review on a PR.

## Review Mode

Determine the review mode **before** starting Step 1. Two modes exist:

- **`external`** (default) — findings are posted to GitHub as a pull request review via `submit_review.py`.
- **`internal`** — findings are presented directly to the user in the chat. Nothing is posted to GitHub. Use this mode when the user says "internal review", "don't post", "just show me", or similar.

Detect `internal` mode from phrases like:
- "internal review"
- "internal code review"
- "don't post", "don't submit", "no GitHub post"
- "just show me the findings"

When `internal` mode is active:
- **Skip Steps 6 and 7 entirely** (anchor validation and `submit_review.py` submission).
- Instead, output the consolidated review directly in the chat as formatted Markdown.
- Do **not** write `/tmp/review-body.txt` or `/tmp/review-comments.json` to disk.
- Format inline findings as a Markdown list grouped by file, with severity badges (`🔴 blocking`, `🟡 notable`, `⚪ nit`) before each item for scannability.
- Still append the methodology footnote and category legend at the end of the output.

For `external` mode, continue with the full submission workflow (Steps 6–7) as described below.

## Goal

Leave high-signal reviews the author can act on, using two independent specialist agents reviewing in parallel, then a manager agent that triages and consolidates their findings into one coherent review.

## Workflow

### Step 1 — Gather shared context (orchestrator)

Before spawning any agents, read and collect the following so every agent starts with the same ground truth:

```sh
gh pr view <pr-url-or-number> \
  --json number,title,body,author,baseRefName,headRefName,headRefOid,files,commits,reviews,comments,url
```

Also collect the raw diff:

```sh
gh pr diff <pr-url-or-number> --patch
```

And any prior review threads:

```sh
python ~/.config/opencode/skills/pr-review/scripts/review_threads.py \
  --repo {owner}/{repo} \
  --pr {id}
```

Store the PR number, repo slug (`owner/repo`), head SHA, PR body, file list, and full patch in variables you will pass verbatim into every agent prompt below.

Also read this skill file and derive a concise `methodologyDescription`: who the reviewers are, what each covers, and how findings are consolidated. Pass this to the manager agent.

#### Classify the PR type before spawning reviewers

Look at the changed file paths and classify the PR into one of two modes. Pass `prMode` into every agent prompt below.

- **`runbook`** — the majority of changed files are under `notebooks/`, `scripts/`, or are standalone `.py`/`.sh` migration/pipeline files intended to be run once or on a schedule. These are _not_ production application code.
- **`application`** — everything else (backend services, frontend, infra, shared libraries, tests).

When `prMode = runbook`:
- Reviewer A should prioritize **operational risk** (idempotency, rerun safety, partial-failure, sequencing, dry-run defaults) over correctness or security.
- Reviewer B should skip structural quality gate and maintainability concerns; focus only on **evidence** (are steps documented, are destructive operations clearly gated or commented).
- Both reviewers must phrase findings as "before you run this" rather than "before you merge this."
- Before flagging a missing `DRY_RUN` flag or commented-out writes as blocking, check whether the PR body or existing comments describe an intentional offline-review / uncomment-at-runtime convention. If so, downgrade to a **nit**.

### Step 2 — Launch 2 specialist reviewer agents in parallel

Spawn both agents **in the same message** using the Task tool so they run concurrently. Each agent must **only research and produce findings** — they must NOT submit any review to GitHub. Pass the full shared context (PR number, repo, head SHA, diff, PR body, file list) into every agent prompt.

#### Reviewer A — Correctness, Security & Operational Risk

Prompt:

```
You are a PR reviewer specializing in correctness, security, and operational risk.

Shared context:
- Repo: {owner}/{repo}
- PR: {id}
- PR mode: {prMode}   // "runbook" or "application"
- Head SHA: {headSha}
- PR body: {prBody}
- Files changed: {fileList}
- Full patch:
{patch}

Read `~/.config/opencode/skills/pr-review/REFERENCE.md` for posture and lens guidance.

If `prMode = runbook`: prioritize **operational risk** (idempotency, rerun safety, partial-failure recovery, dry-run defaults, sequencing). Before flagging missing DRY_RUN or commented-out writes as blocking, check whether the PR body or comments describe an offline-review / uncomment-at-runtime convention — if so, downgrade to nit. Phrase findings as "before you run this" rather than "before you merge this." Skip style, naming, and structural concerns entirely.

Do **not** flag SQL/NoSQL injection via f-string or string interpolation in runbook mode. All query inputs are manually keyed in by the author — they are not user-supplied — so injection is not a realistic threat vector in this context.

If `prMode = application`: focus on:
- Logic bugs, edge cases (empty, null/undefined, missing, duplicate, stale, partial, rerun, unexpected enum/type branches)
- Security issues: auth scope drift, secret exposure, injection, unsafe deserialization, path traversal, SSRF, missing validation, token handling, trust boundaries
- Contract drift across API/schema/client/server/plugin/persistence boundaries
- Async ordering: stale closures, duplicate side effects, missed events, reconnect/retry races
- Performance: N+1 calls, repeated expensive work, unbounded loops, high-cardinality logging, synchronous blocking, cache invalidation
- Lifecycle & bounds: subprocess/timer/socket/watcher ownership, startup/shutdown/cancellation/cleanup, output caps, unbounded memory growth, drain ordering
- Operational risk: missing observability, error swallowing, missing retries, partial-failure recovery, persistence ordering, queue drain races

Do NOT comment on style, maintainability, or structural quality — leave those to the other reviewer.

**Exact-naming rule:** Every `**Suggested Fix:**` must name the exact thing — the specific variable, function, method, palette token, assertion message, or line — not a generic description. "Use `palette.pill_pending.primary` instead of `#74550F`" is correct. "Use a theme token" is not.

For each finding produce a structured JSON object:
{
  "severity": "blocking" | "notable" | "nit",
  "category": "correctness" | "security" | "contract" | "async" | "performance" | "lifecycle" | "operational",
  "path": "src/foo.py",           // omit for PR-level findings
  "line": 42,                      // omit when not line-specific
  "side": "RIGHT",                 // omit when not line-specific
  "body": "<category tag> <short title> <use the preferred inline comment format from REFERENCE.md: **Problem:** / **Suggested Fix:** blocks>"
}

The category tag plus a short title must be the first thing in `body`, formatted as a bold label matching the `category` field, followed by a few-word summary of the finding:
- `**[correctness]**`, `**[security]**`, `**[contract]**`, `**[async]**`, `**[performance]**`, `**[lifecycle]**`, `**[operational]**`

Example body opening: `**[security]** Unvalidated redirect target\n\n**Problem:**\n1. ...`

Return a JSON array of findings. Do not submit anything to GitHub.
```

#### Reviewer B — Maintainability, Structure & Evidence

Prompt:

```
You are a PR reviewer specializing in maintainability, structural quality, and test evidence.

Shared context:
- Repo: {owner}/{repo}
- PR: {id}
- PR mode: {prMode}   // "runbook" or "application"
- Head SHA: {headSha}
- PR body: {prBody}
- Files changed: {fileList}
- Full patch:
{patch}

Read `~/.config/opencode/skills/pr-review/REFERENCE.md` for posture and lens guidance.
If the PR touches React/MUI frontend code (.tsx, sx props, styled() calls, inline style props), also read `~/.config/opencode/skills/pr-review/FRONTEND.md` and apply its checks.

If `prMode = runbook`: skip structural quality gate and naming concerns entirely. Focus only on **evidence** — are destructive operations gated or commented, are steps documented, is there a way to verify before committing. Phrase findings as "before you run this."

If `prMode = application`: focus exclusively on:
- Structural quality gate: ad-hoc branches/flags, hidden coupling, duplicated logic, wrong abstraction layer, files growing past 1000 lines, unnecessary wrappers
- Maintainability: weak naming, hard-coded behavior, confusing control flow, unclear ownership; for frontend code this includes hardcoded magic values, missing theme tokens, `style` prop vs `sx`, and duplicated `sx` blocks — use `[maintainability]`
- Structure: fragile absolute offsets in frontend code — use `[structure]`
- Evidence: whether tests prove the risky invariant (not just a passing broad test), mock fidelity, missing negative/round-trip tests, missing manual proof for UI behavior

Do NOT comment on correctness, security, performance, or operational risk — leave those to the other reviewer.

**Exact-naming rule:** Every `**Suggested Fix:**` must name the exact thing — the specific variable, function, method, palette token, assertion message, or line — not a generic description. "Use `palette.pill_pending.primary` instead of `#74550F`" is correct. "Use a theme token" is not.

For each finding produce a structured JSON object:
{
  "severity": "blocking" | "notable" | "nit",
  "category": "structure" | "maintainability" | "evidence",
  "path": "src/foo.py",
  "line": 42,
  "side": "RIGHT",
  "body": "<category tag> <short title> <use the preferred inline comment format from REFERENCE.md: **Problem:** / **Suggested Fix:** blocks>"
}

The category tag plus a short title must be the first thing in `body`, formatted as a bold label matching the `category` field, followed by a few-word summary of the finding:
- `**[structure]**`, `**[maintainability]**`, `**[evidence]**`

Example body opening: `**[evidence]** Missing test for retry path\n\n**Problem:**\n1. ...`

Return a JSON array of findings. Do not submit anything to GitHub.
```

### Step 3 — Triage and consolidate (orchestrator)

Once all three reviewer agents return their findings, triage and consolidate them directly:

1. De-duplicate: if two reviewers flagged the same line/issue, keep the more detailed body and merge any complementary context.
2. Promote severity when multiple reviewers independently flagged the same issue.
3. Re-rank: order findings by severity (`blocking` first, then `notable`, then `nit`).
4. Consolidate related issues: if several findings share the same root cause, write one strong consolidated comment that mentions sibling sites.
5. Produce:
   - A short top-level review body (bullets: major themes, overall risk, blocking issues).
   - A final `review-comments.json` array in the supported comment shapes from `REFERENCE.md`. Each comment body **must** open with the bold category tag followed by a short title (e.g. `**[security]** Unvalidated redirect target`) on its own line, then a blank line, then the preferred inline format: `**Problem:**` (numbered steps) + `**Suggested Fix:**`. For nitpicks, use `**Nit:**` as the heading instead of `**Problem:**`. Preserve the tag from the source finding; do not strip or move it during consolidation.
     - **Formatting `**Suggested Fix:**`:** never bury structure in a run-on paragraph.
       - If the fix has conditional branches ("if X do A, if Y do B") or more than one discrete step, render them as a Markdown list. Lead with the decision/question, then one bullet per branch with the condition bolded (e.g. `- **If gating is endpoint-wide:** ...`).
       - If the fix is a concrete code change, put the replacement in a fenced code block (with language hint) on its own lines, then keep any rationale in prose after it.
       - A single one-line fix with no code snippet can stay inline.
       - The exact-naming rule still applies inside each bullet or code block.
   - A `review-body.txt` file. At the very end, append a `---` horizontal rule followed by this fixed methodology footnote:

      > This review was produced by two independent specialist agents (correctness/security and maintainability/evidence) whose findings were de-duplicated and consolidated by an orchestrator. Reviewer A covered logic bugs, contract drift, async ordering, and operational risk. Reviewer B covered structural quality, maintainability, and test evidence.

     Then append the category legend. Render only the tags that actually appear in this review's comments, as a Markdown bullet list (one tag per line) so it stays readable — do not emit it as a single run-on paragraph. Use a `<details>` block to keep it collapsed:

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
6. Validate anchors before submitting:
   ```sh
   python ~/.config/opencode/skills/pr-review/scripts/submit_review.py \
     --repo {owner}/{repo} \
     --pr {id} \
     --validate-only \
     --body-file /tmp/review-body.txt \
     --comments-file /tmp/review-comments.json
   ```
7. Fix any anchor failures, then submit:
   ```sh
   python ~/.config/opencode/skills/pr-review/scripts/submit_review.py \
     --repo {owner}/{repo} \
     --pr {id} \
     --validate \
     --body-file /tmp/review-body.txt \
     --comments-file /tmp/review-comments.json
   ```

## Output Rules

- Be polite and empathetic. Frame every finding as a collaborative improvement, not a criticism of the author.
- Keep the top-level review body short and actionable.
- Open every inline comment with a bold category tag followed by a short title on its own line (e.g. `**[security]** Unvalidated redirect target`), then a blank line, then `**Problem:**` (numbered steps) + `**Suggested Fix:**`. For nitpicks use `**Nit:**` instead of `**Problem:**`.
- Every `**Suggested Fix:**` must name the exact thing — the specific variable, function, token, assertion message, or line. Generic descriptions ("use a theme token") are not sufficient.
- Append the required bot signature to every review body and comment (`submit_review.py` does this automatically).
- Do not use `REQUEST_CHANGES` unless explicitly asked.
- Submit `COMMENT` unless the change is clearly ready for `APPROVE`.

## Practical Checks

- If a `Read` call on the expected repo path fails, switch to GitHub-fetched file content via `gh api ... -H "Accept: application/vnd.github.raw+json"`.
- Before submitting inline comments, sanity-check the exact target line from the head file content.
- For tricky anchor cases, run `submit_review.py --validate-only` first. If needed, rerun with `GH_DEBUG=api` to capture GitHub's validation error.

See `../pr-review/REFERENCE.md` for shared workflow, recommended commands, helper scripts, comment JSON shapes, formatting rules, and validation commands.
