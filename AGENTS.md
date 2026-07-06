# AGENTS.md

## Project

`aiflect` is a general-purpose LLM inference invocation abstraction layer. It
hides interface differences across providers such as OpenAI, Anthropic,
Volcengine, DeepSeek, and other compatible backends.

## Agent Operating Model

Use this file as the stable repository entry point. Keep task-specific
procedures in `.agents/skills` and load the relevant skill before acting on a
specialized workflow.

- Load `.agents/skills/aiflect-implementation` before implementing, reviewing,
  or planning non-test code changes.
- Load `.agents/skills/aiflect-knowledge-base` before working in `docs`,
  entering `design mode`, updating requirements, or reconciling design and code.
- Load `.agents/skills/aiflect-testing` before adding, running, or diagnosing
  tests, including costly provider tests.
- Prefer `rg` and `rg --files` for repository search.
- Keep edits scoped to the current user request and existing project patterns.
- Do not revert user or generated worktree changes unless explicitly asked.
- Do not perform local merge operations involving `main` unless the user
  explicitly commands them.

## Core Directories

- `.agents/skills` - Repository-local agent skills. Detailed development,
  maintenance, and testing workflows live here.
- `.devcontainer` - Development container configuration.
- `.venv` - Project-root Python development environment for local scripts,
  packaging, and tests.
- `asserts` - Test assertion assets. The user maintains `asserts/INDEX.md`.
- `docs` - Product knowledge base. Start from `docs/INDEX.md` when product
  design, implementation intent, or user-facing behavior matters.
- `python` - Python reference implementation.
  - `python/whero/aiflect` - Package implementation.
  - `python/tests` - Unit and costly tests.
  - `python/pyproject.toml` - Packaging and pytest configuration.
- `scripts` - Development, diagnostic, testing, and installation scripts.

## Repository Invariants

- Python 3.12 is the reference implementation target.
- Use the project-root `.venv` for Python commands; do not install dependencies
  into the system environment for this project.
- Comments and docstrings must be written in English and be sufficient for
  review.
- The Python implementation is the behavioral reference for other language
  implementations.
- Do not run live provider, network, credentialed, or billable tests unless the
  user explicitly asks for them.
- For new implementation work, follow the branch workflow in
  `.agents/skills/aiflect-implementation`: sync/check `main`, create a feature
  branch from updated `main`, and ask before continuing on a non-`main` branch
  unless the user explicitly named that branch.
- When creating a remote PR or MR, include a description summary whenever the
  platform supports one. If the summary cannot be attached directly, include a
  copyable summary in the final response and use PR/MR-renderable documentation
  links.
- Do not modify files under `docs` unless the user request includes that work or
  the user grants permission. If design documents and code conflict, report the
  conflict before changing direction.

## Skill Maintenance

When a recurring agent workflow grows beyond a short routing rule, create or
update a skill under `.agents/skills/<skill-name>/SKILL.md` instead of expanding
this file. Keep skill frontmatter accurate because it is the trigger surface for
future agents.
