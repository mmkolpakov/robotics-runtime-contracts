# Separate Structural and Semantic Validation

- Status: accepted
- Date: 2026-07-26

## Context and Problem Statement

JSON Schema expresses document structure and many conditional constraints, but
some invariants compare values, calculate aggregates, or span collections.
Encoding one invariant in both JSON Schema and Python creates unreachable code
and divergent error behavior.

## Decision Drivers

- One authoritative owner per invariant
- Standard validation before custom code
- Precise JSON paths
- Reviewable cross-field logic

## Considered Options

- Put every rule in Python
- Duplicate important rules in both layers
- Use JSON Schema for structural rules and Python for irreducible relationships

## Decision Outcome

JSON Schema owns types, required fields, closed objects, enum constraints,
collection cardinality, uniqueness, and expressible conditionals. Python
semantic validators run only after structural success and own relational or
calculated invariants that are not cleanly expressed by the schema.

### Consequences

- Removing a Python check requires a regression test proving schema ownership.
- Semantic validators may rely on structurally valid input.
- Published schema rules remain immutable.
- Error classes distinguish structural and semantic failures.
