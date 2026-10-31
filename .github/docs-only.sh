#!/usr/bin/env bash
# Prints docs_only=true to $GITHUB_OUTPUT when a pull request changes nothing but
# README.md, CLAUDE.md, CHANGELOG.md and docs/**, so browser.yml can skip its install
# and test steps. The job still runs and reports success: `interaction` is a required
# check on main, and a required check that never reports (a path-filtered workflow)
# blocks the merge. Copied from helping-ai-workflow/md2doc, allow-list re-checked here.
#
# An allow-list, not a deny-list: any other path runs the full suite. Each entry was
# checked with grep: nothing under tests_browser/ or scripts/ reads it, and
# tests/test_browser_workflow.py asks this script about every module the page loads.
# ci.yml does not use it: the unit suite reads every one of these files (README by the
# freshness tests, CHANGELOG by the version tests, every tracked text file by
# test_privacy and test_no_merge_markers), so a docs-only PR still needs `test`.
#
# On pull_request the checkout is the PR's merge commit, so HEAD^1 is the tip of the
# base branch and the diff is exactly what the PR changes (needs fetch-depth: 2).
# Anything else (workflow_dispatch) runs the full suite. CHANGED_FILES overrides the
# diff for the test.
set -euo pipefail

docs_only=false
if [ "${EVENT_NAME:-}" = pull_request ]; then
  files=${CHANGED_FILES-$(git diff --name-only HEAD^1 HEAD)}
  echo "changed files:"
  echo "$files"
  if [ -n "$files" ] && ! grep -vqE '^(README\.md|CLAUDE\.md|CHANGELOG\.md|docs/.+)$' <<<"$files"; then
    docs_only=true
  fi
fi
echo "docs_only=$docs_only"
echo "docs_only=$docs_only" >> "${GITHUB_OUTPUT:-/dev/null}"
