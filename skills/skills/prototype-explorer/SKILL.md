---
name: prototype-explorer
description: Turn a static HTML artifact (a report, diagram, event graph, catalog, or dataset dump) into a single-file interactive explorer, verify it in a headless browser, and capture it on a throwaway `prototypes` branch. Use when the user asks to extract part of a generated HTML page and "make it interactive", "give it a nice UI", or "make it explorable".
---

# Prototype Explorer

An **explorer** is a self-contained HTML file built around one dataset you can pan, filter, search and inspect. It is a third shape of [prototype](../prototype/SKILL.md): it reuses that skill's rules (throwaway, trivial to run, surface the state, capture on a branch) and its single-file format from [LOGIC.md](../prototype/LOGIC.md). The question it answers is "what does this data look like when I can poke at it?"

The source is usually an HTML file an agent wrote earlier (for example an `explain-diff-html` output in `/tmp`). Those files get deleted, so the first job is to rescue the data.

## Steps

### 1. Locate the source and isolate the data

Find the file. `file://` URLs map to a plain path, and on macOS `/tmp` is `/private/tmp`. Read it whole, then find the **data block**: the plain JS constants (or embedded JSON) that the page renders from. List the constants and their line range.

Done when: you can name every constant the target view needs, and none of them touch the DOM.

### 2. Plan the scope in one line

Write down what the explorer keeps and what it drops. Example: "Graph only: lanes, nodes, links, detail drawer; drop the prose, the join examples and the catalog." If the user said "just the X part", everything outside X goes, except data that X's detail view needs.

### 3. Build it as shell + app + verbatim data

Write the file in three parts and assemble them with a short script. Long single-file writes can fail when the tool's JSON payload gets too large.

- `shell.html`: markup and CSS, with `/*__DATA__*/` and `/*__APP__*/` placeholders.
- `app.js`: all behaviour.
- The data: **sliced verbatim** from the source by line range (assert the first and last lines), never retyped. Retyping data is where silent drift comes from.

Put the parts in a temp directory and write the assembled file to its destination. Then pick the features from [EXPLORER.md](EXPLORER.md). The non-negotiables are listed there.

Done when: the assembled file opens by double-click with no network requests.

### 4. Verify in a headless browser, then look at it

Copy [verify.example.js](verify.example.js), point it at the file, and adapt the selectors. Use Playwright from any `node_modules` that already has it (in tcs-ui that is the worktree root). The script must:

- collect `pageerror` and console `error`/`warning` messages; the target is **zero**;
- check every interaction in your feature list (search → select, filter toggles, depth or neighbourhood highlight, jump links, Esc, zoom, theme, deep-link reload);
- save a screenshot of each of these states: overview, selected, dark theme, deep link.

Then **read the screenshots**. Problems that only show when you look at them: the default zoom is too far out to read, the minimap hides content, a search highlight stays after a selection, labels collide. Fix them, rebuild, and run the script again.

Done when: zero errors, every assertion holds, and every screenshot is readable at its default zoom.

### 5. Capture it on the `prototypes` branch

This is the prototype skill's capture rule, applied to repos:

- If a branch called `prototypes` already exists, add to it. Otherwise create it from the latest default branch (`git fetch origin main`, then branch from `origin/main`).
- If the current worktree has uncommitted changes, never switch branches in it. Use `git worktree add -b prototypes <sibling-dir> origin/main --no-track`.
- Put files in `prototypes/` at the repo root. Keep the original source next to the explorer so the data has a primary source.
- Pre-commit hooks in a fresh worktree need dependencies. Run the project's install command (`yarn install`) and commit again. Never pass `--no-verify`.
- Push to every remote the project's notes say to push to (tcs-ui: `origin` and `gitlab`).

Done when: the commit is on both remotes, and you have told the user the file path and opened it (`open <path>`).

## Hand over

Report the path, the branch, and the commit. List the features in a few bullets and give the keyboard shortcuts. Say which defaults you chose after looking at the screenshots (for example "fit to width, not fit all"), so the user can overrule them.
