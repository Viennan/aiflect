# AGENTS.md

## Introduction

This project named `vatbrain` defines a general-purpose LLM inference invocation abstraction layer and related adapters, which are used to hide the interface differences of various providers (OpenAI, Anthropic, and others).

## Core Project Directories

- `docs` - The documentation knowledge base for this product. Its internal structure may evolve with the product, but `docs/INDEX.md` should remain the primary entry point for navigating the knowledge base.
  - `user` - Dir for user documents.
  - `design` - Dir for highlevel design documents.
  - `impls` - Dir for lowlevel implementation documents guided by `design` folder.
  - `3rds` - 3rd-party reference docs.
  - `INDEX.md` - Index file for the knowlege base.
- `.devcontainer` - Development container configuration for local and remote development environments.
- `.venv` - The virtual python env for developing and testing python codes and executing python scripts in `scripts` folder.
- `scripts` - Scripts for development, testing, installation, and other automated workflows of this project.
- `asserts` - The asserts (video\audio\image and other kinds of files) for building unittests.
- `TEST.md` - Guidelines for building unittests.
- `python` - Source directory for python implementation version.
  - `whero` - The top domain for this python package. There are other sub-domain packages in their own repositories, which have the same top domain `whero`.
    - `vatbrain` - Implementation directory for `vatbrain` subdomain.
  - `tests` - All unittests.
  - `pyproject.toml` - For python packaging.

## Design Mode

`design mode` is an exploratory research mode where you discuss product architecture and brainstorm with the user. When the user asks you to enter `design mode`, please adhere to the following rules:

- In this mode, pay greater attention to the systematic nature and advancement of the design solutions, and identify the semantics and responsibilities of each module.
- Thoroughly understand the user's questions and provide inspiring and constructive feedback in the form of a research report, integrating current product design and code architecture.
- The research report should focus more on high-level design and provide guidance, rather than getting bogged down in specific details.
- Reference and cite authoritative sources when necessary to improve research quality, and provide the sources (links) of references.

## Doc Maintaining Rules

When maintaining documents in the `docs` directory, the following rules should be followed:

- The `docs` directory serves as the knowledge base for this product. Maintain an index and summary of each document in `docs/INDEX.md` for quick lookup.
- The `docs/design` directory contains the product's design documents, including product design philosophy, module responsibilities (What does this module stand for? More emphasis on high-level semantics.), architecture, and related development-facing materials.
- For docs in `docs/design`, "Design Philosophy" and "Module Responsibilities" are more important things which should be clearly and explicitly, while the other parts can be elaborated or condensed as appropriate.
- Docs in `docs/design` should provide more high-level guidance rather than concrete implementation details, so avoid including too many implementation specifics when updating.
- The `docs/impls` directory contains the implementation details under the guidance of `docs/design`.
- User-facing documentation should live under `docs/user` when that area is introduced or expanded.
- When organizing content discussed in `design mode` into the knowledge base, ensure that reference links are preserved, and compile the user's questions into an FAQ for storage.
- Use base file name or full name up to `docs` dir (should be clean and not including `docs`) with its relative path (comparing to `docs`) as the linking url to reference other doc in the knowlege base.
- When reviewing documents, refer to both design documents and code implementation. In case of conflicts, notify the user and do not make changes without authorization.
- Do not alter the content in the `docs` directory without the user's permission.
- Organize files under the `docs/impl` and `docs/user` directories based on programming language dimensions.
- Each language-specific variant uses its own `STATUS.md` to describe the currently implemented features and TODOs.

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

## Recommendations

- Consider the documentation under `docs` as a persistent, global memory pool for recall designations and implementation specifics across different sessions and feature development processes.
- Use `docs/INDEX.md` to quickly recall the product design and use it as an index to load other documents as needed.
- Pay great attention to the "Design Philosophy" and "Module Resposibilites" in docs of `docs/design`, which may not be clearly infered only from code.
- The files under `docs/impls` are invaluable for recalling implementation details, particularly those involving subjective intent, when the source code alone proves insufficient or ambiguous.
