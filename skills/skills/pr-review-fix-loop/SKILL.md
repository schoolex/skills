---
name: pr-review-fix-loop
description: Runs a bounded internal reviewer/fixer loop over your own PR or branch changes, never posting to GitHub. Use when the user says "internal review and fix", "loop it", "review fix review", "fix all non-nits and recheck", or wants findings fixed rather than posted.
---

# PR Review Fix Loop

Use this skill to internally review PR changes, fix the review findings, and re-review until no actionable findings remain or three rounds have completed.

## Operating Rules

- Run at most 3 review/fix rounds.
- Spawn two role-specific agents through the Task tool: `reviewer` and `fixer`.
- The reviewer must not edit files or submit GitHub review comments unless the user explicitly asks.
- The fixer may edit files, run targeted tests, and report what changed.
- Keep the primary agent as coordinator: decide when to stop, resolve conflicts, and give the final user summary.
- Do not revert or overwrite unrelated user changes.
- Fix only `blocking` and `notable` findings by default; list nits in the final summary unless the user asks to fix them too.
- Verification for tcs-ui is Playwright (`yarn workspace @tcs-ui/core-app playwright test --project=integration-chromium --grep ...`) plus `yarn lint` on changed files — there are no unit tests and Cypress is gone.
- Pass the diff as a file path (`git diff origin/<base>...HEAD > /tmp/loop.patch`), not inline text, so each round's prompt stays small.
- Do not commit or push unless the user asks; when they do, push to both `origin` and `gitlab`.

## Reviewer Standard

The reviewer uses the same checks as the PR review skills. Both subagents must read `~/.config/opencode/skills/skills/pr-review/REFERENCE.md` first and apply its shared posture, review lens, risk map, and structural quality gate rather than a paraphrase.

## Workflow

1. Determine the review target.
   - If the user supplied a PR URL or number, inspect it with `gh pr view`, `gh api --paginate`, and the PR diff.
   - Otherwise, inspect local branch changes with `git status` and an appropriate diff against the base branch.
2. Round 1: spawn the reviewer agent with the target context and ask for actionable findings only.
3. If the reviewer finds no actionable issues, stop and summarize.
4. Spawn the fixer agent with the reviewer findings and ask it to make the smallest correct fixes, then run targeted verification.
5. Spawn the reviewer again with the updated diff and prior findings. Ask it to verify fixes and look for regressions introduced by the fixes.
6. Repeat fix/review until findings are resolved or round 3 completes.
7. If findings remain after round 3, stop and report the remaining issues instead of continuing.

## Reviewer Agent Prompt Shape

Include these constraints when spawning the reviewer:

```text
You are the reviewer in an internal PR review/fix loop. First read ~/.config/opencode/skills/skills/pr-review/REFERENCE.md and apply its shared posture, project facts, review lens, risk map, and structural quality gate. Read the diff from the supplied patch path. Do not edit files and do not submit GitHub comments. Review the current PR/diff for correctness, security, performance, maintainability, operational risk, and missing tests. Return only actionable findings with file/line references, severity (blocking/notable/nit), impact, and suggested smallest fix. Also look for structural simplifications: places where behavior can stay the same while deleting branches, wrappers, duplicated helpers, misplaced logic, or unnecessary state. Treat spaghetti growth and unjustified file-size expansion as actionable findings, not style nits. If prior findings were supplied, verify whether each is fixed. If there are no actionable findings, say so explicitly and list any residual risks or tests you could not run.
```

## Fixer Agent Prompt Shape

Include these constraints when spawning the fixer:

```text
You are the fixer in an internal PR review/fix loop. First read ~/.config/opencode/skills/skills/pr-review/REFERENCE.md so your fixes match the review standard. Address only the supplied reviewer findings. Make the smallest correct code changes, preserve unrelated work, and run targeted verification where feasible. Return the files changed, how each finding was addressed, verification commands and results, and any blockers.
```

## Final Response

Summarize:

- Number of rounds completed.
- Findings fixed.
- Findings still open, if any.
- Verification run and results.
- Files changed.
