# Keep One Canonical Contract Set Before 1.0

- Status: accepted
- Date: 2026-07-26

## Context and Problem Statement

The repository has no external consumers, while several experimental document
generations made producer behavior and review scope ambiguous.

## Decision Drivers

- One obvious writer and reader per document role
- Small review and maintenance surface
- Deterministic identity for retained evidence
- A migration policy that starts when a real consumer exists

## Considered Options

- Retain every experimental reader
- Keep one canonical pre-1.0 contract set
- Stabilize all current documents as a permanent multi-version API

## Decision Outcome

Before package `1.0.0`, every public role maps to one canonical `v1` schema in a
machine-readable catalog. Tagged releases remain immutable, but the current
package does not carry superseded experimental readers. A breaking replacement
requires a package minor release and migration notes for known consumers.

### Consequences

- Producers and consumers resolve roles through one catalog.
- Unused compatibility branches are deleted.
- Migrations remain explicit and cannot invent missing business meaning.
- Compatibility policy must be revisited before onboarding an external consumer.
