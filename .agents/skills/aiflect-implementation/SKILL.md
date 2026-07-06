---
name: aiflect-implementation
description: Use when implementing, modifying, reviewing, or planning aiflect non-test code, provider adapters, public Python APIs, packaging, scripts, Git branch setup, or behavior changes. Covers the mental-model-first development workflow, main-branch synchronization, feature branch creation, Python 3.12 conventions, documentation checkpoints, provider-boundary expectations, and scoped implementation practice. For commit, push, remote submission, or PR/MR description work, load aiflect-submission.
---

# Aiflect Implementation

## Workflow

1. Establish the Git baseline before implementing a new requirement:
   - Inspect the current branch and worktree.
   - Follow the branch workflow below unless the user explicitly named a
     development branch.
2. Build a mental model before editing:
   - Read the relevant source files and nearby tests.
   - Read `python/pyproject.toml` when dependencies, packaging, or pytest
     behavior may matter.
   - Load `$aiflect-knowledge-base` when product design, user-facing behavior,
     requirements, or `docs` content may affect the change.
3. Define the smallest useful change:
   - Prioritize the feature or fix requested in the current session.
   - Avoid feature creep and unrelated refactors.
   - If a proposal would change core processes, public API shape, package
     structure, or product positioning, pause and ask first.
4. Implement in the existing style:
   - Prefer local helpers, types, and adapter patterns already used in the
     repository.
   - Use structured APIs or parsers instead of ad hoc string manipulation when a
     reasonable option exists.
   - Add abstractions only when they remove real complexity, reduce meaningful
     duplication, or match an established local pattern.
   - Write comments and docstrings in English; keep them useful for review.
5. Verify with the relevant test workflow:
   - Load `$aiflect-testing` before adding, running, or diagnosing tests.
   - Do not run live provider, credentialed, network, or billable checks unless
     the user explicitly asks.
6. When the user asks to commit, push, submit to a remote, or create/update a
   PR/MR, load `$aiflect-submission` and follow that submission checklist.

## Git Branching and Remote Workflow

For new implementation requirements, work from an updated `main` branch unless
the user explicitly specifies a development branch.

- If the user names a development branch, use that branch and do not create a
  different one unless the user asks.
- If the current branch is `main`, immediately update or check it against the
  remote before creating work:
  - Prefer `git fetch` followed by `git pull --ff-only` when the worktree and
    repository policy allow it.
  - If pulling is unsafe or unavailable, inspect remote status instead, for
    example with `git fetch`, `git status`, and the relevant upstream comparison.
  - Create a new feature branch from the updated or checked `main` before
    editing.
- If the current branch is not `main` and the user did not specify a development
  branch, ask whether to continue development on the current branch before
  editing.
- Never perform local merge operations involving `main` automatically. This
  includes merging `main` or `origin/main` into a feature branch, and merging a
  feature branch into `main`. Do so only when the user explicitly commands that
  merge.
- Do not hide branch uncertainty. If local changes, missing upstreams, or
  detached HEAD state make the safe path unclear, explain the state and ask
  before switching branches or altering history.

Submission to a remote hosting system such as GitHub, GitLab, or a similar
forge is owned by `$aiflect-submission`. Load it before staging, committing,
pushing, creating a PR/MR, or preparing a PR/MR description.

## Python Reference Implementation

- Treat `python/whero/aiflect` as the reference implementation for project
  behavior.
- Use Python 3.12 features where they improve clarity and avoid legacy burden.
- Use the project-root virtual environment for all Python commands:

```bash
.venv/bin/python -m pip install -e "python[test]"
```

From the Python project directory, use:

```bash
../.venv/bin/python -m pytest
```

- Keep provider-neutral contracts in `whero.aiflect.core`.
- Keep provider-specific request/response mapping, capability handling, and
  SDK details under the matching `whero.aiflect.providers.<provider>` package.
- Do not assume a model supports a capability merely because its provider
  supports it; consult or extend capability metadata.

## Documentation Checkpoints

For non-test code changes, decide whether repository knowledge must be updated:

- Requirements and coarse implementation progress belong under
  `docs/requirements`.
- High-level product architecture and module responsibilities belong under
  `docs/design`.
- Implementation details belong under `docs/impls`, organized by language when
  appropriate.
- User-facing behavior belongs under `docs/user`, organized by language when
  appropriate.

Only modify `docs` when the user request includes that work or the user grants
permission. When documentation updates are needed, load `$aiflect-knowledge-base`
and keep `docs/INDEX.md` aligned.

## Assets and Credentials

- Use `asserts` only through the testing workflow and consult
  `asserts/INDEX.md` before selecting assets.
- Never commit or persist provider API keys, access tokens, secret keys, refresh
  tokens, or session credentials.
- Prefer local fakes, fixtures, and static assertions over live provider calls
  during implementation.
