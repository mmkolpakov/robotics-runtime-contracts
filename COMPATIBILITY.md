# Compatibility Policy

This policy defines compatibility for the Python package and every JSON Schema
contract published by this repository.

## Version Axes

The project has two independent version axes:

1. The Python distribution follows
   [Semantic Versioning](https://semver.org/) while it remains pre-1.0.
2. Every document declares an exact schema version in `schema_version`, and
   every schema has a versioned `$id`.

A package minor release may add a new schema version without changing existing
schema bytes. Removing a schema, changing a public Python symbol, or changing
validation behavior for an already published schema is a package-level breaking
change.

## Published Schema Immutability

A schema is published when it is included in a tagged release. Its bytes,
canonical `$id`, validation rules, and SHA-256 digest are immutable after that
release. A changed field, constraint, or meaning requires a new schema version.
The regression test in `tests/test_contracts.py` protects the recorded digests.

Unreleased schema versions may change on a development branch. Their digest is
fixed when the release containing them is tagged.

Package `0.7.0` preserves the validation behavior and schema bytes of
`acceptance-result.v1`. The stricter assertion-status hierarchy, lifecycle
sample uniqueness, and evidence binding are introduced only by
`acceptance-result.v2`.

Package `0.8.0` preserves both earlier result schemas byte for byte and adds
`acceptance-result.v3`. Version 3 accepts verified
`application/x-ndjson` evidence, aligning result documents with streaming trace
segments already supported by `evidence-index.v2`.

Package `0.9.1` preserves every earlier schema byte for byte, adds
batch document validation to the CLI, and retains the `0.9.0` additions:
`acceptance-scenario.v3`. Version 3 makes the skipped-step budget explicit for
stepped simulation. It also adds a CLI over the same structural, semantic, and
extension validation used by the Python API.

## Reader and Writer Rules

- Readers select the validator from the document's exact `schema_version`.
- Writers emit one declared version and must not rely on a reader guessing a
  version.
- Readers may support multiple versions side by side.
- Migration is explicit and creates a new document. Validation never mutates an
  input document.
- A migration that cannot preserve meaning requires caller-supplied values.
- There is no implicit downgrade path.

## Schema Matrix

`Exact` means that producers write the named version and consumers validate that
same version. `Forward migration` identifies the only package-provided
conversion.

| Schema | Compatibility mode | Migration policy |
| --- | --- | --- |
| `acceptance-scenario.v1` | Exact read/write; forward migration | `migrate_scenario_v1_to_v2()` requires metric selectors and time-authority thresholds from the caller |
| `acceptance-scenario.v2` | Exact read/write | Coexists with v3; no automatic migration |
| `acceptance-scenario.v3` | Exact read/write | Current scenario target; stepped simulation requires an explicit skip budget |
| `acceptance-run.v1` | Exact read/write | No automatic migration |
| `acceptance-result.v1` | Exact read/write | Coexists with v2; no lossless automatic migration |
| `acceptance-result.v2` | Exact read/write | Coexists with v3; no automatic migration |
| `acceptance-result.v3` | Exact read/write | Current result target; no downgrade |
| `acceptance-aggregate.v1` | Exact read/write | Coexists with v2; no automatic migration |
| `acceptance-aggregate.v2` | Exact read/write | Current cross-domain aggregate target |
| `causal-chain.v1` | Exact read/write | No automatic migration |
| `dataset-manifest.v1` | Exact read/write | No automatic migration |
| `evidence-index.v1` | Exact read/write | Coexists with v2; no automatic migration |
| `evidence-index.v2` | Exact read/write | Current evidence-index target |
| `execution-permit.v1` | Exact read/write | No automatic migration |
| `execution-verification.v1` | Exact read/write | No automatic migration |
| `mcap-summary.v1` | Exact read/write | No automatic migration |
| `model-artifact-manifest.v1` | Exact read/write | No automatic migration |
| `qualification-bundle.v1` | Exact read/write | No automatic migration |
| `qualification-policy.v1` | Exact read/write | No automatic migration |
| `runtime-manifest.v1` | Exact read/write | No automatic migration |
| `zenoh-channel.v1` | Exact read/write | No automatic migration |
| `zenoh-channel-observation.v1` | Exact read/write | No automatic migration |

## Normative Runtime Basis

The package itself requires CPython 3.12 or newer. Runtime contracts deliberately
record a narrower robotics baseline where interoperability depends on it:

- `runtime-manifest.v1` identifies ROS 2 Jazzy and Gazebo Harmonic.
- `acceptance-scenario.v1`, `acceptance-scenario.v2`,
  `acceptance-scenario.v3`, and
  `evidence-index.v2` require `zstd` evidence compression.
- Other schemas remain independent of robot type, scene, model family, and
  product rules.

Changing a required ROS distribution, Gazebo collection, compression format, or
the meaning of an enum value requires a new schema version. Package installation
does not qualify a runtime or physical target.

## Domain Extensions

`acceptance-scenario.v1`, `acceptance-scenario.v2`, and
`acceptance-scenario.v3` support digest-pinned,
namespaced local extensions. Extension schemas are supplied by the caller, must
use JSON Schema Draft 2020-12, and may contain only local references. They are
not fetched from the network. Forward migration preserves extension
declarations and payloads; callers must supply the same pinned schema documents
when validating the migrated scenario.

An `acceptance-result.v2` or `acceptance-result.v3` document with status
`passed` contains at least one assertion result and one evidence item. Its
time-authority evidence digest must identify an item in that evidence list. A
non-passing result may represent an early stop with zero time-authority samples
and no evidence digest; measured observations and successful results require
the digest.

An extension remains owned by its consumer until its semantics are broadly
reusable and accepted through the normal schema-change process. Moving a field
into the common catalog requires a new common schema version and explicit
migration guidance.

## Change Review

Every contract change must state:

- affected schema versions;
- reader and writer impact;
- migration path;
- positive and negative examples;
- whether any normative runtime basis changed.

Architecture decisions are recorded in [`docs/decisions`](docs/decisions/).
