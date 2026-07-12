# Migrating Physical Observation Contracts to v3

Version 0.5.0 adds a contract generation for authorized hardware-in-the-loop
and real-target observation. Existing v1 and v2 schema bytes and semantics are
unchanged. Consumers opt in one document family at a time; no published
document is rewritten in place.

## Scope

The v3 generation covers physical observation with independently isolated
actuators. It does not authorize physical actuation.

| Document | Previous version | New version | Primary change |
| --- | --- | --- | --- |
| Scenario | `acceptance-scenario.v2` | `.v3` | Authorization intent and forbidden ROS interfaces |
| Runtime | `runtime-manifest.v2` | `.v3` | Verified permit facts and immutable target identity |
| Permit | `execution-permit.v1` | `.v2` | Trust policy and physical target identity binding |
| Verification | None | `execution-verification.v1` | Two verified Sigstore signers and policy decision |
| Result | `acceptance-result.v2` | `.v3` | Authorization, forbidden graph, and hardware timing evidence |

`model-artifact-manifest.v1`, `dataset-manifest.v1`, and
`evidence-index.v1` remain current.

## Scenario v3

Add `authorization` and `forbidden_ros_graph` to a v2 scenario.

Simulation uses:

```yaml
authorization:
  mode: none
forbidden_ros_graph:
  topics: []
  services: []
  actions: []
```

HIL and real-target observation use:

```yaml
authorization:
  mode: signed_execution_permit
  permit_schema: execution-permit.v2
  verification_schema: execution-verification.v1
  trust_policy_sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  two_party_approval: true
forbidden_ros_graph:
  topics:
    - /cmd_vel
  services: []
  actions: []
```

A physical scenario must declare at least one forbidden topic, service, or
action. HIL requires `physical_effect: none`. Real-target execution requires
`physical_effect: observation`. Both reject `actuator` in `hardware_scope`.

## Runtime v3

Add `authorization` to a v2 runtime. Each physical target now records:

- a logical `target_id`;
- an `identity_kind` and SHA-256 identity digest;
- a preflight evidence digest;
- an optional stable device path.

Target IDs and identity digests are unique. Simulation uses `mode: none` and
an empty `physical_targets` array. Physical runtimes require SROS2 Enforce,
`live_target`, `real_hardware`, and `hardware_realtime`.

## Permit v2

Create a new v2 permit instead of modifying a v1 permit. Bind it to the exact:

- scenario SHA-256;
- OCI image digest;
- lab trust policy SHA-256;
- target environment, logical ID, identity kind, and identity digest;
- hardware scope and permitted physical effect.

Operator and approver identities must differ. The permit lifetime is at most
30 minutes. HIL permits only `none`; real targets permit only `observation`.

Operational permits are UTF-8 JSON. YAML fixtures demonstrate schema values
but are not signing artifacts.

## Verification v1

The preflight verifier writes `execution-verification.v1` only after both
signatures and the policy decision pass. The document records:

- hashes of the permit, signed in-toto Statement, execution policy, and lab
  trust policy;
- the observed target identity;
- the immutable Cosign image digest and version;
- exactly one operator and one approver signer record;
- each signer identity, issuer, bundle digest, integrated time, and
  transparency-log result;
- the final `allow` decision.

The verifier, not this package, compares signer identities with the permit and
all permit/runtime/scenario digests. This package validates one document at a
time and performs no file, network, process, or device access.

## Result v3

Add `authorization` and `forbidden_graph_observation` to a v2 result. Physical
results also add `hardware_clock_observation`.

A passed physical result requires:

- a verified permit authorization bound to the same target environment;
- no forbidden ROS interface violations;
- a hardware clock observation taken inside the execution interval;
- a clock source consistent with its synchronization protocol;
- `within_policy: true`;
- all existing assertion, monotonic-time, shutdown, and evidence conditions.

## Signed Bytes

The authorization flow signs one exact in-toto Statement JSON file twice with
`cosign sign-blob`. Preflight verifies both bundles against that same file.
`statement_sha256` hashes the exact signed bytes. `permit_sha256` hashes the
exact standalone UTF-8 JSON permit bytes.

Preflight validates the standalone permit and the Statement predicate with
the same schema and compares their parsed JSON values. It does not reformat
the signed Statement and does not rely on a custom canonical JSON serializer.
This follows the in-toto Envelope guidance to avoid security dependencies on
canonicalization.

## Validation

The canonical HIL examples are under `tests/fixtures/v3/valid/`.

```bash
uv sync --locked --all-groups
uv run pre-commit run --all-files --show-diff-on-failure
uv run pytest tests/test_physical_contracts_v3.py
uv build --no-sources
```

Adopt the contracts release before upgrading the acceptance harness. Upgrade
runtime infrastructure only after the harness release is available as an
immutable artifact.
