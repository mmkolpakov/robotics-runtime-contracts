# Preserve Published Schema Compatibility

- Status: accepted
- Date: 2026-09-07
- Decision: D10 of the approved runtime implementation specification
- Supersedes: [ADR 0001](0001-version-contracts-independently.md)

## Context and Problem Statement

Harness and infra consume different released contract generations. The 0.16
transition reused schema names for incompatible forms, so `schema_version`
alone cannot identify historical evidence. A package minor version and immutable
release assets do not prevent this ambiguity.

## Decision Outcome

A published `<role>.v<major>` name identifies a major document shape. Changes
under that name must be additive after resolving references in both versions:

- optional properties, input-enum additions and documentation annotations may
  be additive;
- output-enum additions (including verdicts), new required fields, removed
  properties, changed types or constants, narrowed constraints, newly closed
  objects, new conditional requirements and changed IDs are breaking;
- breaking changes require a new schema major, a catalog role and migration
  notes. A package minor release does not authorize reuse of an old name.

Digest snapshots are a tripwire for accidental byte changes, not a compatibility
proof. The planned structural comparison against the last released schemas
(implementation item 25) is not implemented yet. Until that gate exists,
published schema changes remain deferred. Once implemented, an intentional
digest update requires a passing compatibility check, consumer tests and a
changelog entry, or the new-major migration path for a breaking change.

## Consequences

Released 0.15 and 0.16 artifacts remain unchanged. Historical readers must select
the original package version as described in the migration guide. The catalog
still gives consumers an explicit role-to-schema mapping. This decision changes
the forward policy; it does not claim that cross-repository or structural
compatibility gates already exist.
