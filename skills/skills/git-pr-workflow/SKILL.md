---
name: git-pr-workflow
description: Commit changes to a new branch, push to all remotes, and create a PR from the repo template with labels and assignee. Use when the user says "create a PR", "commit and push", or "raise a PR".
---

This skill commits changes, pushes them, and opens a pull request from the repository's PR template.

## CRITICAL: Never post test content to real PRs

An agent once spammed dsaidgovsg/tcs-ui#2603 with 18 test reviews. To prevent a repeat:

1. Never test review or comment posting on a real PR. Use a dry run (`submit_review.py --dry-run`) instead.
2. Before any `gh pr review` or `gh pr comment`, the content must be final and the PR number explicitly confirmed. Don't reuse a PR number from earlier in the conversation without checking it.
3. "Test" content is never acceptable on a real PR.

## Steps

### 1. Preflight (one batch)

```sh
git status --short; git branch --show-current; git log --oneline -10
git remote -v
ssh-add -l >/dev/null 2>&1 || ssh-add --apple-use-keychain ~/.ssh/id_ed25519   # avoids "Permission denied (publickey)" on push
```

### 2. Create a branch off the default branch

New work branches from the latest default branch (`main` in tcs-ui, `master` in tcs-core), **not** from whatever branch is checked out:

```sh
git fetch origin && git switch -c <type>--<description> origin/<default>
```

- Types are `feat--`, `chore--` and `fix--`, with a double hyphen (not an em dash).
- If the change is already on another branch, carry over only the relevant commits or files. Then check `git diff origin/<default>...HEAD --stat` to confirm there are no unrelated changes.

### 3. Commit

```sh
git add <files>
git commit -S -m "<type>(<scope>): <description>"
```

- Pre-commit hooks lint every `.md` and `.ts` file in the worktree. Fix the lint errors rather than bypassing them.
- Use `--no-verify` only when a hook fails for an unrelated environment reason, such as the Docker daemon not running. Tell the user when you do.

### 4. Push to every remote, before creating the PR

```sh
git push -u origin HEAD
git remote | grep -qx gitlab && git push gitlab HEAD
```

`gh pr create` aborts if the branch hasn't been pushed. If the push fails with `Permission denied (publickey)`, rerun the `ssh-add` line from step 1 and retry once. If it still fails, stop and tell the user.

### 5. Create the PR

Read `.github/pull_request_template.md`, then:

```sh
gh pr create --base <default> --title "<type>(<scope>): <short, general title>" --body-file /tmp/pr-body.md
```

Body rules, based on repeated user edits:

- Make the **Description** and **Motivation** concise and high level, around three lines each. Leave out implementation details.
- Write it from the whole branch diff (`git diff origin/<default>...HEAD`), not from the last commit.
- Linked Issues: use `Relates to #<n>` when there's an issue, otherwise `N/A`.
- **How Has This Been Tested:** leave it for the human, unless the user gave the testing steps. Never cite unit tests.
- Checklist:

```markdown
- [x] I have performed a review of my changes locally
- [x] I have checked that no sensitive data is committed in the git history
- [ ] I have checked that the correct labels are applied to the PR
- [x] I have added comments if my changes contain hard-to-understand logic
- [ ] I have added tests and/or detailed the steps to verify that my changes are correct
- [x] I have updated any documentation if required
```

### 6. Labels and assignee (one call)

```sh
gh pr edit <n> --add-label <labels> --add-assignee @me
```

Choose labels from the branch prefix: `feat--` gets `feat`, `chore--` gets `chore`, and `fix--` gets `fix,bug`.

### 7. PR comments

- Write multi-line comments through a file or stdin (`gh pr comment <n> --body-file -`). Never put escaped `\n` in `--body`.
- To fix a badly formatted comment, run `gh pr comment <n> --edit-last --body-file -`.
- Don't cite unit tests as verification.

## Common issues

| Symptom | Fix |
|---|---|
| `Permission denied (publickey)` | `ssh-add --apple-use-keychain ~/.ssh/id_ed25519`, then retry |
| `you must first push the current branch` | Push first (step 4) |
| "Commits must have verified signatures" | Re-sign with `git rebase --exec 'git commit --amend --no-edit -S' origin/<default>`, then `push --force-with-lease`, but ask the user first |
| GPG signing fails | Check `gpg --list-secret-keys`; `gh gpg-key list` needs `gh auth refresh -s read:gpg_key` |
| PR diff shows unrelated changes | The branch was cut from the wrong base. Recreate it from `origin/<default>` (step 2) |
