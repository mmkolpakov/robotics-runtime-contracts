from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

from robotics_runtime_contracts import (
    SCHEMA_NAME,
    ScenarioValidationError,
    load_schema,
    schema_path,
    validate_scenario,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def test_schema_satisfies_draft_2020_12_metaschema() -> None:
    schema = load_schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:robotics-runtime-contracts:acceptance-scenario:v1"


@pytest.mark.parametrize("fixture", sorted((FIXTURES / "valid").iterdir()))
def test_valid_scenarios(fixture: Path) -> None:
    validate_scenario(load_fixture(fixture))


@pytest.mark.parametrize(
    ("fixture_name", "expected_path"),
    [
        ("invalid-extension-key.yaml", "$.extensions"),
        ("negative-timeout.json", "$.timeouts.execution_sec"),
        ("unmatched-topic.json", "$.expected_ros_graph.topics[0]"),
        ("unknown-root-property.json", "$"),
        ("unknown-target.json", "$.target_environment"),
    ],
)
def test_invalid_scenarios_report_exact_path(
    fixture_name: str,
    expected_path: str,
) -> None:
    with pytest.raises(ScenarioValidationError) as caught:
        validate_scenario(load_fixture(FIXTURES / "invalid" / fixture_name))

    assert caught.value.json_path == expected_path
    assert str(caught.value).startswith(f"{expected_path}:")


def test_package_exposes_single_schema() -> None:
    assert schema_path().name == SCHEMA_NAME
    assert schema_path().is_file()
    assert sorted(path.name for path in schema_path().parent.glob("*.schema.json")) == [SCHEMA_NAME]
