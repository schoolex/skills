## Shared Goal

Write reviews the author can act on. Be concise, specific, and focused on what needs to change and why.

## Bot Identity

Reviewer identity has a single source of truth, resolved (in order) from:

1. `PR_REVIEW_SIGNOFF` — full signature string, if set.
2. `PR_REVIEW_BOT_LOGIN` — the bot's GitHub login; the signature becomes `[Reviewed by <login>'s bot]`.
3. The default login `schoolex` when neither is set.

The same login also gates thread resolution in follow-up reviews (only resolve threads you opened). To check the active value:

```sh
python3 -c "import sys; sys.path.insert(0, '$HOME/.config/opencode/skills/pr-review/scripts'); import review_common as c; print(c.DEFAULT_BOT_LOGIN); print(c.DEFAULT_SIGNOFF)"
```

## Bot Signature

- For every pull request comment or review body the bot writes while using these skills, append the resolved signature (see Bot Identity) on its own line at the end. `submit_review.py` does this automatically; only append it by hand when writing comments outside the helper scripts.
- Do not prefix the signature with a bullet, numbering, quote marker, or any other Markdown decoration.
- Do not add this signature to commit messages, branch names, or PR titles unless explicitly requested.

## Shared Posture

- Be polite and empathetic in all review comments. Remember that code represents real effort by real people; frame every finding as a collaborative improvement, not a criticism of the author.
- Start by understanding the PR intent, changed files, prior review context, linked issues, and the latest head SHA.
- Prioritize correctness, security, performance, maintainability, and operational risk over style nits.
- Build a short risk map before line-by-line review: changed boundaries, ownership, lifecycle, async ordering, data/security, platform edges, and proof.
- Treat large refactors as behavior migrations. Compare old and new ownership, state transitions, side effects, and failure modes before commenting on local style.
- Prefer one consolidated review with high-signal inline comments over many fragmented remarks.
- Use GitHub formatting intentionally when it improves comprehension.

## Initial Review Workflow

1. Read the PR body, changed files, prior reviews, inline threads, and issue comments first.
2. Inspect the current diff and identify the highest-signal findings.
3. Anchor inline comments to stable locations. Prefer `line` and `side` for new comments, especially suggestions. Use `position` only when line-based metadata is unavailable.
4. Fetch the PR head SHA before posting so inline comments bind to the latest commit.
5. Build the review body and comments as files, then submit once with `submit_review.py`.
6. Use `COMMENT` for actionable findings or discussion. Use `APPROVE` only when the change is ready.

## Follow-Up Review Workflow

1. Read the latest PR body, changed files, prior reviews, inline threads, and issue comments before responding.
2. Check what changed since the previous review and which findings are still open.
3. Prefer replying in existing threads with `in_reply_to` when acknowledging fixes, clarifying scope, or closing the loop on earlier comments.
4. If the author explicitly says an issue will be tracked separately, and that scope split is reasonable, treat that thread as non-blocking for the follow-up review instead of repeating the same finding.
5. Only raise fresh inline comments for issues that still need action on this PR.
6. If there are no remaining blocking issues after accounting for fixes and separately tracked follow-ups, you may submit an `APPROVE` review.

## Recommended Commands

Read metadata and overall review state:

```sh
gh pr view <pr-url-or-number> \
  --json number,title,body,author,baseRefName,headRefName,headRefOid,files,commits,reviews,comments,url
```

Read inline review comments and issue comments separately:

```sh
gh api --paginate "repos/{owner}/{repo}/pulls/{id}/comments?per_page=100"
gh api --paginate "repos/{owner}/{repo}/issues/{id}/comments?per_page=100"
```

Read review threads with resolved and outdated state:

```sh
python ~/.config/opencode/skills/pr-review/scripts/review_threads.py \
  --repo {owner}/{repo} \
  --pr {id}
```

Resolve stable review anchors from the raw diff:

```sh
python ~/.config/opencode/skills/pr-review/scripts/diff_position.py \
  <pr-url-or-number> \
  src/service.py \
  --new-line 128 \
  --format json
```

Legacy position lookup by exact text:

```sh
python ~/.config/opencode/skills/pr-review/scripts/diff_position.py \
  <pr-url-or-number> \
  src/service.py \
  'result = expensive_call()'
```

Context view for ambiguous matches:

```sh
python ~/.config/opencode/skills/pr-review/scripts/diff_position.py \
  <pr-url-or-number> \
  src/service.py \
  --match-mode contains \
  --needle 'expensive_call' \
  --format text \
  --all \
  --context 2
```

Submit a consolidated review:

```sh
python ~/.config/opencode/skills/pr-review/scripts/submit_review.py \
  --repo {owner}/{repo} \
  --pr {id} \
  --validate \
  --body-file /tmp/review-body.txt \
  --comments-file /tmp/review-comments.json
```

Validate anchors without submitting:

```sh
python ~/.config/opencode/skills/pr-review/scripts/submit_review.py \
  --repo {owner}/{repo} \
  --pr {id} \
  --validate-only \
  --body-file /tmp/review-body.txt \
  --comments-file /tmp/review-comments.json
```

Submit an approval in a follow-up review:

```sh
python ~/.config/opencode/skills/pr-review/scripts/submit_review.py \
  --repo {owner}/{repo} \
  --pr {id} \
  --event APPROVE \
  --body-file /tmp/review-body.txt
```

Post threaded replies without creating a new review:

```sh
python ~/.config/opencode/skills/pr-review/scripts/submit_review.py \
  --repo {owner}/{repo} \
  --pr {id} \
  --replies-only \
  --comments-file /tmp/review-replies.json
```

## Supported Comment JSON Shapes

- Stable line comments: `{ "path": "src/foo.py", "line": 42, "side": "RIGHT", "body": "..." }`
- Multi-line comments: `{ "path": "src/foo.py", "start_line": 40, "start_side": "RIGHT", "line": 42, "side": "RIGHT", "body": "..." }`
- Legacy diff-position comments: `{ "path": "src/foo.py", "position": 12, "body": "..." }`
- File-level comments: `{ "path": "src/foo.py", "subject_type": "file", "body": "..." }`
- Thread replies: `{ "in_reply_to": 123456789, "body": "..." }`

## Formatting Guidance

- Use short headings and bullets in the top-level review body.
- Use fenced code blocks for suggested snippets and repro steps.
- Keep inline comments compact. A good pattern is: observation -> trigger/failing scenario -> impact -> fix/test.
- **Preferred inline comment format** (use this for all non-trivial findings):
  ```
  **[category]** <short title>

  **Problem:**
  1. <step-by-step explanation of what the code does>
  2. <what invariant breaks or what goes wrong>
  3. <impact — what fails, leaks, or misbehaves>

  **Suggested Fix:**
  <concise fix description, optionally with a code snippet>
  ```
  Open every comment with a bold category tag followed by a short title (a few words summarizing the finding) on its own line, e.g. `**[security]** Unvalidated redirect target`. Valid tags: `**[correctness]**`, `**[security]**`, `**[contract]**`, `**[async]**`, `**[performance]**`, `**[lifecycle]**`, `**[operational]**`, `**[structure]**`, `**[maintainability]**`, `**[evidence]**`. For nitpicks, use `**Nit:**` as the heading instead of `**Problem:**` (keep the category tag and short title).
- **Exact-naming rule:** Every `**Suggested Fix:**` must name the exact thing — the specific variable, function, method, palette token, assertion message, or flag name — not a generic description. `"Use palette.pill_pending.primary instead of #74550F"` is correct. `"Use a theme token"` is not.
- Prefer invariant-shaped comments: `When <realistic condition> happens, <invariant> breaks, causing <impact>. Consider <fix>, and add/adjust a test for <case>.`
- For design-level findings, name the ownership or boundary change: `This moves <responsibility> from <old owner> to <new owner>, but <case> still depends on <old invariant>. When <trigger>, <impact>. Consider <fix/proof>.`
- Include a verification cue when useful: what input/state to simulate, what path to click, what command/test to run, or what grep confirms the issue.
- Use suggestions only for small, safe, uncontroversial edits on the RIGHT side of the diff.
- If several issues share the same root cause, leave one strong comment on the primary line and mention sibling sites in the body rather than duplicating noise.

## Review Lens

- Security: watch for auth scope drift, secret exposure, injection, unsafe deserialization, path traversal, SSRF, and missing validation.
- Performance: look for accidental N+1 calls, repeated expensive work, unbounded loops, high-cardinality logging, synchronous blocking, and cache invalidation mistakes.
- Maintainability: flag hidden coupling, weak naming, hard-coded behavior, missing tests around risky branches, and confusing control flow.
- Readability: prefer comments and suggestions that reduce cognitive load, not just satisfy the API.

## Risk Map

Before writing findings, identify which boundaries the PR touches:

- Process execution, terminals, file watchers, queues, generated files, sockets, timers, and background workers.
- Network, WebSocket, provider, plugin, SDK, IPC, API, schema, and persistence boundaries.
- UI state, streaming state, async effects, retry/reconnect flows, navigation, and unmount behavior.
- Auth, tokens, credentials, CORS, pairing/callback flows, logs, diagnostics, and serialized data.
- Filesystems, paths, shells, ports, worktrees, symlinks, downloads, and platform detection.
- Test infrastructure, mocks, benchmarks, screenshots, recordings, and manual verification claims.

Do not review only the changed lines. Review the invariant the change is supposed to preserve.

## Structural Quality Gate

Before approving, ask whether the PR makes the codebase simpler or merely makes the requested behavior work.

Flag structural regressions when the diff:

- Adds ad-hoc branches, feature flags, nullable modes, or one-off conditionals into already busy flows.
- Preserves incidental complexity when a clearer restructuring could delete concepts, branches, helpers, or state.
- Moves code around without reducing the number of concepts a reader must hold.
- Adds wrappers, pass-through helpers, casts, `any`/`unknown`, or optional params that obscure the real invariant.
- Puts logic in the wrong layer instead of the canonical package, service, hook, component, or helper.
- Duplicates behavior that already has a canonical helper.
- Pushes a file from below 1000 lines to above 1000 lines without a strong reason.
- Serializes independent async work or performs related updates non-atomically when the cleaner structure is obvious.

Prefer comments that ask for the smallest behavior-preserving simplification:

- Delete a layer of indirection.
- Reframe the state model so conditionals disappear.
- Move feature-specific logic behind the abstraction that owns it.
- Replace repeated conditionals with a typed model, dispatcher, or policy object.
- Split a large file into focused modules.
- Reuse the canonical helper.
- Make the boundary explicit instead of relying on casts, fallbacks, or optionality.

## Addressed-Finding Priority

These patterns came from addressed 2026 review findings in T3 Code and OpenCode. Bias toward them before style comments:

- Boundary contracts: shape drift across provider/API/client/server/plugin/schema/persistence boundaries.
- Ownership and abstraction fit: duplicated logic, unclear responsibility, hidden coupling, or refactors that move behavior without preserving state transitions.
- Async ordering: stale closures, duplicate side effects, missed events, reconnect/retry races, and late state writes.
- Lifecycle and bounds: startup/shutdown ownership, cancellation, cleanup, timeouts, listener removal, output caps, queue drains, and memory/file-size limits.
- Evidence: tests or manual proof that exercise the exact risky condition, not just a nearby happy path.
- Security/data handling: token scope, secret storage, logging, callback state, CORS/header behavior, and trust boundaries.
- Platform/path edges: Windows shell quoting, CRLF, symlinks, worktree vs project root, paths beginning with `-`, default ports, and platform-specific UI assumptions.

Separate confidence from severity. If static evidence is partial, say what should be verified. Reserve blocking language for demonstrable invariant breaks.

## Patterns From Addressed Reviews

Run these checks before writing comments:

- Edge cases: empty, missing, `None`/`undefined`, duplicate, invalid, negative, partial, stale, rerun, and unexpected enum/type branches.
- Auth and scoping: caller, route guard, role/feature gate, fetch scope, filtering before serialization, redaction, and alternate UI/API paths.
- Contract drift: backend model, frontend serializer, API client, route constants, OpenAPI/docs, env vars, SDK/shared helpers, and tests.
- Tests: whether the test fails for the exact risky branch; whether mocks are keyed by semantic inputs instead of call count/order; failure and rollback coverage.
- External services: non-2xx handling, retries, cleanup, operation ordering, partial-failure recovery, and persistence before/after provider calls.

Boundary contracts:

- Check what shape enters and leaves every changed boundary: provider payloads, schema encodings, API responses, WebSocket messages, plugin contracts, SDK adapters, decoded settings, and persisted records.
- Look for local conversions that flatten structured content, drop nested error details, coerce unknown input too early, or spread decoded objects into encoded forms.
- Prefer shared schemas/type guards at runtime boundaries. Ask for negative tests where only happy-path contract tests exist.
- For branch refs, path-like identifiers, enum states, and provider IDs, check nested values and future provider variants rather than only today's examples.

Ownership and abstraction fit:

- Ask whether the abstraction clarifies ownership or merely moves behavior.
- Watch for duplicate fetch logic, duplicate listeners, duplicate sanitization, dead code, hidden global state, and separate manual/interval paths that can drift.
- In refactors, compare old and new state transitions: loading, error reset, pending input routing, selected item fallback, retry behavior, and persistence side effects.
- For extracted components/hooks/managers/adapters, verify that lifecycle responsibility moved with the behavior.

Async ordering and idempotency:

- Check stale closures after navigation, project/thread switches, unmounts, reconnects, retries, and interval/manual refresh overlap.
- Check whether retries are idempotent and whether a failed send both requeues internally and rejects to a caller that may retry too.
- Check cooldowns and readiness flags: they should advance when useful work happened, not when work was skipped.
- Check event/listener registration for duplicate handlers, missed cleanup, out-of-order delivery, and late state writes.
- Prefer explicit readiness barriers, completion receipts, drain methods, sequence numbers, and serialized per-resource operations over sleeps and polling.

Lifecycle, cleanup, and bounds:

- For subprocesses, terminals, file watchers, queues, generated files, sockets, and timers, ask who owns startup, shutdown, cancellation, cleanup, timeout, and force-kill fallback.
- Check failures after partial startup: if an error occurs after spawn/open/subscribe but before setup completes, the resource still needs cleanup.
- Check output/history/diff/file reads for caps before allocation. Truncation should be visible to callers, not silently parsed as complete data.
- Check queued persistence and background writes for unbounded memory growth, unhandled rejections, delete/write races, and drain ordering.
- Check listeners and injected managers for removal in stop/dispose paths, especially when the dependency may outlive the caller.

Security and data handling:

- Name the trust boundary. Check who can trigger the route/callback/message, what state authenticates it, and what happens on error branches.
- Credentials should use platform-appropriate secret storage where possible. Encryption without real secret material is not a substitute for a keychain.
- Check token scopes in docs and code, secret logging, diagnostic dumps, serialized settings, URL token stripping, CORS/header consistency, and retry paths that re-read sensitive inputs.
- Make sure auth/state validation gates every callback outcome, including `error`, missing-code, retry, and cancellation branches.

Platform and path edges:

- Check Windows shell quoting, `cmd.exe` vs POSIX quoting, CRLF handling, device names, symlinked `.git` directories, and case/path normalization.
- User paths that can begin with `-` should be passed after `--` or through an API that avoids option parsing.
- Distinguish project root, worktree path, repository root, and remote runtime cwd. Avoid silently starting processes in the wrong directory.
- Check default ports and URL builders so omitted ports do not produce invalid `ws://host:`-style URLs.
- UI and docs should not assume macOS when Windows/Linux behavior or icons are user-visible.

Evidence and verification:

- Ask whether the evidence proves the risky invariant. A passing broad test is weaker than a failing-then-passing regression for the specific condition.
- Mocks should match real payload shape, error shape, timing, and retry behavior. Avoid tests that pass because the mock is keyed by call count rather than semantics.
- For schema/contract changes, look for negative tests and round-trip tests, not only positive decode/encode cases.
- For performance claims, ask for before/after measurements under comparable input sizes.
- For UI behavior, ask for screenshots, recordings, or explicit manual scenario notes when tests do not cover the interaction.

Path-aware checks:

- `api/backend/**`: auth scope, pagination, response contracts, query defaults, serialization boundaries, data leak paths, status codes, and source-of-truth constants.
- `notebooks/migration/**`: idempotency, rerun safety, partial writes, non-atomic delete/insert pairs (flag as blocking if there is no transaction or rollback path), commented-out writes, broad list overwrites, cleanup, and verification/readback. Before flagging a missing `DRY_RUN` flag or commented-out writes as **blocking**, check whether the PR body or existing comments describe an intentional offline-review / uncomment-at-runtime convention — if so, downgrade to **nit** and note the rerun risk. Phrase operational risk findings as "before you run this" rather than "before you merge this."
- `api/infra/**`: provider API contracts, secret/config availability, client construction timing, retries, cleanup, and persistence ordering.
- Query/data code: timestamp units, timezone boundaries, active vs inactive date keys, hardcoded columns, silent data dropping, SQL/query generation, and pushdown vs in-memory filtering.
- `packages/core-app/src/api/**`: shared interceptors, route prefixes, env fallbacks, nullable/optional fields, unsafe casts, empty interfaces, and backend assumptions.
- `packages/core-app/src/features/**`: route guards, feature flags, role gates, state reset, async lifecycle, duplicate actions, stale closures, and late stream/session events.
- `packages/core-app/src/shared/components/**`: visual states, accessibility labels, empty states, keyboard/menu behavior, invalid input dismissal, disabled/loading states, and reusable abstractions.

## Safe GH CLI Patterns

- Prefer `gh api --input /tmp/payload.json` for nested payloads. It is more reliable than many `-F` flags.
- Quote endpoints that contain `{owner}` or `{repo}` placeholders in shells that treat braces specially.
- Do not use `gh api -f "$(cat review.json)"` for JSON bodies; use `--input review.json`.
- Use `--paginate` for comment history to avoid silently missing older threads.
- Keep body text in files rather than inline shell strings when it includes backticks, quotes, braces, or Markdown fences.
- Prefer the helpers in `skills/pr-review/scripts/review_common.py` and `skills/pr-review/scripts/submit_review.py` over hand-rolled JSON submission.

## Helper Scripts

- `~/.config/opencode/skills/pr-review/scripts/diff_position.py`
  - Parses `gh pr diff --patch` safely.
  - Resolves `position`, `line`, `side`, `old_line`, and `new_line`.
  - Supports exact, contains, and regex matching plus contextual output.
- `~/.config/opencode/skills/pr-review/scripts/review_threads.py`
  - Uses GitHub GraphQL to fetch review threads with resolved and outdated state.
  - Produces compact summaries or raw JSON for follow-up review decisions.
- `~/.config/opencode/skills/pr-review/scripts/review_common.py`
  - Centralizes sign-off handling, comment normalization, JSON file writing, and `gh api --input` submission helpers.
- `~/.config/opencode/skills/pr-review/scripts/submit_review.py`
  - Builds normalized review payloads and threaded replies from JSON.
  - Auto-fetches the PR head SHA unless disabled.
  - Validates safer comment shapes, optional PR diff anchors, and thread replies.
  - Submits payloads through the shared JSON helpers.

## Validation

```sh
python3 -m unittest skills/pr-review/scripts/test_review_helpers.py
python3 -m py_compile \
  skills/pr-review/scripts/review_common.py \
  skills/pr-review/scripts/diff_position.py \
  skills/pr-review/scripts/review_threads.py \
  skills/pr-review/scripts/submit_review.py \
  skills/pr-review/scripts/test_review_helpers.py
```
