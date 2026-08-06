from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from robotics_runtime_contracts import (
    ContractValidationError,
    SchemaCompatibilityError,
    SemanticValidationError,
    UnknownCompatibilityRuleError,
    load_mapping,
    loads_mapping,
    validate_companion_schema,
    validate_document,
)
from tests.support import load_fixture

FIXTURES = Path(__file__).parent / "fixtures"


def current_scenario() -> dict[str, object]:
    scenario = load_fixture(FIXTURES / "scenario" / "valid" / "simulation-realtime.yaml")
    scenario["schema_version"] = "acceptance-scenario.v5"
    scenario["metric_definitions"] = [
        {
            "metric_name": "robotics.message.age",
            "unit": "ms",
            "instrument_kind": "histogram",
            "temporality": "delta",
        },
        {
            "metric_name": "org.example.temperature",
            "unit": "Cel",
            "instrument_kind": "gauge",
            "temporality": "instantaneous",
        },
    ]
    scenario["assertions"].append(
        {
            "assertion_id": "temperature-stable",
            "kind": "metric_duration",
            "metric_name": "org.example.temperature",
            "unit": "Cel",
            "operator": "lte",
            "threshold": 75,
            "window_sec": 30,
            "max_sample_gap_sec": 1,
            "duration_requirement": {"kind": "minimum_contiguous", "duration_sec": 10},
            "attribute_match": {"sensor": "spindle"},
        }
    )
    return scenario


def test_current_scenario_resolves_external_schema_references_offline() -> None:
    validate_document(current_scenario())


def test_current_scenario_inherits_execution_invariants() -> None:
    scenario = current_scenario()
    scenario["execution"]["plant_backend"] = "recorded_data"

    with pytest.raises(ContractValidationError):
        validate_document(scenario)


def test_current_scenario_rejects_unknown_core_metric() -> None:
    scenario = current_scenario()
    scenario["metric_definitions"][0]["metric_name"] = "robotics.product.secret"

    with pytest.raises(SemanticValidationError, match="reserved robotics"):
        validate_document(scenario)


def test_current_result_requires_product_evidence_ownership() -> None:
    result = load_fixture(FIXTURES / "result" / "valid" / "passed.yaml")
    result["schema_version"] = "acceptance-result.v5"
    result["evaluation_mode"] = "live"
    result["assertion_results"][0]["source"] = "core"
    result["assertion_results"].append(
        {
            "assertion_id": "org.example.sorting.shape",
            "source": "product",
            "namespace": "org.example.sorting",
            "status": "passed",
            "observed_value": "round",
            "unit": "1",
            "evidence_sha256": ["d" * 64],
        }
    )
    result["observed_ros_graph"]["services"] = [
        {
            "name": "/controller/reset",
            "type": "example_interfaces/srv/Trigger",
            "server_nodes": 1,
            "client_nodes": 1,
        }
    ]
    validate_document(result)

    result["assertion_results"][-1]["assertion_id"] = "foreign.assertion"
    with pytest.raises(SemanticValidationError, match="owned by its namespace"):
        validate_document(result)


def test_current_runtime_accepts_namespaced_configuration_kind() -> None:
    runtime = load_fixture(FIXTURES / "runtime" / "valid" / "cpu-simulation.yaml")
    runtime["schema_version"] = "runtime-manifest.v3"
    runtime["configuration_artifacts"] = [{"kind": "org.example.device_map", "sha256": "a" * 64}]
    validate_document(runtime)

    runtime["configuration_artifacts"][0]["kind"] = "device_map"
    with pytest.raises(SemanticValidationError, match="reverse-domain"):
        validate_document(runtime)


def test_current_runtime_inherits_physical_target_invariants() -> None:
    runtime = load_fixture(FIXTURES / "runtime" / "valid" / "cpu-simulation.yaml")
    runtime["schema_version"] = "runtime-manifest.v3"
    runtime["physical_targets"] = [
        {
            "target_id": "controller-alpha",
            "scope": "controller",
            "identity_kind": "mavlink_system_component",
            "identity_sha256": "e" * 64,
            "preflight_evidence_sha256": "f" * 64,
            "stable_device_path": "/dev/robotics/controller-alpha",
        }
    ]

    with pytest.raises(ContractValidationError):
        validate_document(runtime)


def test_current_evidence_accepts_vendor_media_type() -> None:
    evidence = load_fixture(FIXTURES / "evidence-index" / "valid" / "mixed.yaml")
    evidence["schema_version"] = "evidence-index.v3"
    evidence["segments"].append(
        {
            "uri": "file:///evidence/controller.ulg",
            "local_path": "/evidence/controller.ulg",
            "media_type": "application/vnd.example.ulog",
            "sha256": "e" * 64,
            "size_bytes": 128,
            "retention_class": "regression-30d",
            "segment_index": 2,
            "upload_status": "local",
            "checksum_verified": True,
        }
    )
    validate_document(evidence)


def test_clock_relation_and_transport_v2_are_consistent() -> None:
    relation = {
        "schema_version": "clock-relation.v1",
        "relation_id": "control-worker-clock",
        "run_id": "run-00000000-0000-4000-8000-000000000001",
        "scenario_sha256": "c" * 64,
        "source_domain_id": "control",
        "destination_domain_id": "worker",
        "method": "measured_skew",
        "sync_protocol": "ptp",
        "started_at": "2026-07-26T12:00:00Z",
        "finished_at": "2026-07-26T12:00:30Z",
        "sample_count": 30,
        "max_absolute_skew_ms": 0.5,
        "policy": {
            "method": "measured_skew",
            "minimum_samples": 30,
            "maximum_absolute_skew_ms": 1,
        },
        "status": "passed",
        "violations": [],
        "evidence_sha256": "a" * 64,
    }
    validate_document(relation)

    transport_path = FIXTURES / "qualification" / "transport" / "transport.json"
    transport = json.loads(transport_path.read_text(encoding="utf-8"))
    transport["schema_version"] = "transport-qualification-result.v2"
    transport["scenario_sha256"] = "c" * 64
    transport["clock_relations"] = [
        {
            "relation_id": relation["relation_id"],
            "source_domain_id": relation["source_domain_id"],
            "destination_domain_id": relation["destination_domain_id"],
            "sha256": "b" * 64,
            "status": "passed",
        }
    ]
    validate_document(transport)

    broken = deepcopy(relation)
    broken["max_absolute_skew_ms"] = 2
    with pytest.raises(SemanticValidationError, match="contradicts measured clock skew"):
        validate_document(broken)

    undersampled = deepcopy(relation)
    undersampled["sample_count"] = 29
    with pytest.raises(SemanticValidationError, match="contradicts measured clock skew"):
        validate_document(undersampled)

    non_finite = deepcopy(relation)
    non_finite["max_absolute_skew_ms"] = float("nan")
    with pytest.raises(ValueError, match="non-finite"):
        validate_document(non_finite)


def test_shared_clock_identity_does_not_claim_measured_skew() -> None:
    relation = {
        "schema_version": "clock-relation.v1",
        "relation_id": "source-destination-clock",
        "run_id": "run-00000000-0000-4000-8000-000000000001",
        "scenario_sha256": "c" * 64,
        "source_domain_id": "source",
        "destination_domain_id": "destination",
        "method": "shared_clock_identity",
        "sync_protocol": "shared_kernel_clock",
        "started_at": "2026-07-26T12:00:00Z",
        "finished_at": "2026-07-26T12:00:30Z",
        "policy": {"method": "shared_clock_identity"},
        "shared_clock_identity": {
            "authority": "shared-linux-kernel-clock-realtime",
            "boot_id": "00000000-0000-4000-8000-000000000001",
            "implementation": "clock_gettime(CLOCK_REALTIME)",
            "resolution_sec": 1e-9,
            "source_observation_sha256": "a" * 64,
            "destination_observation_sha256": "b" * 64,
        },
        "status": "passed",
        "violations": [],
        "evidence_sha256": "d" * 64,
    }
    validate_document(relation)

    relation["max_absolute_skew_ms"] = 0
    with pytest.raises(ContractValidationError):
        validate_document(relation)


def test_scenario_companion_version_matrix_is_public() -> None:
    validate_companion_schema(
        "acceptance-scenario.v5",
        "runtime_manifest",
        "runtime-manifest.v3",
    )

    with pytest.raises(SchemaCompatibilityError, match="requires runtime-manifest.v3"):
        validate_companion_schema(
            "acceptance-scenario.v5",
            "runtime_manifest",
            "runtime-manifest.v2",
        )

    validate_companion_schema(
        "acceptance-scenario.v4",
        "runtime_manifest",
        "runtime-manifest.v1",
    )
    validate_companion_schema(
        "acceptance-scenario.v4",
        "runtime_manifest",
        "runtime-manifest.v2",
    )
    with pytest.raises(SchemaCompatibilityError, match="runtime-manifest.v3"):
        validate_companion_schema(
            "acceptance-scenario.v4",
            "runtime_manifest",
            "runtime-manifest.v3",
        )

    validate_companion_schema(
        "acceptance-scenario.v4",
        "transport_qualification",
        "transport-qualification-result.v1",
    )
    with pytest.raises(
        SchemaCompatibilityError,
        match="requires transport-qualification-result.v1",
    ):
        validate_companion_schema(
            "acceptance-scenario.v4",
            "transport_qualification",
            "transport-qualification-result.v2",
        )


def test_json_loader_preserves_scientific_notation(tmp_path: Path) -> None:
    path = tmp_path / "clock.json"
    path.write_text(json.dumps({"resolution_sec": 1e-9}), encoding="utf-8")

    assert load_mapping(path)["resolution_sec"] == 1e-9


@pytest.mark.parametrize("value", ['{"value": NaN}', "value: .nan"])
def test_document_loader_rejects_non_finite_numbers(value: str) -> None:
    with pytest.raises(ValueError, match="non-finite"):
        loads_mapping(value)


@pytest.mark.parametrize(
    ("scenario", "kind"),
    [
        ("acceptance-scenario.v99", "runtime_manifest"),
        ("acceptance-scenario.v5", "typo"),
    ],
)
def test_companion_matrix_rejects_unknown_rules(scenario: str, kind: str) -> None:
    with pytest.raises(UnknownCompatibilityRuleError):
        validate_companion_schema(scenario, kind, "runtime-manifest.v3")


def test_current_result_accepts_vendor_evidence_end_to_end() -> None:
    result = load_fixture(FIXTURES / "result" / "valid" / "passed.yaml")
    result["schema_version"] = "acceptance-result.v5"
    result["evaluation_mode"] = "live"
    for assertion in result["assertion_results"]:
        assertion["source"] = "core"
    result["evidence"].append(
        {
            "uri": "file:///evidence/controller.ulg",
            "media_type": "application/vnd.example.ulog",
            "sha256": "e" * 64,
            "size_bytes": 128,
            "retention_class": "regression-30d",
            "segment_index": 2,
        }
    )
    validate_document(result)


def test_current_result_rejects_skipped_assertion_with_passed_verdict() -> None:
    result = load_fixture(FIXTURES / "result" / "valid" / "passed.yaml")
    result["schema_version"] = "acceptance-result.v5"
    result["evaluation_mode"] = "live"
    for assertion in result["assertion_results"]:
        assertion["source"] = "core"
    result["assertion_results"][0]["status"] = "skipped"

    with pytest.raises(ContractValidationError, match="'passed' was expected"):
        validate_document(result)


def test_current_result_inherits_verdict_invariants() -> None:
    result = load_fixture(FIXTURES / "result" / "valid" / "passed.yaml")
    result["schema_version"] = "acceptance-result.v5"
    result["evaluation_mode"] = "live"
    result["unevaluated"] = ["$.time_authority_observation"]
    for assertion in result["assertion_results"]:
        assertion["source"] = "core"

    with pytest.raises(ContractValidationError):
        validate_document(result)


def test_campaign_verdict_is_derived_from_run_statuses() -> None:
    campaign = {
        "schema_version": "campaign-summary.v1",
        "campaign_id": "campaign-00000000-0000-4000-8000-000000000001",
        "scenario_id": "org.example.camera-stream",
        "scenario_sha256": "c" * 64,
        "generated_at": "2026-07-26T12:05:00Z",
        "runs": [
            {
                "run_id": "run-00000000-0000-4000-8000-000000000001",
                "acceptance_run_sha256": "b" * 64,
                "aggregate_sha256": "a" * 64,
                "parameters": {"seed": 1},
                "status": "passed",
            }
        ],
        "acceptance": {
            "minimum_passed_runs": 1,
            "maximum_failed_runs": 0,
            "maximum_incomplete_runs": 0,
            "maximum_error_runs": 0,
        },
        "verdict": {
            "status": "passed",
            "total_runs": 1,
            "passed_runs": 1,
            "failed_runs": 0,
            "incomplete_runs": 0,
            "error_runs": 0,
        },
    }
    validate_document(campaign)
