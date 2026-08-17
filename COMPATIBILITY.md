# Compatibility Policy

This policy covers the Python distribution and its JSON Schema contracts.

## Pre-1.0 Canon

The project has no external consumers. Before package `1.0.0`, the default
branch publishes one canonical `v1` contract set. Each document role maps to
exactly one schema in
[`catalog.v1.json`](src/robotics_runtime_contracts/schemas/catalog.v1.json).

Superseded experimental readers and writers are removed rather than carried as
parallel APIs. Historical releases remain reproducible from immutable Git tags
and release artifacts, but the current package does not promise to read their
documents.

## Package Versions

The Python distribution follows Semantic Versioning:

- patch: implementation or documentation changes that preserve the active
  contract set;
- minor before `1.0`: a breaking replacement of the active contract set or a
  new public capability;
- major after `1.0`: a breaking public API or contract change.

Every pre-1.0 breaking change requires release notes and migration notes for
known consumers. Once external consumers exist, compatibility policy must be
revisited before the next incompatible change.

## Readers And Writers

- Documents declare an exact `schema_version`.
- Readers resolve document roles through the catalog and never guess a version.
- Writers emit only the catalogued schema for a role.
- Validation never mutates input and never retrieves a schema from the network.
- Migrations are introduced only for a real consumer and remain separate from
  validation.
- There is no implicit downgrade path.

## Schema Identity

The canonical IDs use the `urn:robotics-runtime-contracts:v1:*` namespace.
Public role schemas and internal reusable resources have disjoint IDs. Schema
digests are derived from packaged bytes with `schema_digest()`; no hand-written
digest table is maintained.

Tagged release artifacts and their attestations are immutable. Development
branches may change unreleased schema bytes while keeping tests, examples, and
the three-repository integration fixture synchronized.

## Neutrality

Common contracts do not select a simulator, middleware implementation, model
runtime, accelerator vendor, storage provider, or robot. Concrete provider
identities and capabilities are observed data. Domain-only fields use
digest-pinned, reverse-domain extensions.

Moving an extension into the common contract requires reusable semantics,
positive and negative fixtures, and an architecture decision.

## Change Review

Every contract change states:

- the affected document roles and producers;
- positive, negative, and cross-repository tests;
- evidence and physical-safety impact;
- the package-version impact;
- the migration plan for any known consumer.
