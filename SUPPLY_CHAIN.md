# Supply-Chain Assurance

This document records the actual build assurance of each released component
against the [SLSA v1.2 Build Track](https://slsa.dev/spec/v1.2/).

GitHub documents artifact attestations from hosted workflows in SLSA v1.0
terms. The project assessment below maps the same controls to the current v1.2
requirements. It is a maintainer assessment, not an independent certification.

## Component Table

| Component | Source and builder | Provenance | Actual level |
| --- | --- | --- | --- |
| Python wheel (`.whl`) | `v*` tag whose commit is reachable from `origin/main`; `.github/workflows/release.yml`; GitHub-hosted Ubuntu 24.04; `uv build --no-sources` | `actions/attest` creates signed SLSA build provenance bound to the artifact digest | Build L2 |
| Source distribution (`.tar.gz`) | `v*` tag whose commit is reachable from `origin/main`; `.github/workflows/release.yml`; GitHub-hosted Ubuntu 24.04; `uv build --no-sources` | `actions/attest` creates signed SLSA build provenance bound to the artifact digest | Build L2 |

Both distributions are built and tested once in a job without OIDC authority.
The resulting workflow artifact is consumed unchanged by the enabled
publication jobs:

- the optional `publish-pypi` job publishes to PyPI through Trusted
  Publishing when `PYPI_PUBLISH_ENABLED` is `true`;
- the `github-release` job attests the distributions and creates the GitHub
  Release.

Only the PyPI job has `id-token: write` for publication. It does not check out
the repository or execute project code. No PyPI API token is used or stored.
The hosted builder and authentic provenance meet the L2 shape. Build L3 is not
claimed because the project does not use and verify an isolated reusable build
workflow as its trusted builder boundary.

The repository does not claim a SLSA Source Track level.

## Consumer Verification

Download an artifact from the GitHub Release, then verify its attestation:

```bash
gh attestation verify \
  robotics_runtime_contracts-<version>-py3-none-any.whl \
  --repo mmkolpakov/robotics-runtime-contracts
```

The same command applies to the source distribution. Consumers that pin a
builder may add `--signer-workflow` for
`mmkolpakov/robotics-runtime-contracts/.github/workflows/release.yml`.

Verification establishes artifact identity and build provenance. It does not
qualify a robotics runtime, dataset, model, or physical target.

## Release Controls

- Dependencies are resolved from the committed `uv.lock`.
- Actions are pinned by immutable commit SHA.
- Release builds run repository checks and the complete test suite.
- Wheel and source distribution installation are checked in CI.
- Consumer examples are validated by the same public API before release.
- The Git tag must equal `v` followed by the installed package version.
- The release job fetches `origin/main` and fails before building when the
  tagged commit is not reachable from that branch.
- PyPI publication requires the repository variable
  `PYPI_PUBLISH_ENABLED=true` and uses the protected GitHub environment named
  `pypi`.

Any change to the builder boundary, attestation action, release trigger, or
artifact set requires updating this table.

The workflow gate proves branch ancestry; it does not decide who may create,
update, or delete a release tag. Repository administrators must separately
maintain a GitHub tag ruleset for `v*` that restricts those operations to the
release maintainers. The ruleset is an external repository control and is not
represented by a file in this source tree. A release is not authorized until
both the ancestry gate and that ruleset are active.

## Trusted Publisher Setup

Status: **pending external configuration**.

PyPI must be configured once before the first release. Register a pending
publisher if the project does not yet exist on PyPI; otherwise add a Trusted
Publisher to the existing `robotics-runtime-contracts` project. Use these exact
values:

| PyPI field | Value |
| --- | --- |
| Owner | `mmkolpakov` |
| Repository | `robotics-runtime-contracts` |
| Workflow | `release.yml` |
| Environment | `pypi` |

Create and protect the `pypi` environment in GitHub before registering the
publisher. No `PYPI_API_TOKEN` secret is required. After the Trusted Publisher
is active, set the repository variable `PYPI_PUBLISH_ENABLED` to `true`.
Until then, the PyPI job remains skipped and the attested GitHub Release is the
canonical distribution channel. Once enabled, a PyPI publication failure fails
the release workflow.

Release `robotics-runtime-contracts` before releasing a version of
`robotics-acceptance-harness` that depends on it. Create and push the protected
version tag only after the contracts GitHub Release and build-provenance
attestation are available.
