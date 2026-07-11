from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

from robotics_runtime_contracts import (
    SCHEMA_FILES,
    SCHEMA_NAME,
    ScenarioValidationError,
    UnknownSchemaError,
    load_schema,
    resolve_schema_name,
    schema_names,
    schema_path,
    validate_document,
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


def test_acceptance_scenario_v1_is_byte_for_byte_stable() -> None:
    digest = sha256(schema_path().read_bytes()).hexdigest()
    assert digest == "e134f3f8b5a24a80177a5bc79e81ee4330e68b8d32416cb043e1f94db6efcb66"


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


def test_package_exposes_registered_schemas() -> None:
    assert schema_path().name == SCHEMA_NAME
    assert schema_path().is_file()
    installed = sorted(path.name for path in schema_path().parent.glob("*.schema.json"))
    assert installed == sorted(SCHEMA_FILES.values())


def test_versioned_registry_resolves_version_file_and_id() -> None:
    canonical_id = "urn:robotics-runtime-contracts:acceptance-scenario:v1"
    assert schema_names() == tuple(SCHEMA_FILES)
    assert SCHEMA_FILES["acceptance-scenario.v1"] == SCHEMA_NAME
    assert resolve_schema_name("acceptance-scenario.v1") == "acceptance-scenario.v1"
    assert resolve_schema_name(SCHEMA_NAME) == "acceptance-scenario.v1"
    assert resolve_schema_name(canonical_id) == "acceptance-scenario.v1"
    assert schema_path(canonical_id) == schema_path()
    assert load_schema(SCHEMA_NAME) == load_schema()


def test_validate_document_uses_declared_schema_version() -> None:
    scenario = load_fixture(FIXTURES / "valid" / "simulation.json")
    validate_document(scenario)


def test_unknown_schema_is_rejected_before_validation() -> None:
    with pytest.raises(UnknownSchemaError, match="Unknown schema"):
        resolve_schema_name("acceptance-scenario.v99")
