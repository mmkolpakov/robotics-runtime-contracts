from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from robotics_runtime_contracts import (
    ContractValidationError,
    SemanticValidationError,
    validate_document,
)
from tests.support import load_fixture

FIXTURES = Path(__file__).parent / "fixtures" / "result"


def result() -> dict[str, Any]:
    return load_fixture(FIXTURES / "valid" / "passed.yaml")


def test_passed_result_requires_complete_evaluation() -> None:
    document = result()
    document["unevaluated"] = ["$.evidence_policy.topics"]

    with pytest.raises(ContractValidationError) as caught:
        validate_document(document)

    assert caught.value.json_path == "$.unevaluated"


def test_result_rejects_unknown_time_authority_statistics() -> None:
    document = result()
    document["time_authority_observation"]["unknown_statistic_ms"] = 1

    with pytest.raises(ContractValidationError) as caught:
        validate_document(document)

    assert caught.value.json_path == "$.time_authority_observation"


def test_result_accepts_streaming_trace_evidence() -> None:
    document = result()
    document["evidence"].append(
        {
            "uri": "file:///evidence/traces.otlp.jsonl",
            "media_type": "application/x-ndjson",
            "sha256": "e" * 64,
            "size_bytes": 512,
            "retention_class": "pull-request-7d",
            "segment_index": 1,
        }
    )

    validate_document(document)


def test_result_rejects_unsorted_delivery_latency_statistics() -> None:
    document = result()
    document["time_authority_observation"]["p50_delivery_latency_ms"] = 1
    document["time_authority_observation"]["p95_delivery_latency_ms"] = 0.5

    with pytest.raises(SemanticValidationError, match="p50 <= p95 <= max"):
        validate_document(document)


@pytest.mark.parametrize("status", ["failed", "error"])
def test_known_failure_can_retain_unevaluated_fields(status: str) -> None:
    document = result()
    document["status"] = status
    document["unevaluated"] = ["$.evidence_policy.topics"]

    validate_document(document)


@pytest.mark.parametrize(
    ("assertion_status", "result_status"),
    [
        ("error", "incomplete"),
        ("error", "failed"),
        ("failed", "incomplete"),
        ("failed", "cancelled"),
    ],
)
def test_result_cannot_hide_a_more_severe_assertion(
    assertion_status: str,
    result_status: str,
) -> None:
    document = result()
    document["assertion_results"][0]["status"] = assertion_status
    document["status"] = result_status
    document["unevaluated"] = ["$.evidence_policy.topics"]

    with pytest.raises(SemanticValidationError, match="less severe"):
        validate_document(document)


@pytest.mark.parametrize("assertion_status", ["error", "failed"])
def test_passed_result_requires_passed_assertions(assertion_status: str) -> None:
    document = result()
    document["assertion_results"][0]["status"] = assertion_status

    with pytest.raises(ContractValidationError):
        validate_document(document)


def test_incomplete_result_accepts_a_skipped_assertion() -> None:
    document = result()
    document["assertion_results"][0]["status"] = "skipped"
    document["status"] = "incomplete"
    document["unevaluated"] = ["$.assertions.camera-age"]

    validate_document(document)


def test_result_accepts_a_non_inference_workload() -> None:
    document = result()
    document["workload"] = {"kind": "none"}
    document.pop("model_manifest_sha256")

    validate_document(document)


def test_inference_result_requires_a_model_manifest() -> None:
    document = result()
    document.pop("model_manifest_sha256")

    with pytest.raises(ContractValidationError):
        validate_document(document)


def test_result_rejects_contradictory_lifecycle_observations() -> None:
    document = result()
    document["lifecycle_states"] = [
        {"node": "/controller", "state": "active", "observed_at_ns": 10},
        {"node": "/controller", "state": "inactive", "observed_at_ns": 10},
    ]

    with pytest.raises(SemanticValidationError, match="observed_at_ns pairs"):
        validate_document(document)


@pytest.mark.parametrize("field", ["assertion_results", "evidence"])
def test_passed_result_requires_assertions_and_evidence(field: str) -> None:
    document = result()
    document[field] = []

    with pytest.raises(ContractValidationError) as caught:
        validate_document(document)

    assert caught.value.json_path == f"$.{field}"


def test_passed_result_requires_time_authority_samples() -> None:
    document = result()
    document["time_authority_observation"]["sample_count"] = 0

    with pytest.raises(ContractValidationError) as caught:
        validate_document(document)

    assert caught.value.json_path == "$.time_authority_observation.sample_count"


def test_time_authority_evidence_must_be_listed() -> None:
    document = result()
    document["time_authority_observation"]["evidence_sha256"] = "e" * 64

    with pytest.raises(SemanticValidationError) as caught:
        validate_document(document)

    assert caught.value.json_path == "$.time_authority_observation.evidence_sha256"


@pytest.mark.parametrize(
    ("status", "unevaluated"),
    [
        ("failed", []),
        ("incomplete", ["$.time_authority_observation"]),
    ],
)
def test_nonpassing_result_can_report_no_measurements(
    status: str,
    unevaluated: list[str],
) -> None:
    document = result()
    document["status"] = status
    document["unevaluated"] = unevaluated
    document["assertion_results"] = []
    document["evidence"] = []
    document["time_authority_observation"] = {
        "source_id": "simulation-clock",
        "sample_count": 0,
        "window_start_ns": 0,
        "window_end_ns": 0,
        "p50_delivery_latency_ms": 0,
        "p95_delivery_latency_ms": 0,
        "max_delivery_latency_ms": 0,
        "within_policy": False,
    }

    validate_document(document)


def test_incomplete_result_requires_an_unevaluated_declaration() -> None:
    document = result()
    document["status"] = "incomplete"

    with pytest.raises(ContractValidationError) as caught:
        validate_document(document)

    assert caught.value.json_path == "$.unevaluated"
