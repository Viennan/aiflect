---
name: aiflect-knowledge-base
description: Use when reading, maintaining, or reconciling the aiflect knowledge base under docs; when the user requests design mode; when requirements, design records, implementation notes, user docs, third-party references, or public-behavior documentation may need to be created or updated.
---

# Aiflect Knowledge Base

## Entry Points

- Start with `docs/INDEX.md` to locate current knowledge-base documents.
- Use `docs/requirements/STATUS.md` to understand requirement lifecycle state
  and coarse implementation progress.
- Read relevant `docs/design` documents before changing architecture,
  responsibilities, or product semantics.
- Read relevant `docs/impls` and `docs/user` documents when implementation
  details or public behavior matter.
- Treat `docs/3rds` as third-party fact sources, not direct product design
  commitments.

## Maintenance Workflow

1. Confirm the user request includes documentation work or that the user has
   granted permission to modify `docs`.
2. Read `docs/INDEX.md` and the smallest relevant set of knowledge-base files.
3. Compare the documents with current code when reviewing or updating design and
   implementation claims.
4. If documents and code conflict, notify the user and do not change product
   direction without authorization.
5. Make focused updates in the document category that owns the information.
6. Keep `docs/INDEX.md` aligned with every created, removed, or materially
   changed knowledge-base document.

## Knowledge-Base Organization

- `docs/INDEX.md` - Central index and short summaries for navigation.
- `docs/requirements` - Requirement management records and lifecycle state.
  Requirement state belongs here, not in design or implementation documents.
- `docs/design` - High-level design philosophy, module responsibilities,
  architecture, and development-facing design guidance.
- `docs/impls` - Implementation details guided by design documents; organize
  language-specific content under directories such as `docs/impls/python`.
- `docs/user` - User-facing documentation; organize language-specific content
  under directories such as `docs/user/python`.
- `docs/3rds` - Local snapshots or excerpts of third-party references.

Each language-specific variant under `docs/impls` or `docs/user` may use its own
`STATUS.md` to describe implemented features and TODOs.

## Requirement Management

- Maintain requirement records only for changes involving project non-test code.
- Documentation-only, test-only, workflow-only, and repository housekeeping
  changes are outside requirement management.
- Keep requirement-management templates in the knowledge base, for example under
  `docs/requirements`, rather than embedding templates in `AGENTS.md`.
- Treat templates as adaptable starting points.

## Design Documents

- Make "Design Philosophy" and "Module Responsibilities" clear and explicit in
  design documents.
- Keep `docs/design` focused on high-level guidance rather than detailed
  implementation mechanics.
- When the user agrees to modify product design, synchronously update the
  relevant design documents.
- When organizing content discussed in `design mode`, preserve reference links
  and compile the user's questions into an FAQ.

## Implementation and User Documents

- Place implementation details under `docs/impls` and keep them aligned with the
  corresponding design documents.
- Place user-facing documentation under `docs/user` when that area is introduced
  or expanded.
- When modifications affect public behavior and documentation updates are
  authorized, synchronously update the relevant user or implementation
  documents.

## Link Style

- Use Markdown links relative to the current document when referencing other
  knowledge-base documents.
- Prefer the target filename as link text.
- Add the minimal directory prefix only when needed to distinguish duplicate
  filenames, such as `impls/python/STATUS.md` and `user/python/STATUS.md`.

## Design Mode

When the user asks to enter `design mode`:

- Treat the session as exploratory architecture and product research.
- Integrate current product design and code architecture before proposing
  changes.
- Focus on systematic design advancement, module semantics, responsibilities,
  and tradeoffs.
- Prefer a research-report shape with high-level guidance over low-level
  implementation detail.
- Cite authoritative sources when external references are necessary.
- If a proposal would change core processes, page structure, product
  positioning, or public API direction, pause and ask for confirmation before
  editing documents or code.
