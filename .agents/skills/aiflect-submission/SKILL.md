---
name: aiflect-submission
description: Use when committing, pushing, submitting to a remote, creating or updating a PR/MR, or preparing PR/MR descriptions for aiflect work. Covers final diff review, validation reporting, scoped staging, commit creation, branch push, GitHub/GitLab PR/MR creation attempts, mandatory copyable descriptions when remote tools are unavailable, and final submission checklists.
---

# Aiflect Submission

## Purpose

Use this skill after implementation or documentation work is ready to submit. Keep the workflow low freedom: verify, commit, push, create or prepare PR/MR, then report all submission artifacts.

## Workflow

1. Inspect submission state:
   - Run `git status --short --branch`.
   - Review `git diff --stat` and focused diffs for changed files.
   - Confirm no unrelated user changes are being staged.
2. Verify before committing:
   - Run `git diff --check`.
   - Reuse the latest relevant validation only if it still covers the current diff; otherwise run the focused tests required by the change.
   - Never run live provider, credentialed, network, or billable tests without explicit user approval.
3. Commit:
   - Stage only files in scope.
   - Use a concise imperative commit message.
   - After committing, record `git rev-parse HEAD`.
4. Push:
   - Push the current branch to the appropriate remote with upstream tracking when needed.
   - Do not merge into `main` or merge `main` into the branch unless the user explicitly asks.
5. Prepare PR/MR description before the final response:
   - Include `Summary`, `Validation`, and `Docs` sections when applicable.
   - For GitHub documentation links, use full URLs pinned to the final commit SHA.
   - If the remote tool creates the PR/MR with a body, still record the body in the final summary if useful.
6. Create or prepare PR/MR:
   - Prefer `gh pr create` for GitHub when available and authenticated.
   - If no remote PR/MR tool or token is available, use the push output or remote URL to provide a PR creation link and a copyable description block.

## Final Response Checklist

Always include:

- Commit SHA.
- Branch and push status.
- PR/MR URL, or the PR/MR creation URL when the remote object could not be created.
- Validation commands and results.
- Whether the PR/MR description was attached directly or is provided as a copyable block.

When no PR/MR object was created, include a fenced `md` block containing the complete copyable PR/MR description.

## PR/MR Description Template

```md
## Summary

- ...

## Validation

- `command`
- Result: ...

## Docs

- [doc-name](https://github.com/<owner>/<repo>/blob/<commit-sha>/path/to/doc.md)
```

Omit empty sections only when they truly do not apply.
