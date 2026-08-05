from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from robotics_runtime_contracts import (
    ContractValidationError,
    SemanticValidationError,
    validate_document,
)
from tests.support import load_fixture

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("fixture", "mutation", "expected_path"),
    [
        (
            "scenario/valid/simulation-realtime.yaml",
            lambda value: value["timeouts"].update(stable_for_sec=31),
            "$.timeouts.stable_for_sec",
        ),
        (
            "scenario/valid/simulation-realtime.yaml",
            lambda value: value["expected_ros_graph"]["topics"].append(
                deepcopy(value["expected_ros_graph"]["topics"][0])
            ),
            "$.expected_ros_graph.topics",
        ),
        (
            "dataset/valid/camera-mcap.yaml",
            lambda value: value["time"].update(end_ns=value["time"]["start_ns"]),
            "$.time.end_ns",
        ),
        (
            "runtime/valid/cpu-simulation.yaml",
            lambda value: value["workload"]["inference"].update(fallback_count=1),
            "$.workload.inference.fallback_count",
        ),
        (
            "runtime/valid/no-inference-simulation.yaml",
            lambda value: value["clock"].update(sync_protocol="playback_clock"),
            "$.clock.sync_protocol",
        ),
        (
            "runtime/valid/no-inference-simulation.yaml",
            lambda value: value.update(
                schema_version="runtime-manifest.v2",
                configuration_artifacts=[
                    {"kind": "host_topology", "sha256": "a" * 64},
                    {"kind": "host_topology", "sha256": "b" * 64},
                ],
            ),
            "$.configuration_artifacts",
        ),
        (
            "result/valid/passed.yaml",
            lambda value: value["clock_observation"].update(monotonic=False),
            "$.clock_observation.monotonic",
        ),
    ],
)
def test_cross_field_invariants(
    fixture: str,
    mutation: object,
    expected_path: str,
) -> None:
    document = load_fixture(FIXTURES / fixture)
    mutation(document)

    with pytest.raises(SemanticValidationError) as caught:
        validate_document(document)

    assert caught.value.json_path == expected_path


def test_invalid_date_time_reports_contract_path() -> None:
    document = load_fixture(FIXTURES / "physical/valid/hil-permit.yaml")
    document["issued_at"] = "not-a-date"

    with pytest.raises(ContractValidationError) as caught:
        validate_document(document)

    assert caught.value.json_path == "$.issued_at"


def test_semantic_timestamp_parser_accepts_rfc3339_lowercase_utc_designator() -> None:
    document = load_fixture(FIXTURES / "physical/valid/hil-permit.yaml")
    document["issued_at"] = document["issued_at"].replace("Z", "z")
    document["expires_at"] = document["expires_at"].replace("Z", "z")
    document["interlock_check"]["checked_at"] = document["interlock_check"]["checked_at"].replace(
        "Z", "z"
    )

    validate_document(document)


@pytest.mark.parametrize(
    ("fixture", "mutation", "expected_path"),
    [
        (
            "scenario/valid/simulation-realtime.yaml",
            lambda value: value["forbidden_ros_graph"]["topics"].extend(["/cmd_vel", "/cmd_vel"]),
            "$.forbidden_ros_graph.topics",
        ),
        (
            "runtime/valid/no-inference-simulation.yaml",
            lambda value: value["physical_targets"].append(
                {
                    "target_id": "controller",
                    "scope": "controller",
                    "identity_kind": "udev_serial",
                    "identity_sha256": "a" * 64,
                    "preflight_evidence_sha256": "b" * 64,
                    "stable_device_path": "/dev/robotics/controller",
                }
            ),
            "$.physical_targets",
        ),
    ],
)
def test_schema_owned_invariants_remain_enforced(
    fixture: str,
    mutation: object,
    expected_path: str,
) -> None:
    document = load_fixture(FIXTURES / fixture)
    mutation(document)

    with pytest.raises(ContractValidationError) as caught:
        validate_document(document)

    assert caught.value.json_path == expected_path
