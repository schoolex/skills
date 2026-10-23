#!/usr/bin/env bash
# Capture before/after screenshots of a tcs-ui change with one shots spec.
#
#   shoot.sh --spec <shots.spec.ts> [--app core|docs] [--base <ref>] [--out <dir>] [--only before|after]
#   shoot.sh --clean
#
# after  = the current worktree, uncommitted changes included
# before = a throwaway worktree at --base (default: merge-base with origin/main)
#
# Each side runs its own dev server on a free port (strictPort, never reused),
# so a stale server from another worktree can't answer for it.
set -euo pipefail

die() { echo "shoot: $*" >&2; exit 1; }

REPO=$(git rev-parse --show-toplevel 2>/dev/null) || die "run inside a tcs-ui worktree"
[ -f "$REPO/packages/core-app/playwright.config.ts" ] || die "$REPO is not tcs-ui"
SKILL_DIR=$(cd "$(dirname "$0")/.." && pwd)
BRANCH=$(git -C "$REPO" branch --show-current || true)
BRANCH=${BRANCH:-detached}
SLUG=$(printf '%s' "$BRANCH" | tr -c 'A-Za-z0-9._-' '-')
TMP=${TMPDIR:-/tmp}
WORK="${TMP%/}/tcs-ui-shots/$SLUG"
BEFORE_TREE="$WORK/before"

APP=core SPEC="" BASE="" OUT="" ONLY="" CLEAN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --app) APP=$2; shift 2 ;;
    --spec) SPEC=$2; shift 2 ;;
    --base) BASE=$2; shift 2 ;;
    --out) OUT=$2; shift 2 ;;
    --only) ONLY=$2; shift 2 ;;
    --clean) CLEAN=1; shift ;;
    *) die "unknown arg $1" ;;
  esac
done

remove_before_tree() {
  if [ -d "$BEFORE_TREE" ]; then
    git -C "$REPO" worktree remove --force "$BEFORE_TREE" 2>/dev/null || rm -rf "$BEFORE_TREE"
  fi
  git -C "$REPO" worktree prune
}

if [ "$CLEAN" = 1 ]; then
  remove_before_tree
  rm -rf "$WORK"
  echo "shoot: removed $WORK"
  exit 0
fi

case "$APP" in
  core) APP_DIR=packages/core-app; SHOTS_REL=playwright/.shots ;;
  docs) APP_DIR=packages/docs-app; SHOTS_REL=.shots ;;
  *) die "--app must be core or docs" ;;
esac
[ -n "$SPEC" ] && [ -f "$SPEC" ] || die "--spec <file> is required"
SPEC=$(cd "$(dirname "$SPEC")" && pwd)/$(basename "$SPEC")
case "$SPEC" in "$REPO"/*) die "keep the shots spec outside the repo (it is copied in per run)" ;; esac
[ -d "$REPO/node_modules" ] || die "no node_modules in $REPO; run yarn install first"

if [ -z "$BASE" ]; then
  git -C "$REPO" fetch -q origin main || echo "shoot: warning: fetch failed, using cached origin/main" >&2
  BASE=$(git -C "$REPO" merge-base origin/main HEAD)
fi
BASE_SHA=$(git -C "$REPO" rev-parse --short "$BASE^{commit}") || die "bad --base $BASE"
OUT=${OUT:-$HOME/Desktop/pr-shots/$SLUG}
mkdir -p "$OUT" "$WORK"

free_port() { python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1])'; }

# Write the throwaway Playwright config + spec into <tree>/<app>/<shots dir>.
install_shots() {
  local tree=$1 port=$2 dir="$1/$APP_DIR/$SHOTS_REL"
  mkdir -p "$dir"
  cp "$SPEC" "$dir/shots.spec.ts"
  if [ "$APP" = core ]; then
    cat > "$dir/playwright.config.ts" <<EOF
import base from '../../playwright.config';

export default {
  ...base,
  testDir: '.',
  testMatch: 'shots.spec.ts',
  outputDir: '$WORK/test-output',
  retries: 0,
  workers: 1,
  reporter: [['line']],
  use: {...base.use, baseURL: 'http://127.0.0.1:$port', screenshot: 'off'},
  webServer: {
    command: 'node_modules/.bin/vite --host 127.0.0.1 --port $port --strictPort --config vite.test.config.mts',
    cwd: '$tree/$APP_DIR',
    url: 'http://127.0.0.1:$port',
    reuseExistingServer: false,
    timeout: 240000,
    env: {
      BROWSER: 'none',
      REACT_APP_ENV: 'test',
      REACT_APP_ANALYTICS_HOST: 'https://analytics.playwright.test',
      REACT_APP_ANALYTICS_TOKEN: 'phc_playwright_test_token',
    },
  },
};
EOF
  else
    cat > "$dir/playwright.config.ts" <<EOF
import {defineConfig, devices} from '@playwright/test';

export default defineConfig({
  testDir: '.',
  testMatch: 'shots.spec.ts',
  outputDir: '$WORK/test-output',
  timeout: 120000,
  retries: 0,
  workers: 1,
  reporter: [['line']],
  use: {
    ...devices['Desktop Chrome'],
    viewport: {width: 1440, height: 1000},
    baseURL: 'http://127.0.0.1:$port',
  },
  webServer: {
    command: '../../node_modules/.bin/docusaurus start --host 127.0.0.1 --port $port --no-open',
    cwd: '$tree/$APP_DIR',
    url: 'http://127.0.0.1:$port',
    reuseExistingServer: false,
    timeout: 300000,
  },
});
EOF
  fi
}

uninstall_shots() { rm -rf "$1/$APP_DIR/$SHOTS_REL"; }

# Clone node_modules copy-on-write so workspace symlinks (@tcs-ui/common ->
# ../../packages/common) resolve inside the before tree, not the after tree.
prepare_before_tree() {
  if [ -d "$BEFORE_TREE" ] && [ "$(git -C "$BEFORE_TREE" rev-parse --short HEAD 2>/dev/null)" = "$BASE_SHA" ] \
    && [ -d "$BEFORE_TREE/$APP_DIR/node_modules" ]; then
    echo "shoot: reusing before tree at $BASE_SHA"
    return
  fi
  remove_before_tree
  echo "shoot: creating before tree at $BASE_SHA (cloning node_modules, ~40s)"
  local d
  git -C "$REPO" worktree add -q --detach "$BEFORE_TREE" "$BASE_SHA"
  for d in node_modules packages/common/node_modules "$APP_DIR/node_modules"; do
    [ -d "$REPO/$d" ] || continue
    cp -Rc "$REPO/$d" "$BEFORE_TREE/$d" 2>/dev/null || cp -R "$REPO/$d" "$BEFORE_TREE/$d"
  done
  # Gitignored env files (docs-app's docusaurus.config reads packages/docs-app/.env).
  local f
  for f in "$REPO"/.env* "$REPO"/packages/*/.env*; do
    [ -f "$f" ] && cp "$f" "$BEFORE_TREE/${f#"$REPO"/}"
  done
  if ! git -C "$REPO" diff --quiet "$BASE_SHA" HEAD -- yarn.lock; then
    echo "shoot: yarn.lock differs from base; running yarn install in before tree"
    (cd "$BEFORE_TREE" && yarn install >/dev/null)
  fi
}

run_side() {
  local side=$1 tree=$2 port
  port=$(free_port)
  rm -rf "${OUT:?}/$side"
  mkdir -p "$OUT/$side"
  install_shots "$tree" "$port"
  echo "shoot: [$side] $tree on :$port"
  # The tree's own playwright binary: mixing copies breaks test() registration.
  local log="$WORK/$side.log" rc=0
  (cd "$tree/$APP_DIR" && SHOT_DIR="$OUT/$side" "$tree/node_modules/.bin/playwright" test \
    -c "$SHOTS_REL/playwright.config.ts" >"$log" 2>&1) || rc=$?
  grep -vE '^\s*$|\[WebServer\]' "$log" | sed 's/\x1b\[[0-9;]*[A-Za-z]//g' | tail -40
  uninstall_shots "$tree"
  if [ "$rc" != 0 ]; then
    FAILED="$FAILED $side"
    echo "shoot: [$side] FAILED (full log: $log)" >&2
  fi
}
FAILED=""

cleanup() {
  uninstall_shots "$REPO"
  [ -d "$BEFORE_TREE" ] && uninstall_shots "$BEFORE_TREE"
  return 0
}
trap cleanup EXIT INT TERM

[ "$ONLY" != before ] && run_side after "$REPO"
if [ "$ONLY" != after ]; then
  prepare_before_tree
  run_side before "$BEFORE_TREE"
fi

AFTER_LABEL="after: $BRANCH @ $(git -C "$REPO" rev-parse --short HEAD)"
git -C "$REPO" diff --quiet HEAD || AFTER_LABEL="$AFTER_LABEL + uncommitted"
node "$SKILL_DIR/scripts/compose.mjs" "$REPO" "$OUT" "before: $BASE_SHA" "$AFTER_LABEL"
if [ -n "$FAILED" ]; then
  die "spec failed on:$FAILED. A test that fails before its shot() leaves that view unpaired."
fi
