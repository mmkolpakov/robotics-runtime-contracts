# 0001 Schema Versioning

## Status

Accepted.

## Decision

Schemas use semantic file names with an explicit major contract suffix, for
example `scenario-manifest.v1.schema.json`.

Breaking changes create a new major schema file. Additive compatible fields may
stay in the same major version when existing fixtures remain valid.

## Consequences

Consumers can pin an exact schema file and upgrade deliberately. Domain-specific
fields start as local extensions and are promoted only after compatibility tests
prove that they are reusable.
