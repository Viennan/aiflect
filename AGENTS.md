# AGENTS.md

## Introduction

This project named `aiflect` defines a general-purpose LLM inference invocation abstraction layer and related adapters, which are used to hide the interface differences of various providers (OpenAI, Anthropic, and others).

## Core Project Directories

- `docs` - Product knowledge base. See [Knowledge Base](#knowledge-base) for organization, maintenance rules, and usage guidance.
- `.devcontainer` - Development container configuration for local and remote development environments.
- `.venv` - The virtual python env for developing and testing python codes and executing python scripts in `scripts` folder.
- `scripts` - Scripts for development, testing, installation, and other automated workflows of this project.
- `asserts` - The asserts (video\audio\image and other kinds of files) for building unittests.
- `TEST.md` - Guidelines for building unittests.
- `python` - Source directory for python implementation version.
  - `whero` - The top domain for this python package. There are other sub-domain packages in their own repositories, which have the same top domain `whero`.
    - `aiflect` - Implementation directory for `aiflect` subdomain.
  - `tests` - All unittests.
  - `pyproject.toml` - For python packaging.

## Knowledge Base

The `docs` directory is the persistent product knowledge base. It records product design, implementation intent, user-facing behavior, and third-party references across sessions and feature work. Its internal structure may evolve, but `docs/INDEX.md` remains the primary entry point for navigation and recall.

### Organization

- `docs/INDEX.md` - Central index and summary for quickly locating knowledge-base documents.
- `docs/requirements` - Requirement management documents, including a lightweight status overview and per-requirement management records. Requirement state belongs here, not in design or implementation documents.
- `docs/design` - High-level design documents, including product design philosophy, module responsibilities, architecture, and development-facing design materials.
- `docs/impls` - Implementation details guided by `docs/design`; organize language-specific implementation documents under language directories such as `docs/impls/python`.
- `docs/user` - User-facing documentation; organize language-specific user documents under language directories such as `docs/user/python`.
- `docs/3rds` - Local snapshots or excerpts of third-party reference materials. These are fact sources for analysis and adapter implementation, not direct product design commitments.
- Each language-specific variant under `docs/impls` or `docs/user` uses its own `STATUS.md` to describe currently implemented features and TODOs.

### Maintenance Rules

- Maintain `docs/INDEX.md` with an index entry and short summary for each knowledge-base document.
- In `docs/design`, make "Design Philosophy" and "Module Responsibilities" clear and explicit. Other sections may be expanded or condensed as appropriate.
- Keep `docs/design` focused on high-level guidance rather than detailed implementation mechanics.
- Place implementation details under `docs/impls` and keep them aligned with the corresponding design documents.
- Place user-facing documentation under `docs/user` when that area is introduced or expanded.
- Track requirement lifecycle state and coarse implementation progress under `docs/requirements`. Design, implementation, and user documents may link to the requirement that introduced a change, but should not carry the requirement's current management state.
- Only maintain requirement records for changes that involve project non-test code. Documentation-only, test-only, workflow-only, or repository housekeeping changes are outside requirement management.
- Keep requirement-management templates in the knowledge base, for example under `docs/requirements`, rather than embedding template details in `AGENTS.md`. Treat templates as adaptable starting points rather than fixed formats.
- When organizing content discussed in `design mode` into the knowledge base, preserve reference links and compile the user's questions into an FAQ.
- Use Markdown links relative to the current document when referencing other documents in the knowledge base. Link text should prefer the target document file name; add the minimal directory prefix when needed to distinguish duplicate file names such as `impls/python/STATUS.md` and `user/python/STATUS.md`.
- When reviewing documents, refer to both design documents and code implementation. If they conflict, notify the user and do not make changes without authorization.
- Do not alter content in the `docs` directory without the user's permission.
- When the user agrees to modify product design, synchronously update the relevant design documents.
- When modifications affect public behavior, synchronously update the relevant user or implementation documents.

### Usage

- `docs/INDEX.md` is a useful starting point when recalling product design, implementation intent, or user-facing behavior.
- Pay close attention to the "Design Philosophy" and "Module Responsibilities" in `docs/design`; they may encode intent that is not obvious from source code alone.
- Use `docs/impls` to recover implementation details, especially subjective decisions, adapter boundaries, and historical implementation rationale.
- During project iteration, `docs/requirements/STATUS.md` can be a useful heuristic entry point for discovering active requirements and their coarse progress. Coding agents should still choose the most relevant documents based on the user's request and local context.
- Treat `docs/3rds` as third-party fact sources. Product semantics should be derived from `docs/design`, not directly from third-party reference snapshots.
- In `design mode`, integrate the current product design and code architecture before giving a research report or proposing a design change.

## Design Mode

`design mode` is an exploratory research mode where you discuss product architecture and brainstorm with the user. When the user asks you to enter `design mode`, please adhere to the following rules:

- In this mode, pay greater attention to the systematic nature and advancement of the design solutions, and identify the semantics and responsibilities of each module.
- Thoroughly understand the user's questions and provide inspiring and constructive feedback in the form of a research report, integrating current product design and code architecture.
- The research report should focus more on high-level design and provide guidance, rather than getting bogged down in specific details.
- Reference and cite authoritative sources when necessary to improve research quality, and provide the sources (links) of references.

## Engineering Rules

### Code Implemetation

- Comments and docstrings must be written in English and must be sufficient to facilitate review.
- The Python language version is the reference implementation of this project. When implementing versions in other languages, their functionality should be aligned with the Python version.
- When developing, follow the principle of first establishing a "mental model" before implementation, which means taking the following steps before coding:
  - A thorough discussion is required, and an implementation plan — including detailed design — should be placed under `docs/impls`.
  - Define the user interface and usage patterns — in other words, the "programming model" — and update them in corresponding user docs (under `docs/user`).
- Prioritize focusing on the features requested by the user in the current session to avoid feature creep.
- When evaluating implementation cost, development efficiency, or delivery difficulty, explicitly factor in the productivity gains provided by AI assistance instead of estimating as if the work were done without AI support.
- If ambiguities are found in the design documents, you may make suggestions and ask for the user's opinion on modifications, but do not change the product direction without authorization.
- If a new proposal would change the core processes, page structure, or product positioning, pause and ask first.
- If the user agrees to modify the design, please synchronously update the relevant design documents.
- When modifications affect public behaviors, synchronously update the relevant documents.

### Testing

- Read `TEST.md` for detailed information about building unittests.

### Asserts

- The `asserts/INDEX.md` contains the textual descriptions of all asserts, which will be maintained by user.
- Read `asserts/INDEX.md` to determine which assert to use when needed.
- Any assert in `assert` should be managed by Git LFS.

### Python Specification

- The Python version used in this project is 3.12. Actively use mature and proven new features to implement functionality, and avoid outdated features with legacy burdens.
- Use `.venv` in the project root as the Python development environment for this project. All Python code, including tests, must be run within this environment and must not pollute the system environment.
- Maintain a `python/pyproject.toml` for packaging, or as a reference for recovering the project-root `.venv`.
