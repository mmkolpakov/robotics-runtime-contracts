from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from robotics_runtime_contracts import SemanticValidationError, validate_document

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(path: str) -> dict[str, object]:
    return yaml.safe_load((FIXTURES / path).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("fixture", "mutation", "expected_path"),
    [
        (
            "v2/valid/simulation-realtime.yaml",
            lambda value: value["timeouts"].update(stable_for_sec=31),
            "$.timeouts.stable_for_sec",
        ),
        (
            "v2/valid/simulation-realtime.yaml",
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
            lambda value: value["inference"].update(fallback_count=1),
            "$.inference.fallback_count",
        ),
        (
            "permit/valid/hil.yaml",
            lambda value: value.update(approver_id=value["operator_id"]),
            "$.approver_id",
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
    document = load_fixture(fixture)
    mutation(document)

    with pytest.raises(SemanticValidationError) as caught:
        validate_document(document)

    assert caught.value.json_path == expected_path
