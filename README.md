# robotics-runtime-contracts

Neutral JSON Schema contracts for robotics simulation runtimes.

## Scope

This repository owns shared machine-readable contracts only. It does not contain
domain scenarios, robot models, product rules, training data, or application code.

Current baseline:

| Area | Version |
| --- | --- |
| Package | 0.2.0 |
| JSON Schema | Draft 2020-12 |
| Python for validation | 3.12 |
| check-jsonschema | 0.37.4 |
| jsonschema | 4.26.0 |
| pytest | 9.0.2 |
| yamllint | 1.38.0 |
| ruff | 0.15.0 |

Release locks require full git commit SHAs and `sha256:` image digests. The
literal `unknown` is rejected by `stack-lock.v1`.

## Contracts

| Schema | Purpose |
| --- | --- |
| `scenario-manifest.v1.schema.json` | Scenario identity, launch boundary, graph readiness, recording policy, and safety target |
| `runtime-profile.v1.schema.json` | Runtime capabilities and environment guard |
| `ros-graph-contract.v1.schema.json` | Expected ROS graph readiness and publisher/subscriber matching |
| `evidence-manifest.v1.schema.json` | Machine-readable result of a run |
| `run-metrics.v1.schema.json` | Numeric and categorical run metrics |
| `artifact-store-policy.v1.schema.json` | Local and S3-compatible artifact retention policy |
| `scenario-composition-manifest.v1.schema.json` | Base scenario, components, overlays, matrix, and trace requirements |
| `domain-extension-manifest.v1.schema.json` | Local domain extensions and promotion path |
| `perception-provider.v1.schema.json` | Computer vision provider boundary and message compatibility policy |
| `model-artifact.v1.schema.json` | Model artifact identity, runtime, and checksum |
| `stack-lock.v1.schema.json` | Pinned repositories, images, and runtime releases |
| `stack-compatibility.v1.schema.json` | Cross-repository compatibility gate |

## Quickstart

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e . -r requirements-dev.txt
make ci
```

Installed package entry:

```python
from robotics_runtime_contracts import schema_path

schema_path("scenario-manifest.v1.schema.json")
```

## Extension Policy

Domain teams can keep local extensions outside this repository while they prove
usefulness. Accepted extensions are promoted through a schema change, fixtures,
and compatibility tests.

Custom perception messages are allowed only when the standard projection is not
technically meaningful. Such cases must include an ADR reference and an explicit
architecture approval marker in the domain extension manifest.
