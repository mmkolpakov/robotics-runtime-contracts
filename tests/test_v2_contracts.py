from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

from robotics_runtime_contracts import (
    ContractValidationError,
    SemanticValidationError,
    migrate_scenario_v1_to_v2,
    validate_document,
    validate_scenario,
)

FIXTURES = Path(__file__).parent / "fixtures"
RUN_ID = "run-01234567-89ab-4def-8123-456789abcdef"
RESULT_ID = "result-01234567-89ab-4def-8123-456789abcdef"
AGGREGATE_ID = "aggregate-01234567-89ab-4def-8123-456789abcdef"
SHA256 = "a" * 64
EVIDENCE_SHA256 = "d" * 64


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def result_v2() -> dict[str, Any]:
    result = load_yaml(FIXTURES / "result" / "valid" / "passed.yaml")
    result.update(
        {
            "schema_version": "acceptance-result.v2",
            "result_id": RESULT_ID,
            "run_id": RUN_ID,
            "scenario_id": "org.example.camera-stream",
            "domain_id": "camera-domain",
            "verdict_scope": "domain",
            "unevaluated": [],
            "time_authority_observation": {
                "source_id": "simulation-clock",
                "sample_count": 30,
                "window_start_ns": 1,
                "window_end_ns": 30,
                "p50_offset_ms": 0.1,
                "p95_offset_ms": 0.2,
                "max_offset_ms": 0.3,
                "within_policy": True,
                "evidence_sha256": EVIDENCE_SHA256,
            },
        }
    )
    return result


def result_v3() -> dict[str, Any]:
    result = result_v2()
    result["schema_version"] = "acceptance-result.v3"
    return result


def ndjson_evidence() -> dict[str, Any]:
    return {
        "uri": "file:///evidence/traces.otlp.jsonl",
        "media_type": "application/x-ndjson",
        "sha256": "e" * 64,
        "size_bytes": 512,
        "retention_class": "pull-request-7d",
        "segment_index": 1,
    }


def test_v1_scenario_migrates_to_valid_v2_without_inventing_selectors() -> None:
    scenario = load_yaml(FIXTURES / "scenario" / "valid" / "simulation-realtime.yaml")
    migrated = migrate_scenario_v1_to_v2(
        scenario,
        metric_attributes={"camera-age": {"domain.id": "camera-domain", "topic": "/camera/image"}},
        time_authority_min_samples=30,
        max_clock_offset_p50_ms=1,
        max_clock_offset_p95_ms=2,
        max_clock_offset_ms=5,
    )

    validate_scenario(scenario)
    validate_scenario(migrated)
    assert migrated["assertions"][0]["attribute_match"]["topic"] == "/camera/image"
    assert scenario["schema_version"] == "acceptance-scenario.v1"


def test_v1_migration_rejects_missing_metric_selector() -> None:
    scenario = load_yaml(FIXTURES / "scenario" / "valid" / "simulation-realtime.yaml")

    with pytest.raises(ValueError, match="camera-age"):
        migrate_scenario_v1_to_v2(
            scenario,
            metric_attributes={},
            time_authority_min_samples=30,
            max_clock_offset_p50_ms=1,
            max_clock_offset_p95_ms=2,
            max_clock_offset_ms=5,
        )


def test_v2_scenario_rejects_unsorted_time_authority_thresholds() -> None:
    scenario = load_yaml(FIXTURES / "scenario" / "valid" / "simulation-realtime.yaml")
    migrated = migrate_scenario_v1_to_v2(
        scenario,
        metric_attributes={"camera-age": {"domain.id": "camera-domain"}},
        time_authority_min_samples=30,
        max_clock_offset_p50_ms=3,
        max_clock_offset_p95_ms=2,
        max_clock_offset_ms=5,
    )

    with pytest.raises(SemanticValidationError, match="p50 <= p95 <= max"):
        validate_scenario(migrated)


def test_v2_physical_constraints_remain_enforced_after_allof_cleanup() -> None:
    scenario = load_yaml(FIXTURES / "physical" / "valid" / "hil-scenario.yaml")
    migrated = migrate_scenario_v1_to_v2(
        scenario,
        metric_attributes={},
        time_authority_min_samples=30,
        max_clock_offset_p50_ms=1,
        max_clock_offset_p95_ms=2,
        max_clock_offset_ms=5,
    )
    validate_scenario(migrated)

    real_observation = deepcopy(migrated)
    real_observation["execution"]["target_environment"] = "real_robot"
    real_observation["execution"]["physical_effect"] = "observation"
    validate_scenario(real_observation)

    real_actuation = deepcopy(real_observation)
    real_actuation["execution"]["physical_effect"] = "actuation"
    with pytest.raises(ContractValidationError):
        validate_scenario(real_actuation)


def test_v2_passed_result_requires_complete_evaluation() -> None:
    result = result_v2()
    validate_document(result)

    result["unevaluated"] = ["$.evidence_policy.topics"]
    with pytest.raises(ContractValidationError) as caught:
        validate_document(result)
    assert caught.value.json_path == "$.unevaluated"


def test_v2_result_remains_immutable_and_rejects_ndjson_evidence() -> None:
    result = result_v2()
    result["evidence"].append(ndjson_evidence())

    with pytest.raises(ContractValidationError) as caught:
        validate_document(result)

    assert caught.value.json_path == "$.evidence[1].media_type"


def test_v3_result_accepts_verified_ndjson_evidence() -> None:
    result = result_v3()
    result["evidence"].append(ndjson_evidence())

    validate_document(result)


@pytest.mark.parametrize("status", ["failed", "error"])
def test_v2_known_failure_can_retain_unevaluated_fields(status: str) -> None:
    result = result_v2()
    result["status"] = status
    result["unevaluated"] = ["$.evidence_policy.topics"]

    validate_document(result)


@pytest.mark.parametrize(
    ("assertion_status", "result_status"),
    [
        ("error", "incomplete"),
        ("error", "failed"),
        ("failed", "incomplete"),
        ("failed", "cancelled"),
    ],
)
def test_v2_result_cannot_hide_a_more_severe_assertion(
    assertion_status: str,
    result_status: str,
) -> None:
    result = result_v2()
    result["assertion_results"][0]["status"] = assertion_status
    result["status"] = result_status
    result["unevaluated"] = ["$.evidence_policy.topics"]

    with pytest.raises(SemanticValidationError, match="less severe"):
        validate_document(result)


def test_v2_incomplete_result_accepts_a_skipped_assertion() -> None:
    result = result_v2()
    result["assertion_results"][0]["status"] = "skipped"
    result["status"] = "incomplete"
    result["unevaluated"] = ["$.assertions.domain-smoke"]

    validate_document(result)


def test_v2_result_rejects_contradictory_lifecycle_observations() -> None:
    result = result_v2()
    result["lifecycle_states"] = [
        {"node": "/controller", "state": "active", "observed_at_ns": 10},
        {"node": "/controller", "state": "inactive", "observed_at_ns": 10},
    ]

    with pytest.raises(SemanticValidationError, match="observed_at_ns pairs"):
        validate_document(result)


@pytest.mark.parametrize("field", ["assertion_results", "evidence"])
def test_v2_passed_result_requires_assertions_and_evidence(field: str) -> None:
    result = result_v2()
    result[field] = []

    with pytest.raises(ContractValidationError) as caught:
        validate_document(result)
    assert caught.value.json_path == f"$.{field}"


def test_v2_passed_result_requires_time_authority_samples() -> None:
    result = result_v2()
    result["time_authority_observation"]["sample_count"] = 0

    with pytest.raises(ContractValidationError) as caught:
        validate_document(result)
    assert caught.value.json_path == "$.time_authority_observation.sample_count"


def test_v2_time_authority_evidence_must_be_listed() -> None:
    result = result_v2()
    result["time_authority_observation"]["evidence_sha256"] = "e" * 64

    with pytest.raises(SemanticValidationError) as caught:
        validate_document(result)
    assert caught.value.json_path == "$.time_authority_observation.evidence_sha256"


def test_v2_time_authority_evidence_can_reference_listed_item() -> None:
    result = result_v2()

    validate_document(result)
    assert (
        result["time_authority_observation"]["evidence_sha256"] == result["evidence"][0]["sha256"]
    )


@pytest.mark.parametrize(
    ("status", "unevaluated"),
    [
        ("failed", []),
        ("incomplete", ["$.time_authority_observation"]),
    ],
)
def test_v2_early_nonpassing_result_can_report_no_measurements(
    status: str,
    unevaluated: list[str],
) -> None:
    result = result_v2()
    result["status"] = status
    result["unevaluated"] = unevaluated
    result["assertion_results"] = []
    result["evidence"] = []
    result["time_authority_observation"] = {
        "source_id": "simulation-clock",
        "sample_count": 0,
        "window_start_ns": 0,
        "window_end_ns": 0,
        "p50_offset_ms": 0,
        "p95_offset_ms": 0,
        "max_offset_ms": 0,
        "within_policy": False,
    }

    validate_document(result)


def test_v2_incomplete_result_requires_an_unevaluated_declaration() -> None:
    result = result_v2()
    result["status"] = "incomplete"

    with pytest.raises(ContractValidationError) as caught:
        validate_document(result)
    assert caught.value.json_path == "$.unevaluated"


def test_acceptance_aggregate_rejects_incorrect_status() -> None:
    aggregate = {
        "schema_version": "acceptance-aggregate.v1",
        "aggregate_id": AGGREGATE_ID,
        "run_id": RUN_ID,
        "acceptance_run_sha256": SHA256,
        "generated_at": "2026-07-26T12:00:00Z",
        "per_domain_results": [
            {
                "domain_id": "camera-domain",
                "result_id": RESULT_ID,
                "result_sha256": SHA256,
                "status": "failed",
            }
        ],
        "per_domain_aggregate": "passed",
        "cross_domain_e2e": {
            "status": "unevaluated",
            "reason": "trace_evidence_not_evaluated",
        },
    }

    with pytest.raises(SemanticValidationError, match="aggregate domain status"):
        validate_document(aggregate)


def test_evidence_index_v2_requires_summary_for_mcap() -> None:
    index = {
        "schema_version": "evidence-index.v2",
        "run_id": RUN_ID,
        "generated_at": "2026-07-26T12:00:00Z",
        "finalized": True,
        "policy_observation": {
            "recording_mode": "bounded",
            "compression": "zstd",
            "upload_mode": "local_only",
            "remote_sink_used": False,
            "spool_peak_size_bytes": 1024,
            "upload_lag_max_sec": 0,
        },
        "segments": [
            {
                "uri": "file:///evidence/run_0.mcap",
                "local_path": "/evidence/run_0.mcap",
                "media_type": "application/mcap",
                "sha256": SHA256,
                "size_bytes": 1024,
                "retention_class": "pull-request-7d",
                "segment_index": 0,
                "upload_status": "local",
                "checksum_verified": True,
            }
        ],
    }

    with pytest.raises(ContractValidationError) as caught:
        validate_document(index)
    assert caught.value.json_path == "$.segments[0]"


def test_mcap_summary_requires_consistent_channel_count() -> None:
    summary = {
        "schema_version": "mcap-summary.v1",
        "source_sha256": SHA256,
        "compressions": ["zstd"],
        "statistics": {
            "message_count": 10,
            "schema_count": 1,
            "channel_count": 1,
            "attachment_count": 0,
            "metadata_count": 1,
            "chunk_count": 1,
            "message_start_time_ns": 1,
            "message_end_time_ns": 2,
        },
        "channels": [
            {
                "topic": "/camera/image",
                "message_encoding": "cdr",
                "schema_name": "sensor_msgs/msg/Image",
                "message_count": 10,
            }
        ],
    }
    validate_document(summary)

    invalid = deepcopy(summary)
    invalid["statistics"]["channel_count"] = 2
    with pytest.raises(SemanticValidationError, match="summarized channels"):
        validate_document(invalid)
