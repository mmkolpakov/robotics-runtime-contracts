# Contributing

## Scope

Changes must remain independent of a specific robot, simulator scene, model
family, or product rule. Domain data belongs in a digest-pinned namespaced
extension, not in a common schema.

Follow [COMPATIBILITY.md](COMPATIBILITY.md). Before package `1.0.0`, update the
single canonical `v1` contract set and remove superseded experiments. A
breaking change requires a package minor release, release notes, and a migration
plan for every known consumer. Tagged releases remain immutable.

Architectural changes to this package require an accepted
[MADR](https://adr.github.io/madr/) record in
[`docs/decisions`](docs/decisions/). Product and robot-specific decisions do
not belong in this repository.

## Development

Requirements: Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --locked --all-groups
uv run pre-commit run --all-files --show-diff-on-failure
uv run mypy --strict src/robotics_runtime_contracts
uv run pytest
uv build --no-sources
```

Every schema change requires positive and negative fixtures, a metaschema test,
semantic tests where JSON Schema cannot express the invariant, and a synchronized
cross-repository fixture. Update `consumer-examples/` when a public workflow
changes. Pull requests must not include credentials, private data, model
weights, recordings, or hardware identifiers.

## Pull Requests

Keep each commit independently reviewable. Explain the compatibility effect,
the consumer problem being solved, and why an existing schema or extension is
insufficient. CI must pass before merge.
