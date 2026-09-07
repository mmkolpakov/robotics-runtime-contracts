# Compatibility Policy

This policy covers the Python distribution and its JSON Schema contracts.

## Known Consumers

The integration audit on 2026-09-03 recorded these baselines:

| Consumer | Contracts pin | Scope of evidence |
| --- | --- | --- |
| Acceptance harness 0.18.0 (`614864d`) | `>=0.16,<0.17`, source `6c6b72a` (tree identical to `v0.16.0`) | Harness fixtures use the 0.16 catalog |
| Runtime infra (`caa62ab`) with harness 0.17.1 (`2fbdaf7`) | 0.15.4 (`d0f2909`) | Infra foundation integration tests its pinned pair |

This table is a dated snapshot, not a claim about current consumer branches.
The 0.15 and 0.16 generations are incompatible. See the
[migration guide](docs/migrations/0.15-to-0.16.md) and [changelog](CHANGELOG.md).

## Current Catalog

Release 0.16 maps each document role to exactly one schema in
[`catalog.v1.json`](src/robotics_runtime_contracts/schemas/catalog.v1.json).

Superseded experimental readers and writers are removed rather than carried as
parallel APIs. Historical releases remain reproducible from immutable Git tags
and release artifacts, but the current package does not promise to read their
documents.

## Package Versions

The Python distribution follows Semantic Versioning:

- patch: implementation or documentation changes that preserve the active
  contract set;
- minor before `1.0`: a new public capability or a documented breaking API
  change; a breaking schema change also requires a new schema major;
- major after `1.0`: a breaking public API or contract change.

Every pre-1.0 breaking change requires release notes and migration notes for
known consumers. Package versioning does not permit incompatible reuse of a
published schema identifier; [ADR 0007](docs/decisions/0007-preserve-published-schema-compatibility.md)
supersedes the former pre-1.0 replacement policy.

## Readers And Writers

- Documents declare `schema_version`; historical 0.15/0.16 evidence also needs
  its producer's exact package version because some identifiers were reused.
- Readers resolve document roles through the catalog and never guess a version.
- Writers emit only the catalogued schema for a role.
- Validation never mutates input and never retrieves a schema from the network.
- Migrations are introduced only for a real consumer and remain separate from
  validation.
- There is no implicit downgrade path.

## Schema Identity

The canonical IDs use the `urn:robotics-runtime-contracts:v1:*` namespace.
Public role schemas and internal reusable resources have disjoint IDs. Schema
digests are derived from packaged bytes with `schema_digest()`.

[`docs/schema-digests.json`](docs/schema-digests.json) records SHA-256 for all
29 schema resources and the catalog from `v0.16.0` (`0c2c0f4`). The test compares
raw packaged bytes and the complete file inventory with this checked-in
snapshot. Whitespace changes, modified internal cores, missing files and new
files all require review; JSON is not normalized before hashing.

The snapshot also ships in the source distribution so its bundled tests can
run. Tests never regenerate expected digests. After the structural gate exists,
an intentional snapshot update must accompany a changelog entry and a passing
compatibility comparison, or a new schema major and migration notes for a
breaking change. Updating hashes merely to make a failure disappear is not a
compatibility review.

Tagged release artifacts and their attestations are immutable. Under a published
name only additive changes are permitted. Breaking changes require a new schema
major, a catalog role and migration notes. The planned structural comparison
against the last release is not implemented yet; published schema changes remain
deferred until that gate exists. A digest comparison alone cannot prove
compatibility.

This repository validates its own fixtures and consumer examples against the
current checkout. It has no three-repository integration fixture or consumer
release gate. Consumer repositories must supply integration evidence when
adopting a new release.

## Neutrality

Common contracts do not select a robot or product. They model ROS 2/SROS2 and
runtime-specific constraints; concrete provider identities and capabilities are
observed data. Scenario extensions support digest-pinned, reverse-domain schemas.
Other roles' extension objects currently lack that validation.

Moving an extension into the common contract requires reusable semantics,
positive and negative fixtures, and an architecture decision.

## Change Review

Every contract change states:

- the affected document roles and producers;
- positive, negative, and cross-repository tests;
- evidence and physical-safety impact;
- the package-version impact;
- the migration plan for any known consumer.
