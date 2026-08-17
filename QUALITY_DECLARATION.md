# Robotics Runtime Contracts Quality Declaration

This document applies the guidelines in
[REP-2004](https://github.com/ros-infrastructure/rep/blob/master/rep-2004.rst)
to the
`robotics-runtime-contracts` Python package. The package is not a ROS package,
but REP-2004 provides a useful, recognizable maturity rubric.

The package claims **Quality Level 4**. It is a pre-1.0 package and does not
claim the stable-version, platform breadth, coverage policy, or peer-reviewed
quality registration required for Levels 1 through 3.

## Version Policy

The Python distribution follows Semantic Versioning during its pre-1.0 phase.
The canonical pre-1.0 contract set and release policy are documented in
[COMPATIBILITY.md](COMPATIBILITY.md). Tagged artifacts are immutable; schema
digests for packaged bytes are available through the public API.

The public Python API is the set exported by
`robotics_runtime_contracts.__all__`. Internal modules and underscored symbols
are not a stable API.

## Change Control

Repository policy requires reviewable changes, CI on pushes and pull requests,
positive and negative contract fixtures, consumer-impact analysis, and migration
notes for breaking changes. The repository does not claim an independently
audited peer-review or contributor-origin process.

## Documentation

Feature and API entry points are documented in [README.md](README.md).
Compatibility rules are in [COMPATIBILITY.md](COMPATIBILITY.md), architecture
decisions are in [`docs/decisions`](docs/decisions/), and supply-chain claims
are in [SUPPLY_CHAIN.md](SUPPLY_CHAIN.md).

The package is licensed under the [MIT License](LICENSE). Copyright and author
attribution are recorded in that license and repository history.

## Testing and Static Analysis

CI performs:

- JSON Schema Draft 2020-12 metaschema checks;
- positive, negative, semantic, qualification-link, and consumer-example tests;
- Ruff linting and formatting;
- strict mypy analysis of the typed package;
- wheel and source-distribution builds;
- installation checks against the built distributions.

These checks exceed the minimum Level 4 requirements. The project does not yet
publish or enforce a coverage threshold and therefore does not claim a higher
quality level.

## Dependencies

The runtime dependency is `jsonschema` with its non-GPL format-validation
extras. It is version constrained in `pyproject.toml` and resolved in
`uv.lock`. The package has no runtime ROS dependency.

## Platform Support

The qualified development and release platform is CPython 3.12 on Ubuntu 24.04
x86-64, as exercised by GitHub-hosted CI. The wheel is pure Python, but other
operating systems, architectures, and Python versions are not part of this
quality claim until they are added to the CI matrix.

## Security

The vulnerability disclosure process and response target are documented in
[SECURITY.md](SECURITY.md). Validation performs no schema network fetches.
Release artifacts receive GitHub build-provenance attestations as documented in
[SUPPLY_CHAIN.md](SUPPLY_CHAIN.md).

## Peer Review

This Quality Level 4 claim has not been registered in a centralized REP-2004
package list and has not undergone an external REP-2004 assessment.
