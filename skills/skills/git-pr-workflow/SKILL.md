---
name: git-pr-workflow
description: Commit staged changes to new branch and create PR with template
---

This skill handles committing staged changes, pushing to remote, and creating a pull request using the repository's PR template.

## Steps

### 1. Git Setup
- Check git status: `git status`
- View recent commits for style: `git log --oneline -10`

### 2. Create Branch
- Create branch: `git checkout -b <type>--<description>`
- Types: `feat--`, `chore--`, `fix--` (double hyphens, NOT em dashes)

### 3. Commit
- Check what's staged: `git status`
- Commit with conventional format and sign: `git commit -S -m "chore: <description>"`
- If pre-commit hooks fail due to Node version mismatch, bypass with: `git commit --no-verify -S -m "chore: <description>"`

### 4. Push
- Push and track: `git push -u origin <branch-name>`

### 5. Create PR
- Read PR template: `.github/pull_request_template.md`
- Get assignee from org members: `gh api orgs/<org>/members --jq '.[].login'`
  - For dsaidgovsg: `gh api orgs/dsaidgovsg/members --jq '.[].login'`
- Create PR:
  ```
  gh pr create \
    --title "<title>" \
    --body "$(cat <<'EOF'
  ## Description
  
  <description>
  
  ## Motivation and Context
  
  <why needed>
  
  ## Linked Issues
  
  N/A
  
  ## How Has This Been Tested
  
  <!-- DO NOT fill this in - human will manually describe testing -->
  
  ## Checklist
  
  - [x] I have performed a review of my changes locally
  - [x] I have checked that no sensitive data is committed in the git history
  - [ ] I have checked that the correct labels are applied to the PR
  - [x] I have added comments if my changes contain hard-to-understand logic
  - [ ] I have added tests and/or detailed the steps to verify that my changes are correct
  - [x] I have updated any documentation if required
  EOF
  )"
  ```

### 6. Add Labels
- Determine labels based on branch prefix:
  - `feat--` → add `feat` label
  - `chore--` → add `chore` label
  - `fix--` → add `fix`, `bug` labels
- Add labels: `gh pr edit <pr-number> --add-label <label1>,<label2>`

### 7. Assign Reviewer
- Get current user: `gh api user --jq '.login'`
- Add assignee: `gh pr edit <pr-number> --add-assignee <username>` (use 'me' from previous step)

### 8. Respond To PR Comments
- For multi-line PR comments, use stdin or a temporary body file with `gh pr comment --body-file -`; do not put escaped `\n` sequences inside `--body`.
- Use Markdown formatting with real blank lines between paragraphs and lists.
- Do not cite unit tests as verification in PR comments; mention only non-test validation, manual verification, or omit verification unless the user explicitly asks.

## Common Issues
- Node version mismatch: use `--no-verify`
- Assignee not found: verify username with `gh api orgs/<org>/members`
- Labels: `feat--` → feat, `chore--` → chore, `fix--` → fix,bug
- GPG signing fails: ensure you have a GPG key set up (`gpg --list-keys`) and added to GitHub (`gh auth status`)
- Bad PR comment formatting: edit the last comment with `gh pr comment <number> --edit-last --body-file -` and provide properly formatted Markdown through stdin.
