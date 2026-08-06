# Compatibility Policy

This policy applies to the Python package and every JSON Schema contract in the
repository.

## Versioning

The Python distribution follows [Semantic Versioning](https://semver.org/).
Each document also declares an exact `schema_version`, and every schema has a
versioned `$id`.

Before package `1.0.0`, writers emit one canonical version of each document
kind. The package can retain earlier readers when they are cheap and covered by
immutable-schema digest tests; no writer silently downgrades. `acceptance-aggregate.v4`
references an independently validated transport qualification instead of
embedding its evidence graph.

## Published Schemas

A schema becomes immutable when it is included in a tagged release. Its bytes,
`$id`, meaning, and recorded SHA-256 digest do not change in that release.
Changing a published contract requires a new schema version and package minor
release. Removing a schema from the current pre-1.0 package requires a package
minor release and release notes.

`tests/test_contracts.py` verifies the digest of every schema shipped in the
current wheel. Unreleased schemas may change on a development branch.

## Readers And Writers

- Readers select the validator from the document's declared `schema_version`.
- Writers emit one explicit version; readers never guess.
- Validation never mutates the input document.
- Migrations are separate, explicit tools and are added only for an active
  consumer that cannot migrate at its ownership boundary.
- There is no implicit downgrade path.

The current catalog is listed in [README.md](README.md). The package API and CLI
reject unknown schema identifiers. Retained superseded readers remain available
for explicit validation, while writers use only the current canonical version.

## Runtime Basis

The package requires CPython 3.12 or newer. Runtime contracts record ROS 2
Jazzy, Gazebo Harmonic, and zstd where interoperability depends on them.
Schemas remain independent of robot type, scene, model family, and product
rules. Package installation does not qualify a runtime or physical target.

Changing a required runtime family, compression format, or enum meaning
requires a new schema version.

## Domain Extensions

`acceptance-scenario.v5` supports digest-pinned, namespaced extensions. The
caller supplies Draft 2020-12 schema bytes; validation performs no network
fetches and permits only local references. An extension remains consumer-owned
until its semantics are reusable enough for the common catalog.

Moving an extension field into a common contract requires a new common schema
version and an explicit consumer migration plan.

## Change Review

Every contract change states:

- affected readers and writers;
- positive and negative examples;
- migration or deliberate replacement policy;
- runtime-basis impact;
- evidence and safety impact.

Architecture decisions are recorded in [`docs/decisions`](docs/decisions/).
