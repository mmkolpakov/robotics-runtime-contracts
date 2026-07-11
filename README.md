# Robotics Runtime Contracts

[![CI](https://github.com/mmkolpakov/robotics-runtime-contracts/actions/workflows/ci.yml/badge.svg)](https://github.com/mmkolpakov/robotics-runtime-contracts/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/mmkolpakov/robotics-runtime-contracts)](https://github.com/mmkolpakov/robotics-runtime-contracts/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Versioned JSON Schema contracts and canonical validation for portable robotics
acceptance runs. The package defines what a scenario requests, what a runtime
actually provided, and what evidence an execution produced.

The contracts are neutral to robot type, simulator scene, model family, and
product rules. Launch files, worlds, model weights, and control logic belong in
consumer repositories.

## Install

The current release is 0.4.3. Install its attested wheel directly from the
GitHub Release:

```bash
python -m pip install \
  https://github.com/mmkolpakov/robotics-runtime-contracts/releases/download/v0.4.3/robotics_runtime_contracts-0.4.3-py3-none-any.whl
```

Python 3.12 or newer is required. Release assets include the wheel, source
distribution, checksums, and GitHub artifact attestations.

## Quick Start

To run the packaged examples and development checks, use
[uv](https://docs.astral.sh/uv/) from a checkout:

```bash
git clone https://github.com/mmkolpakov/robotics-runtime-contracts.git
cd robotics-runtime-contracts
uv sync --locked --all-groups
uv run python - <<'PY'
import yaml
from pathlib import Path
from robotics_runtime_contracts import validate_document

path = Path("tests/fixtures/v2/valid/simulation-realtime.yaml")
validate_document(yaml.safe_load(path.read_text(encoding="utf-8")))
print("valid")
PY
```

Applications pass already parsed mappings to the package. JSON and YAML file
loading remains the caller's responsibility.

## Schema Catalog

| Schema version | Purpose |
| --- | --- |
| `acceptance-scenario.v1` | Stable legacy scenario contract |
| `acceptance-scenario.v2` | Execution mode, ROS readiness, time, data plane, and evidence policy |
| `model-artifact-manifest.v1` | Model provenance, provider compatibility, and numerical conformance |
| `dataset-manifest.v1` | Immutable MCAP datasets, channels, time base, and governance |
| `runtime-manifest.v1` | Stable model-backed runtime manifest from v0.4.0 |
| `runtime-manifest.v2` | Runtime facts with explicit `none` or `inference` workload |
| `execution-permit.v1` | Short-lived HIL and real-robot approval predicate |
| `acceptance-result.v1` | Stable model-backed acceptance result from v0.4.0 |
| `acceptance-result.v2` | Result and evidence with explicit `none` or `inference` workload |
| `evidence-index.v1` | Finalized local and confirmed remote evidence segments |

Every schema uses JSON Schema Draft 2020-12, rejects unknown root fields, has a
versioned `$id`, and is included in the Python wheel.

## Python API

```python
from robotics_runtime_contracts import (
    ContractValidationError,
    SemanticValidationError,
    load_schema,
    schema_names,
    validate_document,
)

print(schema_names())
validate_document(document)
schema = load_schema("runtime-manifest.v1")
```

`validate_document()` selects the contract from `schema_version`. Structural
and semantic failures include an exact JSON path. `validate_scenario()` and
`ScenarioValidationError` remain available for `acceptance-scenario.v1` users.

## Domain Extensions

`acceptance-scenario.v2` supports independently versioned, namespaced extension
schemas without weakening common safety, time, or evidence rules. The caller
supplies the digest-pinned schema bytes; validation never fetches a schema from
the network.

```python
validate_document(
    scenario,
    extension_schemas={
        "https://schemas.example.org/sorting.v1.schema.json": schema_bytes,
    },
)
```

Extension keys use reverse-domain namespaces such as `org.example.sorting`.
External `$ref` values are rejected to keep validation deterministic and free
from network or file-system side effects.

## Compatibility

- Published schema versions are immutable.
- Package releases follow semantic versioning.
- Adding a schema is backward-compatible; changing a published schema requires
  a new schema version.
- `acceptance-scenario.v1` is protected by a byte-level SHA-256 regression test.
- See [Migrating from scenario v1 to v2](docs/migration-v1-v2.md) before adopting
  the execution and evidence policies in v2.
- Use [runtime and result v2](docs/runtime-result-v2.md) for executions that may
  omit inference.

## Development

```bash
uv sync --locked --all-groups
uv run pre-commit run --all-files --show-diff-on-failure
uv run pytest
uv build
```

CI validates every schema against its metaschema, runs positive and negative
fixtures, builds wheel and source distributions, and verifies the installed
wheel.

## Support and Security

Use [GitHub Issues](https://github.com/mmkolpakov/robotics-runtime-contracts/issues)
for reproducible contract defects and compatibility questions. See
[CONTRIBUTING.md](CONTRIBUTING.md) before proposing a schema change. Report
security-sensitive findings according to [SECURITY.md](SECURITY.md); never put
credentials, private datasets, device identifiers, or signing material in an
issue.

## License

[MIT](LICENSE)
