from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from robotics_runtime_contracts import validate_document
from robotics_runtime_contracts._qualification import (
    QualificationError,
    _Artifact,
    _load_artifact,
    _validate_links,
    validate_qualification_artifacts,
)
from tests.support import qualification_specifications


def artifacts(case: str) -> list[_Artifact]:
    return [
        _load_artifact(specification, {}) for specification in qualification_specifications(case)
    ]


def artifact(items: list[_Artifact], subject_name: str) -> _Artifact:
    return next(item for item in items if item.subject_name == subject_name)


def document(items: list[_Artifact], subject_name: str) -> dict[str, Any]:
    value = artifact(items, subject_name).document
    assert isinstance(value, dict)
    return value


def validate_mutation(*documents: Mapping[str, Any]) -> None:
    for value in documents:
        validate_document(value)


_DELETE = object()
Change = tuple[str, tuple[str | int, ...], Any]


def apply_changes(items: list[_Artifact], changes: Sequence[Change]) -> None:
    touched: dict[str, dict[str, Any]] = {}
    for subject_name, path, value in changes:
        root = document(items, subject_name)
        target: Any = root
        for key in path[:-1]:
            target = target[key]
        if value is _DELETE:
            del target[path[-1]]
        else:
            target[path[-1]] = deepcopy(value)
        touched[subject_name] = root
    validate_mutation(*touched.values())


_PLAYBACK = {
    "target_environment": "simulation",
    "data_source": "mcap_playback",
    "plant_backend": "recorded_data",
    "time_mode": "playback_clocked",
    "data_plane_profile": "standard_isolated",
}


@pytest.mark.parametrize("case", ["transport", "inference", "physical"])
def test_schema_valid_qualification_fixture_is_complete(case: str) -> None:
    validate_qualification_artifacts(qualification_specifications(case))


@pytest.mark.parametrize("case", ["transport", "inference", "physical"])
def test_generated_qualification_bundle_v2_is_schema_valid(case: str) -> None:
    metadata = validate_qualification_artifacts(qualification_specifications(case))
    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {"name": item["subject_name"], "digest": {"sha256": item["sha256"]}}
            for item in metadata["artifacts"]
        ],
        "predicateType": (
            "https://robotics-runtime-contracts.dev/attestations/qualification-bundle/v2"
        ),
        "predicate": {
            "schema_version": "qualification-bundle.v2",
            "run_id": metadata["run_id"],
            "generated_at": metadata["generated_at"],
            "artifacts": [
                {"kind": item["kind"], "subject_name": item["subject_name"]}
                for item in metadata["artifacts"]
            ],
        },
    }
    policy = {
        "schema_version": "qualification-policy.v2",
        "policy_id": "generated-fixture-policy",
        "predicate_type": (
            "https://robotics-runtime-contracts.dev/attestations/qualification-bundle/v2"
        ),
        "certificate_identities": [
            (
                "https://github.com/example/robotics/.github/workflows/"
                "qualification.yml@refs/heads/main"
            )
        ],
        "certificate_oidc_issuer": "https://token.actions.githubusercontent.com",
        "trusted_root_sha256": "0" * 64,
        "required_artifact_kinds": sorted({item["kind"] for item in metadata["artifacts"]}),
    }

    validate_document(statement, schema="qualification-bundle.v2")
    validate_document(policy)


def test_canonical_loader_reads_every_artifact_once(monkeypatch: pytest.MonkeyPatch) -> None:
    specifications = qualification_specifications("inference")
    fixture_paths = {Path(value.partition("=")[2]) for value in specifications}
    reads: Counter[Path] = Counter()
    original = Path.read_bytes

    def tracked(path: Path) -> bytes:
        if path in fixture_paths:
            reads[path] += 1
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", tracked)

    validate_qualification_artifacts(specifications)

    assert reads == Counter({path: 1 for path in fixture_paths})


@pytest.mark.parametrize(
    ("case", "changes", "message"),
    [
        pytest.param(
            "transport",
            [("evidence/control-commands-observation.json", ("max_message_age_ms",), 101)],
            "contradicts its contract",
            id="delivery-threshold",
        ),
        pytest.param(
            "transport",
            [
                ("evidence/control-commands-observation.json", ("status",), "failed"),
                (
                    "evidence/control-commands-observation.json",
                    ("violations",),
                    [{"code": "message_age_exceeded", "message": "synthetic mismatch"}],
                ),
                (
                    "transport-qualification.json",
                    ("channel_observations", 0, "status"),
                    "failed",
                ),
                ("transport-qualification.json", ("verdict", "status"), "failed"),
                (
                    "acceptance-aggregate.json",
                    ("cross_domain_e2e", "transport_qualification", "status"),
                    "failed",
                ),
                (
                    "acceptance-aggregate.json",
                    ("cross_domain_e2e", "status"),
                    "failed",
                ),
            ],
            "contradicts its contract",
            id="delivery-verdict",
        ),
        pytest.param(
            "transport",
            [
                (
                    "transport-qualification.json",
                    ("causal_chains", 0, "hops", 0, "relationship"),
                    "parent",
                )
            ],
            "relationship",
            id="trace-relationship",
        ),
        pytest.param(
            "transport",
            [
                ("runtime-manifests/control.json", ("execution",), _PLAYBACK),
                ("runtime-manifests/control.json", ("clock", "sync_protocol"), "playback_clock"),
                ("results/control.json", ("execution",), _PLAYBACK),
            ],
            "execution.data_source",
            id="execution-mode",
        ),
        pytest.param(
            "transport",
            [
                (
                    "results/control.json",
                    ("time_authority_observation", "source_id"),
                    "foreign-clock",
                )
            ],
            "time-authority source",
            id="time-source",
        ),
        pytest.param(
            "transport",
            [("results/control.json", ("clock_observation", "real_time_factor"), 0.5)],
            "real-time policy",
            id="realtime-policy",
        ),
        pytest.param(
            "transport",
            [("results/control.json", ("clock_observation", "deadline_miss_ratio"), 0.1)],
            "real-time policy",
            id="deadline-policy",
        ),
        pytest.param(
            "transport",
            [("results/control.json", ("evidence", 0, "version_id"), "unexpected-version")],
            "evidence does not exactly match",
            id="evidence-version",
        ),
        pytest.param(
            "inference",
            [("results/primary.json", ("model_manifest_sha256",), "0" * 64)],
            "model_manifest_sha256",
            id="model-link",
        ),
        pytest.param(
            "physical",
            [("results/controller-domain.json", ("authorization", "permit_sha256"), "0" * 64)],
            "authorization.permit_sha256",
            id="result-permit",
        ),
        pytest.param(
            "physical",
            [("authorization/permit.json", ("scenario_sha256",), "0" * 64)],
            "permit for controller-domain scenario",
            id="permit-scenario",
        ),
        pytest.param(
            "physical",
            [("authorization/verification.json", ("target", "target_id"), "controller-beta")],
            "verification target",
            id="verification-target",
        ),
        pytest.param(
            "physical",
            [
                (
                    "results/controller-domain.json",
                    ("forbidden_graph_observation", "checked_topics"),
                    [],
                )
            ],
            "checked forbidden topics",
            id="forbidden-graph",
        ),
        pytest.param(
            "physical",
            [
                ("runtime-manifests/controller-domain.json", ("clock", "offset_ms"), -1000),
                (
                    "results/controller-domain.json",
                    ("hardware_clock_observation", "offset_ms"),
                    -1000,
                ),
            ],
            "hardware-clock policy verdict",
            id="absolute-clock-offset",
        ),
        pytest.param(
            "physical",
            [
                ("runtime-manifests/controller-domain.json", ("clock", "drift_ppm"), -1000),
                (
                    "results/controller-domain.json",
                    ("hardware_clock_observation", "drift_ppm"),
                    -1000,
                ),
            ],
            "hardware-clock policy verdict",
            id="absolute-clock-drift",
        ),
        pytest.param(
            "physical",
            [("results/controller-domain.json", ("evidence", 1), _DELETE)],
            "evidence does not exactly match",
            id="evidence-set",
        ),
    ],
)
def test_schema_valid_cross_link_contradictions_are_rejected(
    case: str,
    changes: Sequence[Change],
    message: str,
) -> None:
    items = artifacts(case)
    apply_changes(items, changes)

    with pytest.raises(QualificationError, match=message):
        _validate_links(items)


def test_result_evidence_segment_index_is_optional() -> None:
    items = artifacts("transport")
    result = document(items, "results/control.json")
    del result["evidence"][0]["segment_index"]
    validate_mutation(result)

    _validate_links(items)


@pytest.mark.parametrize(
    ("status", "updates", "violations"),
    [
        ("passed", {}, []),
        (
            "failed",
            {"lost_count": 1, "received_count": 19, "loss_ratio": 0.05},
            [{"code": "loss_ratio_exceeded", "message": "delivery loss exceeded"}],
        ),
        (
            "incomplete",
            {"sent_count": 0, "received_count": 0},
            [{"code": "insufficient_messages", "message": "no source messages"}],
        ),
        (
            "error",
            {},
            [{"code": "ambiguous_message_id", "message": "message identity is ambiguous"}],
        ),
    ],
)
def test_complete_transport_qualification_accepts_every_canonical_observation_status(
    status: str,
    updates: Mapping[str, Any],
    violations: list[dict[str, str]],
) -> None:
    items = artifacts("transport")
    observation = document(items, "evidence/control-commands-observation.json")
    transport = document(items, "transport-qualification.json")
    aggregate = document(items, "acceptance-aggregate.json")
    observation.update(updates, status=status, violations=violations)
    transport["channel_observations"][0]["status"] = status
    transport["verdict"]["status"] = status
    aggregate["cross_domain_e2e"]["transport_qualification"]["status"] = status
    aggregate["cross_domain_e2e"]["status"] = status
    validate_mutation(observation, transport, aggregate)

    _validate_links(items)


def test_runtime_v2_configuration_artifact_is_digest_linked() -> None:
    items = artifacts("transport")
    runtime = document(items, "runtime-manifests/control.json")
    runtime.update(
        schema_version="runtime-manifest.v2",
        configuration_artifacts=[
            {
                "kind": "runtime_resources",
                "sha256": artifact(items, "config/bridge.json").sha256,
            }
        ],
    )
    validate_mutation(runtime)

    _validate_links(items)


def test_runtime_v2_configuration_artifact_requires_retained_bytes() -> None:
    items = artifacts("transport")
    runtime = document(items, "runtime-manifests/control.json")
    runtime.update(
        schema_version="runtime-manifest.v2",
        configuration_artifacts=[{"kind": "host_topology", "sha256": "0" * 64}],
    )
    validate_mutation(runtime)

    with pytest.raises(QualificationError, match="host_topology configuration"):
        _validate_links(items)


def test_mcap_summary_cannot_cover_different_sources() -> None:
    items = artifacts("transport")
    summary = artifact(items, "mcap-summaries/control.json")
    worker_index = document(items, "evidence-indexes/worker.json")
    worker_index["segments"][0]["mcap_summary"].update(
        sha256=summary.sha256,
        size_bytes=summary.size_bytes,
    )
    validate_mutation(worker_index)

    with pytest.raises(QualificationError, match="multiple evidence sources"):
        _validate_links(items)


@pytest.mark.parametrize(
    ("case", "subject_name", "message"),
    [
        ("transport", "evidence/control.mcap", "indexed size"),
        ("transport", "config/bridge.json", "bridge configuration"),
        ("inference", "models/detector.onnx", "model source artifact"),
        ("inference", "datasets/baseline.mcap", "dataset MCAP"),
        ("physical", "policy/trust.json", "scenario trust policy"),
        ("physical", "authorization/preflight.json", "interlock"),
        ("physical", "evidence/hardware-clock.json", "indexed size"),
    ],
)
def test_referenced_raw_artifact_is_required(
    case: str,
    subject_name: str,
    message: str,
) -> None:
    items = [item for item in artifacts(case) if item.subject_name != subject_name]

    with pytest.raises(QualificationError, match=message):
        _validate_links(items)
