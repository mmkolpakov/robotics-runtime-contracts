# Robotics Runtime Contracts

[![CI](https://github.com/mmkolpakov/robotics-runtime-contracts/actions/workflows/ci.yml/badge.svg)](https://github.com/mmkolpakov/robotics-runtime-contracts/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/mmkolpakov/robotics-runtime-contracts)](https://github.com/mmkolpakov/robotics-runtime-contracts/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Canonical JSON Schema contracts and validation for portable robotics
acceptance runs. The package defines what a scenario requests, what a runtime
actually provided, and what evidence an execution produced.

The contracts are neutral to robot type, simulator scene, model family, and
product rules. Launch files, worlds, model weights, and control logic belong in
consumer repositories.

## Install

The current release is 0.6.0. Install its attested wheel directly from the
GitHub Release:

```bash
python -m pip install \
  https://github.com/mmkolpakov/robotics-runtime-contracts/releases/download/v0.6.0/robotics_runtime_contracts-0.6.0-py3-none-any.whl
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

path = Path("tests/fixtures/scenario/valid/simulation-realtime.yaml")
validate_document(yaml.safe_load(path.read_text(encoding="utf-8")))
print("valid")
PY
```

Applications pass already parsed mappings to the package. JSON and YAML file
loading remains the caller's responsibility.

## Schema Catalog

| Schema version | Purpose |
| --- | --- |
| `acceptance-scenario.v1` | Execution intent, ROS readiness, timing, evidence, authorization, and forbidden interfaces |
| `model-artifact-manifest.v1` | Model provenance, provider compatibility, and numerical conformance |
| `dataset-manifest.v1` | Immutable MCAP datasets, channels, time base, and governance |
| `runtime-manifest.v1` | Observed runtime, workload, accelerator, security, timing, and physical target facts |
| `execution-permit.v1` | Short-lived two-party physical execution permit bound to policy and target identity |
| `execution-verification.v1` | Verified Sigstore signers, target, and execution-policy decision |
| `acceptance-result.v1` | Acceptance verdict, authorization, forbidden graph, timing, workload, and evidence |
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
`ScenarioValidationError` is the scenario-specific validation error.

## Domain Extensions

`acceptance-scenario.v1` supports independently versioned, namespaced extension
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

- The v1 catalog introduced by package 0.6.0 is the initial public contract set.
- Published schema bytes are immutable and protected by SHA-256 regression tests.
- Package releases follow semantic versioning; a contract change requires a new
  schema version and explicit consumer migration.
- HIL and real-target contracts are observation-only and never authorize
  physical actuation.

Package installation is not a hardware qualification. Accelerator, HIL, and
real-target claims are owned by the runtime infrastructure's
[support matrix](https://github.com/mmkolpakov/robotics-runtime-infra#support-status)
and are scoped to an exact source revision, image digest, and named device.

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
