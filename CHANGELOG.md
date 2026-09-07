# Changelog

## Unreleased

- Add the CPython 3.12-3.14 CI matrix and declare `>=3.12,<3.15` support.
- Allow `referencing>=0.37,<1` while retaining the locked resolution; enable
  Renovate hook updates and group duplicate tool pins. Hosted bot onboarding
  and the first dependency PR remain an external acceptance gate.
- Lock the published 0.16 schema resources and catalog with a byte-digest and
  resource-inventory tripwire; structural compatibility checking remains planned.
- Document the breaking 0.15 to 0.16 migration and known consumer versions.
- Replace the pre-1.0 schema-name reuse policy with the compatibility rules in
  [ADR 0007](docs/decisions/0007-preserve-published-schema-compatibility.md).

## 0.16.0 - 2026-08-17

This release replaces the 0.15 contract generation. It is **not** a drop-in
upgrade for 0.15 producers or retained evidence, even where `schema_version`
still ends in `.v1`. See the
[0.15 to 0.16 migration guide](docs/migrations/0.15-to-0.16.md) before upgrading.

- Introduce a role catalog with one public schema per role and internal core
  resources; remove the former multi-generation compatibility API.
- Replace scenario, runtime, result, evidence and qualification shapes with
  the catalogued `v1` forms, including provider and evaluator declarations.
- Add artifact receipts and verification, acceptance observations, qualification
  profiles, provider conformance and shared validation/status helpers.
- Generalize MCAP summaries and Zenoh channels to recording summaries and
  transport channels; replace the qualification predicate and artifact kinds.
- Rename physical authorization image-digest fields and the permit CLI flag to
  execution-subject digest terminology.

This changelog starts with the 0.16 transition. Earlier patch history remains
in the tagged Git history; this is not a reconstructed list of every 0.15 change.
