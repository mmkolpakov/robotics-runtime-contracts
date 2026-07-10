# robotics-runtime-contracts

Versioned acceptance-scenario contract shared by robotics runtimes and scenario
runners. The package contains one canonical JSON Schema and a small Python API
for validating in-memory scenario mappings.

The contract describes execution environment, deterministic seed, phase
timeouts, expected ROS graph readiness, and namespaced domain extensions. It
does not contain robot models, launch files, product rules, or scenario data.

## Toolchain

| Component | Version |
| --- | --- |
| Python | 3.12 |
| Package | 0.3.0 |
| JSON Schema | Draft 2020-12 |
| uv | 0.11.28 |
| jsonschema | 4.26.x |
| pytest | 9.1.1 |
| ruff | 0.15.21 |

## Development

```bash
uv sync --locked
uv run pre-commit run --all-files
uv run pytest
uv build
```

## Python API

```python
from robotics_runtime_contracts import validate_scenario

validate_scenario(scenario)
```

Validation failures raise `ScenarioValidationError` with the exact JSON path.
Domain-specific data belongs under a reverse-domain-style key in `extensions`.
