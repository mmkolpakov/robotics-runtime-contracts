from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from robotics_runtime_contracts import (
    ContractValidationError,
    SemanticValidationError,
    load_schema,
    validate_document,
)
from robotics_runtime_contracts._qualification import (
    _ARTIFACT_ROLES,
    _RAW_ARTIFACT_KINDS,
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
    "data_source": "recording_playback",
    "plant_backend": "recorded_data",
    "time_mode": "playback_clocked",
    "data_plane_profile": "standard_isolated",
}


@pytest.mark.parametrize("case", ["transport", "inference", "physical"])
def test_schema_valid_qualification_fixture_is_complete(case: str) -> None:
    validate_qualification_artifacts(qualification_specifications(case))


@pytest.mark.parametrize("case", ["transport", "inference", "physical"])
def test_generated_qualification_bundle_is_schema_valid(case: str) -> None:
    metadata = validate_qualification_artifacts(qualification_specifications(case))
    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {"name": item["subject_name"], "digest": {"sha256": item["sha256"]}}
            for item in metadata["artifacts"]
        ],
        "predicateType": (
            "https://robotics-runtime-contracts.dev/attestations/qualification-bundle/v1"
        ),
        "predicate": {
            "schema_version": "qualification-bundle.v1",
            "run_id": metadata["run_id"],
            "generated_at": metadata["generated_at"],
            "artifacts": [
                {"kind": item["kind"], "subject_name": item["subject_name"]}
                for item in metadata["artifacts"]
            ],
        },
    }
    policy = {
        "schema_version": "qualification-policy.v1",
        "policy_id": "generated-fixture-policy",
        "predicate_type": (
            "https://robotics-runtime-contracts.dev/attestations/qualification-bundle/v1"
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

    validate_document(statement, schema="qualification-bundle.v1")
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
            [
                (
                    "results/control.json",
                    ("evidence", 0, "immutable_revision"),
                    "unexpected-revision",
                )
            ],
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


def test_qualification_requires_every_scenario_assertion() -> None:
    items = artifacts("transport")
    scenario = document(items, "scenario.json")
    extra_assertion = deepcopy(scenario["assertions"][0])
    extra_assertion["assertion_id"] = "camera-age-secondary"
    scenario["assertions"].append(extra_assertion)
    validate_mutation(scenario)

    with pytest.raises(QualificationError, match="omits scenario assertions"):
        _validate_links(items)


def test_qualification_requires_clock_relation_for_every_channel_pair() -> None:
    items = artifacts("transport")
    items[:] = [item for item in items if item.kind != "clock_relation"]
    transport = document(items, "transport-qualification.json")
    transport["clock_relations"] = []
    with pytest.raises(SemanticValidationError, match="aggregate transport status 'incomplete'"):
        validate_mutation(transport)

    transport["verdict"]["status"] = "incomplete"
    aggregate = document(items, "acceptance-aggregate.json")
    aggregate["cross_domain_e2e"]["transport_qualification"]["status"] = "incomplete"
    aggregate["cross_domain_e2e"]["status"] = "incomplete"
    validate_mutation(transport, aggregate)
    _validate_links(items)


def test_qualification_binds_clock_relation_to_scenario_policy() -> None:
    items = artifacts("transport")
    relation = document(items, "evidence/control-worker-clock.json")
    relation["policy"] = {**relation["policy"], "maximum_absolute_skew_ms": 2}
    validate_mutation(relation)

    with pytest.raises(QualificationError, match="clock relation .* policy"):
        _validate_links(items)


def test_shared_clock_observations_belong_to_their_endpoint_domains() -> None:
    items = artifacts("transport")
    scenario = document(items, "scenario.json")
    relation = document(items, "evidence/control-worker-clock.json")
    policy = {"method": "shared_clock_identity"}
    scenario["time_policy"]["cross_domain_clock"] = policy
    source_digest = document(items, "evidence-indexes/control.json")["artifacts"][1]["sha256"]
    destination_digest = document(items, "evidence-indexes/worker.json")["artifacts"][1]["sha256"]
    relation.update(
        method="shared_clock_identity",
        sync_protocol="shared_kernel_clock",
        policy=policy,
        shared_clock_identity={
            "authority": "shared-linux-kernel-clock-realtime",
            "boot_id": "01234567-89ab-4def-8123-456789abcdef",
            "implementation": "clock_gettime(CLOCK_REALTIME)",
            "resolution_sec": 1e-9,
            "source_observation_sha256": source_digest,
            "destination_observation_sha256": destination_digest,
        },
    )
    del relation["sample_count"]
    del relation["max_absolute_skew_ms"]
    validate_mutation(scenario, relation)
    _validate_links(items)

    identity = relation["shared_clock_identity"]
    identity["source_observation_sha256"] = destination_digest
    identity["destination_observation_sha256"] = source_digest
    validate_mutation(relation)
    with pytest.raises(QualificationError, match="source_observation.*domain control"):
        _validate_links(items)


def test_qualification_accepts_custom_evidence_media_type() -> None:
    items = artifacts("transport")
    evidence = {
        "artifact_id": "controller-log",
        "kind": "observation",
        "uri": "file:///evidence/controller.vendor",
        "local_path": "/evidence/controller.vendor",
        "media_type": "application/vnd.example.controller-log",
        "sha256": "d" * 64,
        "size_bytes": 128,
        "retention_class": "pull-request-7d",
        "segment_index": 4,
        "storage_state": "local",
    }
    document(items, "evidence-indexes/control.json")["artifacts"].append(evidence)
    document(items, "results/control.json")["evidence"].append(
        {
            key: value
            for key, value in evidence.items()
            if key not in {"local_path", "storage_state"}
        }
    )
    items.append(
        _Artifact(
            kind="other_evidence",
            subject_name="evidence/controller.vendor",
            sha256=evidence["sha256"],
            size_bytes=evidence["size_bytes"],
            document=None,
        )
    )
    validate_mutation(
        document(items, "evidence-indexes/control.json"),
        document(items, "results/control.json"),
    )

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


def test_runtime_configuration_artifact_is_digest_linked() -> None:
    items = artifacts("transport")
    runtime = document(items, "runtime-manifests/control.json")
    runtime["configuration_artifacts"] = [
        {
            "kind": "runtime_resources",
            "sha256": artifact(items, "config/bridge.json").sha256,
        }
    ]
    validate_mutation(runtime)

    _validate_links(items)


def test_runtime_configuration_artifact_requires_retained_bytes() -> None:
    items = artifacts("transport")
    runtime = document(items, "runtime-manifests/control.json")
    runtime["configuration_artifacts"] = [{"kind": "host_topology", "sha256": "0" * 64}]
    validate_mutation(runtime)

    with pytest.raises(QualificationError, match="host_topology configuration"):
        _validate_links(items)


def test_recording_summary_cannot_cover_different_sources() -> None:
    items = artifacts("transport")
    summary = artifact(items, "recording-summaries/control.json")
    worker_index = document(items, "evidence-indexes/worker.json")
    worker_index["artifacts"][0]["recording_summary"].update(
        sha256=summary.sha256,
        size_bytes=summary.size_bytes,
    )
    validate_mutation(worker_index)

    with pytest.raises(QualificationError, match="multiple evidence sources"):
        _validate_links(items)


def test_provider_conformance_is_bound_to_runtime_capabilities() -> None:
    items = artifacts("inference")
    runtime = document(items, "runtime-manifests/primary.json")
    runtime["provider_bindings"][0]["capabilities"] = []
    validate_mutation(runtime)

    with pytest.raises(QualificationError, match="capabilities does not match"):
        _validate_links(items)


@pytest.mark.parametrize("case", ["inference", "physical"])
def test_runtime_requires_a_plant_provider_for_every_data_source(case: str) -> None:
    items = artifacts(case)
    runtime_subject = (
        "runtime-manifests/primary.json"
        if case == "inference"
        else "runtime-manifests/controller-domain.json"
    )
    runtime = document(items, runtime_subject)
    runtime["provider_bindings"] = []

    with pytest.raises(ContractValidationError, match="non-empty"):
        validate_mutation(runtime)


def test_playback_runtime_requires_a_recording_source_provider() -> None:
    runtime = deepcopy(document(artifacts("inference"), "runtime-manifests/primary.json"))
    runtime["execution"] = _PLAYBACK
    runtime["clock"]["sync_protocol"] = "playback_clock"
    runtime["provider_bindings"][0]["provider"]["kind"] = "recording_source"
    validate_mutation(runtime)

    runtime["provider_bindings"][0]["provider"]["kind"] = "simulator"
    with pytest.raises(SemanticValidationError, match="recording_source"):
        validate_mutation(runtime)


def test_qualification_rejects_events_before_run_creation() -> None:
    items = artifacts("inference")
    run = document(items, "acceptance-run.json")
    run["created_at"] = "2026-07-11T12:00:01Z"
    validate_mutation(run)

    with pytest.raises(QualificationError, match="chronologically ordered"):
        _validate_links(items)


@pytest.mark.parametrize(
    ("subject_name", "message"),
    [
        ("evidence/control-commands-observation.json", "channel observation"),
        ("evidence/control-worker-clock.json", "clock relation"),
    ],
)
def test_transport_observations_must_occur_during_the_run(
    subject_name: str,
    message: str,
) -> None:
    items = artifacts("transport")
    observation = document(items, subject_name)
    observation["started_at"] = "2026-07-10T12:00:00Z"
    observation["finished_at"] = "2026-07-10T12:00:30Z"
    validate_mutation(observation)

    with pytest.raises(QualificationError, match=message):
        _validate_links(items)


@pytest.mark.parametrize(
    "subject_name",
    [
        "evidence/control-commands-observation.json",
        "evidence/control-worker-clock.json",
    ],
)
def test_transport_observations_must_fit_both_domain_windows(subject_name: str) -> None:
    items = artifacts("transport")
    observation = document(items, subject_name)
    observation["started_at"] = "2026-07-11T12:02:05Z"
    observation["finished_at"] = "2026-07-11T12:02:10Z"
    validate_mutation(observation)

    with pytest.raises(QualificationError, match="domain .* window"):
        _validate_links(items)


def test_run_bound_receipt_must_be_created_during_the_run() -> None:
    items = artifacts("inference")
    receipt = document(items, "evidence/receipt.json")
    verification = document(items, "evidence/verification.json")
    receipt["created_at"] = "2026-07-11T11:57:00Z"
    verification["verified_at"] = "2026-07-11T11:56:00Z"
    validate_mutation(receipt, verification)

    with pytest.raises(QualificationError, match="receipt timeline"):
        _validate_links(items)


def test_scenario_provider_capabilities_are_not_replaced_by_profile_requirements() -> None:
    items = artifacts("inference")
    scenario = document(items, "scenario.json")
    scenario["provider_requirements"]["capabilities"] = ["capability_not_observed"]
    validate_mutation(scenario)

    with pytest.raises(QualificationError, match="do not satisfy capabilities"):
        _validate_links(items)


def test_provider_capabilities_are_derived_from_passing_checks() -> None:
    items = artifacts("inference")
    conformance = document(items, "providers/conformance-result.json")
    conformance["checks"][0]["capability"] = "unrelated_capability"

    with pytest.raises(SemanticValidationError, match="passing checks"):
        validate_mutation(conformance)


def test_scene_requirements_are_checked_against_provider_observation() -> None:
    items = artifacts("inference")
    runtime = document(items, "runtime-manifests/primary.json")
    conformance = document(items, "providers/conformance-result.json")
    runtime["provider_bindings"][0]["scene"]["entities"] = []
    conformance["scene"]["entities"] = []
    validate_mutation(runtime, conformance)

    with pytest.raises(QualificationError, match="satisfy the scene"):
        _validate_links(items)


def test_scene_physical_parameters_distinguish_boolean_from_number() -> None:
    items = artifacts("inference")
    scenario = document(items, "scenario.json")
    runtime = document(items, "runtime-manifests/primary.json")
    conformance = document(items, "providers/conformance-result.json")
    scenario["provider_requirements"]["scene"]["physical_parameters"] = {"gravity_m_s2": 1}
    runtime["provider_bindings"][0]["scene"]["physical_parameters"] = {"gravity_m_s2": True}
    conformance["scene"]["physical_parameters"] = {"gravity_m_s2": True}
    validate_mutation(scenario, runtime, conformance)

    with pytest.raises(QualificationError, match="do not satisfy the scene"):
        _validate_links(items)


def test_evaluator_receipt_requires_a_matching_verified_producer() -> None:
    items = artifacts("inference")
    verification = document(items, "evaluators/verification.json")
    verification["producer_identity"] = "https://example.invalid/forged"
    validate_mutation(verification)

    with pytest.raises(QualificationError, match="producer does not match"):
        _validate_links(items)


def test_evaluator_content_manifest_must_be_retained() -> None:
    items = artifacts("inference")
    verification = document(items, "evaluators/verification.json")
    verification["content_manifest_sha256"] = "0" * 64
    validate_mutation(verification)

    with pytest.raises(QualificationError, match="content manifest"):
        _validate_links(items)


def test_retained_evidence_receipt_is_bound_to_the_run() -> None:
    items = artifacts("inference")
    receipt = document(items, "evidence/receipt.json")
    receipt["run_id"] = "run-20000000-0000-4000-8000-000000000002"
    validate_mutation(receipt)

    with pytest.raises(QualificationError, match="belongs to another run"):
        _validate_links(items)


def test_retained_evidence_verification_is_bound_to_its_statement() -> None:
    items = artifacts("inference")
    verification = document(items, "evidence/verification.json")
    verification["statement_sha256"] = "0" * 64
    validate_mutation(verification)

    with pytest.raises(QualificationError, match="statement does not match"):
        _validate_links(items)


def test_retained_evidence_must_be_verified_before_its_receipt() -> None:
    items = artifacts("inference")
    verification = document(items, "evidence/verification.json")
    verification["verified_at"] = "2026-07-11T12:02:00Z"
    validate_mutation(verification)

    with pytest.raises(QualificationError, match="created before its verification"):
        _validate_links(items)


def test_retained_evidence_receipt_describes_the_indexed_revision() -> None:
    items = artifacts("inference")
    index = document(items, "evidence-indexes/primary.json")
    result = document(items, "results/primary.json")
    index["artifacts"][0]["immutable_revision"] = "version-id:forged"
    result["evidence"][0]["immutable_revision"] = "version-id:forged"
    validate_mutation(index, result)

    with pytest.raises(QualificationError, match="describes different bytes"):
        _validate_links(items)


def test_verified_descriptor_prevents_relabeling_remote_evidence() -> None:
    items = artifacts("inference")
    index = document(items, "evidence-indexes/primary.json")
    result = document(items, "results/primary.json")
    receipt = document(items, "evidence/receipt.json")
    for artifact in (index["artifacts"][0], result["evidence"][0], receipt["artifact"]):
        artifact["immutable_revision"] = "version-id:forged"
    validate_mutation(index, result, receipt)

    with pytest.raises(QualificationError, match="artifact descriptor does not match"):
        _validate_links(items)


def test_transport_trace_uses_artifact_identity_without_segment_index() -> None:
    items = artifacts("transport")
    transport = document(items, "transport-qualification.json")
    for evidence in transport["trace_evidence"]:
        evidence.pop("segment_index")
    validate_mutation(transport)

    _validate_links(items)


def test_result_rejects_duplicate_artifact_identity_without_a_segment() -> None:
    items = artifacts("inference")
    result = document(items, "results/primary.json")
    duplicate = deepcopy(result["evidence"][0])
    duplicate.pop("segment_index")
    result["evidence"].append(duplicate)

    with pytest.raises(SemanticValidationError, match="artifact_id values must be unique"):
        validate_mutation(result)


def test_qualification_artifact_kinds_have_one_schema_catalog() -> None:
    common = load_schema("common.v1")

    assert set(common["$defs"]["qualificationArtifactKind"]["enum"]) == (
        set(_ARTIFACT_ROLES) | set(_RAW_ARTIFACT_KINDS)
    )


@pytest.mark.parametrize(
    ("case", "subject_name", "message"),
    [
        ("transport", "evidence/control.mcap", "indexed size"),
        ("transport", "config/bridge.json", "bridge configuration"),
        ("inference", "models/detector.onnx", "model source artifact"),
        ("inference", "datasets/baseline.mcap", "dataset recording"),
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
