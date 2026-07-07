---
name: aiflect-implementation
description: Use when implementing, modifying, or reviewing aiflect non-test code, provider adapters, public Python APIs, packaging, scripts, Git branch setup, or behavior changes, especially when carrying an accepted design into code. Covers mental-model-first development, main-branch synchronization, feature branches, Python 3.12 conventions, docs checkpoints, provider-boundary expectations, and scoped implementation practice. For architecture/design planning load aiflect-design; for commit, push, remote submission, or PR/MR description work, load aiflect-submission.
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
   - Load `$aiflect-design` when the implementation depends on architecture,
     public API direction, provider-neutral contracts, or tradeoff decisions
     that are not already accepted.
   - Load `$aiflect-knowledge-base` when product design, implementation intent,
     user-facing behavior, requirements, or `docs` content may affect the
     change.
3. Define the smallest useful change:
   - Prioritize the feature or fix requested in the current session.
   - Avoid feature creep and unrelated refactors.
   - If a proposal would change core processes, public API shape, package
     structure, or product positioning, pause and ask first.
   - If the user provided or accepted a design, implement inside that scope
     instead of reopening settled design choices.
4. Implement in the existing style:
   - Prefer local helpers, types, and adapter patterns already used in the
     repository.
   - Use structured APIs or parsers instead of ad hoc string manipulation when a
     reasonable option exists.
   - Add abstractions only when they remove real complexity, reduce meaningful
     duplication, or match an established local pattern.
   - Write comments and docstrings in English; keep them useful for review.
   - Keep docs updates, when needed, inside the current request or accepted
     design scope.
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

For non-test code changes, decide whether repository knowledge should be read or
updated:

- Requirements and coarse implementation progress belong under
  `docs/requirements`.
- High-level product architecture and module responsibilities belong under
  `docs/design`.
- Implementation details belong under `docs/impls`, organized by language when
  appropriate.
- User-facing behavior belongs under `docs/user`, organized by language when
  appropriate.

Do not treat implementation as docs-free work. Read `docs` when the change
depends on design philosophy, historical reasoning, user-facing intent,
implementation progress, or long-term planning that code alone cannot express.

Docs may be modified during implementation when the current request, an
accepted design, or the implemented behavior requires that change. Keep those
updates focused; do not make opportunistic docs changes outside the active
design or implementation scope.

When implementation evidence shows that the accepted design needs adjustment, or
that the change unexpectedly affects existing design, public behavior, or
product direction, pause and ask the user before changing direction. When
documentation updates are needed, load `$aiflect-knowledge-base` and keep
`docs/INDEX.md` aligned.

## Assets and Credentials

- Use `asserts` only through the testing workflow and consult
  `asserts/INDEX.md` before selecting assets.
- Never commit or persist provider API keys, access tokens, secret keys, refresh
  tokens, or session credentials.
- Prefer local fakes, fixtures, and static assertions over live provider calls
  during implementation.
