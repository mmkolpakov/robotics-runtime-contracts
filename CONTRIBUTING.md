# Contributing

## Scope

Changes must remain independent of a specific robot, simulator scene, model
family, or product rule. Domain data belongs in a digest-pinned namespaced
extension, not in a common schema.

Follow [COMPATIBILITY.md](COMPATIBILITY.md). Published names allow only additive
schema changes; breaking changes require a new schema major, a catalog role,
release notes and a migration plan for every known consumer. Published schema
changes remain deferred until the structural compatibility gate is implemented.
Tagged releases remain immutable.

Architectural changes to this package require an accepted
[MADR](https://adr.github.io/madr/) record in
[`docs/decisions`](docs/decisions/). Product and robot-specific decisions do
not belong in this repository.

## Development

Requirements: Python 3.12 through 3.14 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --locked --all-groups
uv run pre-commit run --all-files --show-diff-on-failure
uv run mypy --strict src/robotics_runtime_contracts
uv run pytest
uv build --no-sources
```

Every schema change requires positive and negative fixtures, a metaschema test,
semantic tests where JSON Schema cannot express the invariant, and consumer
integration evidence. Contracts CI currently checks only its own fixtures and
examples; a cross-repository gate is still planned. Update `consumer-examples/` when a public workflow
changes. Pull requests must not include credentials, private data, model
weights, recordings, or hardware identifiers.

## Pull Requests

Keep each commit independently reviewable. Explain the compatibility effect,
the consumer problem being solved, and why an existing schema or extension is
insufficient. CI must pass before merge.

## Dependency Updates

Renovate tracks Python runtime, development and build requirements and `uv.lock`
through its [PEP 621 manager](https://docs.renovatebot.com/modules/manager/pep621/).
The [GitHub Actions manager](https://docs.renovatebot.com/modules/manager/github-actions/)
tracks action SHA pins and the `astral-sh/setup-uv` `version` input. Hook updates
are explicitly enabled through the
[pre-commit manager](https://docs.renovatebot.com/modules/manager/pre-commit/).
Ruff and check-jsonschema package/hook updates are grouped so their duplicate
pins can be reviewed together. Lock maintenance runs weekly in Helsinki time;
automerge is disabled.

The Python support range, CI matrix and `.python-version` (the minimum supported
development version) are reviewed together when support changes. A dependency
bot update alone must not expand the support claim.

Validate configuration changes with Renovate's official
[config validator](https://docs.renovatebot.com/config-validation/):

```bash
renovate-config-validator --strict renovate.json
```

Configuration in Git is not proof that the hosted bot is installed or active.
An administrator must enable the Renovate GitHub App for this repository and
complete onboarding. The M0 acceptance criterion is an actual dependency PR
from Renovate with passing checks, not a local config-validation result. If no
such PR exists by the end of M0, remove the inactive configuration as required
by the implementation plan. This remains an external gate until a PR is observed.
