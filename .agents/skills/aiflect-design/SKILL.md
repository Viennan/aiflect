---
name: aiflect-design
description: Use when designing, repairing, or planning aiflect architecture, public behavior, provider-neutral contracts, module responsibilities, implementation strategy, requirement shape, deep-design, or Plan-mode style work. Load this skill for user-requested deep-design and when the agent judges a large or complex requirement needs deep, systematic, advanced design; in default implementation sessions, load it when the change needs tradeoff analysis or could alter existing design.
---

# Aiflect Design

## Purpose

Use this skill to make design work explicit before implementation. Design work
includes architecture, product semantics, public API direction, provider-neutral
contracts, module responsibilities, requirement shape, and repair of an existing
design that no longer fits the code or product direction.

## Source Model

- Treat current code and tests as the objective record of implemented behavior.
- Treat `docs` as the knowledge base above the code: design philosophy,
  tradeoffs, historical reasoning, user documentation, implementation history,
  and medium- or long-term planning.
- Use code and `docs` together during architecture and solution design. They
  answer different questions; neither should silently override the other.
- Load `$aiflect-knowledge-base` before using `docs`, then start from
  `docs/INDEX.md` and read the smallest relevant document set.

## Design Workflow

1. Frame the problem:
   - Identify the requested outcome, affected users, public behavior, provider
     boundaries, and non-goals.
   - Decide whether this is a new design, a design repair, or implementation
     planning for an already accepted design.
   - Decide whether `deep-design` applies because the user requested it or
     because the requirement is large or complex enough to benefit from it.
2. Build context from both sources:
   - Read relevant source files, nearby tests, capability metadata, and package
     or pytest configuration when they affect the proposal.
   - Read relevant requirements, design, implementation, and user docs through
     `$aiflect-knowledge-base`.
   - Record mismatches between code and docs instead of smoothing them over.
3. Analyze options:
   - Compare at least the current path and one plausible alternative when the
     decision is architectural or public-facing.
   - Make tradeoffs explicit: simplicity, provider portability, API stability,
     testability, future extension, and migration cost.
   - In `deep-design`, apply the stronger research and ambition rules below.
4. Produce a decision:
   - Prefer a scoped recommendation with rationale, rejected alternatives,
     affected files or docs, and validation expectations.
   - Include unresolved questions when the evidence does not justify a confident
     decision.
   - Do not edit code during pure design work unless the user asks to proceed
     into implementation.
5. Hand off cleanly:
   - When implementation follows, load `$aiflect-implementation` and carry over
     the accepted design constraints.
   - When tests are added or changed, load `$aiflect-testing`.
   - When docs need to be updated, load `$aiflect-knowledge-base` and keep the
     updates inside the accepted design scope.

## Deep Design

Use `deep-design` when the user explicitly asks for it, or when the agent judges
that a large or complex requirement would benefit from it, such as adding a new
subsystem, changing a cross-cutting provider contract, or redesigning a major
public API surface.

In `deep-design`:

- Emphasize depth, systematic reasoning, advanced architecture, and aggressive
  exploration.
- Research industry implementations, established prior art, and frontier
  exploration broadly enough to inform the design.
- Provide links for external references used in the design, and prefer primary
  or authoritative sources when available.
- Compare mature approaches with more ambitious alternatives instead of only
  refining the current implementation.
- Keep aggressive exploration honest by separating the recommended path,
  speculative options, risks, migration cost, and validation requirements.

These principles are not anti-goals for ordinary design. Normal design should
still be thoughtful, systematic, and informed when the problem calls for it;
`deep-design` simply raises the expected depth, research breadth, and appetite
for bold options.

## Stop and Ask

Pause for user decision before continuing when:

- Code and `docs` conflict in a way that changes product direction or public
  behavior.
- The design would change core processes, provider-neutral contracts, package
  structure, public API shape, product positioning, or long-term roadmap.
- Implementation evidence shows the accepted design needs adjustment.
- A docs update would go beyond the current request or accepted design scope.
