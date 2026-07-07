---
name: aiflect-knowledge-base
description: Use when reading, using, maintaining, or reconciling the aiflect docs knowledge base; when requirements, design records, implementation notes, user docs, third-party references, public-behavior documentation, or docs/code consistency matter. For architecture, design repair, deep-design, or Plan-mode style work, pair with aiflect-design.
---

# Aiflect Knowledge Base

## Purpose

Use this skill for the `docs` knowledge base as both a source of product
understanding and a set of maintained documents. The knowledge base exists to
capture information that code alone cannot express: design philosophy,
tradeoffs, historical reasoning, user-facing intent, implementation progress,
and medium- or long-term planning.

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

## Using the Knowledge Base

- Use `docs` together with current code and tests when designing architecture,
  shaping a solution, explaining why an implementation looks the way it does, or
  judging whether a change fits the product direction.
- Treat code as the objective record of implemented behavior.
- Treat `docs` as the record of reasoning above the code: why a path was chosen,
  what alternatives were considered, what redundancy may be intentional, how the
  developer tends to reason, and which future plans may constrain today's work.
- Verify factual implementation claims in `docs` against the current code before
  relying on them.
- If `docs` and code conflict, report the conflict and do not choose a new
  product direction without user authorization.
- Reading `docs` does not by itself authorize editing `docs`; keep write access
  governed by the current request, accepted design scope, or explicit user
  permission.

## Maintenance Workflow

1. Confirm the user request includes documentation work or that the user has
   granted permission to modify `docs`, or that an accepted design or
   implementation scope requires a focused docs update.
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
- For deep-design or Plan-mode style work, load `$aiflect-design` to guide the
  design process, then use this skill to read or update the relevant docs.
- When organizing design discussions into docs, preserve useful reference links
  and compile the user's questions into an FAQ when that helps future readers.

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
