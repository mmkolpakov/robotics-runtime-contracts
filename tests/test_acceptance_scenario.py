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

FIXTURES = Path(__file__).parent / "fixtures" / "scenario"


def scenario(*, stepped: bool = False) -> dict[str, Any]:
    document = load_fixture(FIXTURES / "valid" / "simulation-realtime.yaml")
    if stepped:
        execution = document["execution"]
        policy = document["time_policy"]
        execution["time_mode"] = "simulation_stepped"
        policy.pop("min_realtime_factor")
        policy.pop("max_deadline_miss_ratio")
        policy.update(step_size_sec=0.01, max_skipped_steps=0)
    return document


def test_stepped_simulation_accepts_an_explicit_skip_budget() -> None:
    validate_document(scenario(stepped=True))


def test_stepped_simulation_requires_a_skip_budget() -> None:
    document = scenario(stepped=True)
    document["time_policy"].pop("max_skipped_steps")

    with pytest.raises(ContractValidationError) as caught:
        validate_document(document)

    assert caught.value.json_path == "$.time_policy"


def test_realtime_simulation_rejects_a_skip_budget() -> None:
    document = scenario()
    document["time_policy"]["max_skipped_steps"] = 1

    with pytest.raises(ContractValidationError) as caught:
        validate_document(document)

    assert caught.value.json_path == "$.time_policy"


def test_scenario_rejects_unknown_time_authority_thresholds() -> None:
    document = scenario()
    document["time_policy"]["unknown_threshold_ms"] = 1

    with pytest.raises(ContractValidationError) as caught:
        validate_document(document)

    assert caught.value.json_path == "$.time_policy"


def test_scenario_rejects_unsorted_delivery_latency_thresholds() -> None:
    document = scenario()
    document["time_policy"]["max_time_authority_delivery_latency_p50_ms"] = 3

    with pytest.raises(SemanticValidationError, match="p50 <= p95 <= max"):
        validate_document(document)


def test_scenario_rejects_runtime_owned_assertion_ids() -> None:
    document = scenario()
    document["assertions"][0]["assertion_id"] = "time-policy"

    with pytest.raises(SemanticValidationError, match="reserved") as caught:
        validate_document(document)

    assert caught.value.json_path == "$.assertions[0].assertion_id"
