from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from robotics_runtime_contracts import (
    ContractValidationError,
    SemanticValidationError,
    validate_scenario,
)

FIXTURE = Path(__file__).parent / "fixtures" / "scenario" / "valid" / "simulation-realtime.yaml"


def scenario_v3(*, stepped: bool = False) -> dict[str, Any]:
    scenario: dict[str, Any] = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    scenario["schema_version"] = "acceptance-scenario.v3"
    for assertion in scenario["assertions"]:
        assertion["attribute_match"] = {"domain.id": "foundation"}
    scenario["time_policy"].update(
        {
            "time_authority_min_samples": 30,
            "max_clock_offset_p50_ms": 1,
            "max_clock_offset_p95_ms": 2,
            "max_clock_offset_ms": 5,
        }
    )
    if stepped:
        scenario["execution"]["time_mode"] = "simulation_stepped"
        scenario["time_policy"].pop("min_realtime_factor")
        scenario["time_policy"].pop("max_deadline_miss_ratio")
        scenario["time_policy"]["step_size_sec"] = 0.01
    return scenario


def scenario_v4(*, stepped: bool = False) -> dict[str, Any]:
    scenario = scenario_v3(stepped=stepped)
    scenario["schema_version"] = "acceptance-scenario.v4"
    policy = scenario["time_policy"]
    policy["max_time_authority_delivery_latency_p50_ms"] = policy.pop("max_clock_offset_p50_ms")
    policy["max_time_authority_delivery_latency_p95_ms"] = policy.pop("max_clock_offset_p95_ms")
    policy["max_time_authority_delivery_latency_ms"] = policy.pop("max_clock_offset_ms")
    return scenario


def test_v3_realtime_scenario_remains_valid_without_skip_budget() -> None:
    validate_scenario(scenario_v3())


def test_v3_stepped_scenario_requires_explicit_skip_budget() -> None:
    scenario = scenario_v3(stepped=True)

    with pytest.raises(ContractValidationError) as caught:
        validate_scenario(scenario)

    assert caught.value.json_path == "$.time_policy"

    scenario["time_policy"]["max_skipped_steps"] = 0
    validate_scenario(scenario)


def test_v3_rejects_skip_budget_outside_stepped_simulation() -> None:
    scenario = scenario_v3()
    scenario["time_policy"]["max_skipped_steps"] = 1

    with pytest.raises(ContractValidationError) as caught:
        validate_scenario(scenario)

    assert caught.value.json_path == "$.time_policy"


def test_v4_uses_delivery_latency_for_time_authority_measurements() -> None:
    validate_scenario(scenario_v4())


def test_v4_rejects_legacy_time_authority_offset_percentiles() -> None:
    scenario = scenario_v4()
    scenario["time_policy"]["max_clock_offset_p50_ms"] = 1

    with pytest.raises(ContractValidationError) as caught:
        validate_scenario(scenario)

    assert caught.value.json_path == "$.time_policy"


def test_v4_rejects_unsorted_delivery_latency_thresholds() -> None:
    scenario = scenario_v4()
    scenario["time_policy"]["max_time_authority_delivery_latency_p50_ms"] = 3

    with pytest.raises(SemanticValidationError, match="p50 <= p95 <= max"):
        validate_scenario(scenario)
