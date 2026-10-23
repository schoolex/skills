---
name: tcs-ui-feature
description: Use when implementing a feature, fix, or copy/wording change in tcs-ui (core-app or docs-app) that will go out as a PR. Also use when the user asks for before/after screenshots of a tcs-ui change.
---

# tcs-ui feature workflow

Every change ships with an **evidence pair**: a before and an after screenshot of each changed view. They're rendered from the same fixture data, so a human can confirm the change by eye. Get the evidence pair in front of the user before the PR goes up, and put it in the PR body.

## Steps

### 1. Branch

```sh
git fetch origin && git switch -c <type>--<slug> origin/main
```

`<type>` is `feat`, `fix` or `chore` (or `docs`). Pick a real slug yourself. Never leave a placeholder like `xxx`. Base the branch on `origin/main` even when another branch is checked out. Stacked work is the only exception: base it on the parent branch and pass that as `--base` in step 4.

**Done when** `git merge-base --is-ancestor origin/main HEAD` succeeds and the branch name has no placeholder.

### 2. Scope the change

The change covers exactly what was asked. Before editing:

- **Copy changes:** apply the user's text verbatim. Keep every existing term the user didn't ask to change, e.g. leave `purpose` alone rather than writing `purpose(s)`. Grep `packages/` for every occurrence of the old string: core-app, nge2g-app, docs-app, PDF templates and Playwright assertions. Change each one that refers to the same thing.
- **Payload or field changes:** check tcs-core for consumers of that field and report any breaking change before you write code.
- **UI:** reuse the existing component and layout pattern for that kind of element on the page, e.g. the download menu, or how a neighbouring row places its actions. Name the precedent you followed.

**Done when** you can list every file you'll touch and say why each is in scope.

### 3. Implement and test

- If behaviour changes, add or extend a Playwright spec next to the existing one for that page. If only copy changes, update the existing assertions on the old string. Skip new tests if the user says so.
- Run the specs you touched: `yarn workspace @tcs-ui/core-app playwright test --project=integration-chromium <spec>`. Also run `bash ./scripts/checkTypescript.sh`, plus `yarn lint` (which also checks `.md`/`.mdx`).

**Done when** the touched specs, the type check and lint all pass.

### 4. Capture the evidence pair

1. Pick the views. One view for each place the change renders: form, detail page, approval accordion, docs section. For a hidden-state change, add a view for the state where it shows.
2. Write a **shots spec** in `$TMPDIR`, never in the repo. Start from [templates/core.shots.spec.ts](templates/core.shots.spec.ts) or [templates/docs.shots.spec.ts](templates/docs.shots.spec.ts). Follow the rules in [Shots spec rules](#shots-spec-rules).
3. Run it:

   ```sh
   ~/.agents/skills/skills/tcs-ui-feature/scripts/shoot.sh --spec $TMPDIR/<slug>.shots.spec.ts [--app docs] [--base <ref>]
   ```

   The script shoots the "after" side from the current worktree, including uncommitted edits. It shoots the "before" side from a throwaway worktree at the merge-base with `origin/main`. Each side runs its own dev server on a free port. For each view it writes `<view>.compare.png` (labelled side by side) and an `index.html` to `~/Desktop/pr-shots/<branch>/`. It exits non-zero if either side's spec failed.
4. Read every `compare.png` yourself. Check that the after side shows the change, the before side shows the old state, and both sides crop the same region with fonts loaded. Check the fixture too: it should match what the user saw or reported. If they shared a screenshot, the before side should look like it, e.g. `Yes. as above`, not just `Yes.`. Fix the spec and rerun if any check fails.
5. Show the user each pair inline, with one line per view saying what changed, then `open ~/Desktop/pr-shots/<branch>/index.html`.

**Done when** every view from step 4.1 has a `compare.png` marked `pair` (or `after only` for a view that is new by design), and you've read each one.

If the change has nothing visible (CI, config, pure refactor), the evidence pair is a failing-then-passing test run or a command's output before and after. Say which you used.

### 5. Commit, push, PR

Follow the `git-pr-workflow` skill for commits, pushing to both `origin` and `gitlab`, the PR template and labels. Fill the template's **Screenshots** section with one heading per view and a placeholder line:

```markdown
## Screenshots

**DR detail page: legal ground**
<!-- paste 01-detail-legal-ground.compare.png -->
```

Then hand over the images. GitHub has no API for uploading images to a PR body, so the user drags them in:

```sh
open ~/Desktop/pr-shots/<branch>/ && open "$(gh pr view --json url -q .url)"
```

Tell the user which file goes under which heading.

**Done when** the PR exists, both remotes have the branch, and the Screenshots section has a placeholder for every `compare.png`.

### 6. Iterate

After any follow-up commit that changes rendering, rerun step 4 (the before tree is reused, so it takes about 30s). Show the new pairs and tell the user which PR images to replace. After the PR merges, or when you're done with the branch, run `shoot.sh --clean`.

## Shots spec rules

The script copies the same spec into both trees: `packages/core-app/playwright/.shots/` or `packages/docs-app/.shots/`. That means:

- **Imports must exist at the base commit.** Use `../fixtures/...`, `../integration/pages/.../*Helpers`, `../utils/...` and `src/...`. Build fixture data inline in the spec. Don't import fixtures the branch added.
- **Anchor on something both sides render:** an existing test ID, heading, label, or the section that contains the change. Never anchor on a test ID this change introduces. For a newly added element, shoot its parent section so the before side has a matching view.
- **The file name is the pairing key.** Use the same `shot(..., '<nn>-<view>')` name on both sides, numbered in PR order.
- **Use the same fixture on both sides.** Turn on any feature flag the change sits behind for both sides.
- **Use `shot()` from the template.** It waits for fonts, crops to the target plus padding, and corrects for scroll offset.
- **docs-app pages:** wait for the specific element plus `networkidle` (the first paint is the page shell), then shoot the changed table or section.

## Script troubleshooting

| Symptom | Cause / fix |
|---|---|
| `test() to be called here` | Two Playwright copies. The script uses each tree's own binary; don't call one tree's Playwright on the other. |
| Before side `webServer was not able to start` | Read `$TMPDIR/tcs-ui-shots/<branch>/before.log`. For docs, a missing `packages/docs-app/.env` (the script copies `.env*` from the current tree). |
| Before side fails on an import | The spec imports something the base doesn't have. Inline it. |
| `yarn.lock differs from base` takes minutes | Expected: the before tree needs its own install. |
| Stale before tree after a rebase | It's keyed by base SHA and rebuilt automatically. `--clean` forces a rebuild. |
