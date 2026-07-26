# Version Package Releases and Document Contracts Independently

- Status: accepted
- Date: 2026-07-26

## Context and Problem Statement

One Python release may need to read several document generations. Coupling
schema versions to the package version would force synchronized upgrades and
would make stored evidence ambiguous.

## Decision Drivers

- Deterministic validation of historical documents
- Explicit producer and consumer compatibility
- Immutable evidence interpretation
- Incremental migration

## Considered Options

- Use only the Python package version
- Change schemas in place
- Give every schema an independent versioned identifier

## Decision Outcome

Every document declares an exact `schema_version`; every schema has a versioned
`$id`; and tagged releases freeze published schema bytes by SHA-256. The Python
distribution follows its own Semantic Versioning lifecycle.

### Consequences

- Readers may support several schema versions in one package release.
- Breaking contract changes require a new schema version.
- Migrations are explicit and cannot invent missing business meaning.
- The catalog and compatibility matrix must be updated together.
