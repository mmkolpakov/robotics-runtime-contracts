from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

from robotics_runtime_contracts import (
    PUBLISHED_SCHEMA_SHA256,
    SCHEMA_FILES,
    SCHEMA_NAME,
    ScenarioValidationError,
    UnknownSchemaError,
    load_schema,
    resolve_schema_name,
    schema_dir,
    schema_names,
    schema_path,
    validate_document,
    validate_scenario,
)


def test_package_declares_pep561_typing() -> None:
    marker = schema_dir().parent / "py.typed"
    assert marker.is_file()


FIXTURES = Path(__file__).parent / "fixtures" / "scenario"


def load_fixture(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def test_schema_satisfies_draft_2020_12_metaschema() -> None:
    schema = load_schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:robotics-runtime-contracts:acceptance-scenario:v1"


def test_all_published_schemas_are_byte_for_byte_stable() -> None:
    assert set(PUBLISHED_SCHEMA_SHA256) == set(SCHEMA_FILES)
    for schema_name, expected_digest in PUBLISHED_SCHEMA_SHA256.items():
        assert sha256(schema_path(schema_name).read_bytes()).hexdigest() == expected_digest


@pytest.mark.parametrize("fixture", sorted((FIXTURES / "valid").iterdir()))
def test_valid_scenarios(fixture: Path) -> None:
    validate_scenario(load_fixture(fixture))


@pytest.mark.parametrize(
    ("mutation", "expected_path"),
    [
        (lambda value: value["timeouts"].update(execution_sec=-1), "$.timeouts.execution_sec"),
        (lambda value: value.update(unknown=True), "$"),
        (
            lambda value: value["execution"].update(target_environment="unknown"),
            "$.execution.target_environment",
        ),
    ],
)
def test_invalid_scenarios_report_exact_path(
    mutation: Any,
    expected_path: str,
) -> None:
    scenario = load_fixture(FIXTURES / "valid" / "simulation-realtime.yaml")
    mutation(scenario)
    with pytest.raises(ScenarioValidationError) as caught:
        validate_scenario(scenario)

    assert caught.value.json_path == expected_path
    assert str(caught.value).startswith(f"{expected_path}:")


def test_package_exposes_registered_schemas() -> None:
    assert schema_path().name == SCHEMA_NAME
    assert schema_path().is_file()
    installed = sorted(path.name for path in schema_path().parent.glob("*.schema.json"))
    assert installed == sorted(SCHEMA_FILES.values())


def test_catalog_resolves_name_file_and_id() -> None:
    canonical_id = "urn:robotics-runtime-contracts:acceptance-scenario:v1"
    assert schema_names() == tuple(SCHEMA_FILES)
    assert SCHEMA_FILES["acceptance-scenario.v1"] == SCHEMA_NAME
    assert resolve_schema_name("acceptance-scenario.v1") == "acceptance-scenario.v1"
    assert resolve_schema_name(SCHEMA_NAME) == "acceptance-scenario.v1"
    assert resolve_schema_name(canonical_id) == "acceptance-scenario.v1"
    assert schema_path(canonical_id) == schema_path()
    assert load_schema(SCHEMA_NAME) == load_schema()


def test_load_schema_returns_an_isolated_copy() -> None:
    schema = load_schema("acceptance-scenario.v1")
    schema["properties"]["schema_version"]["const"] = "poisoned"

    fresh = load_schema("acceptance-scenario.v1")
    assert fresh["properties"]["schema_version"]["const"] == "acceptance-scenario.v1"


def test_validate_document_uses_declared_schema_version() -> None:
    scenario = load_fixture(FIXTURES / "valid" / "simulation-realtime.yaml")
    validate_document(scenario)


def test_unknown_schema_is_rejected_before_validation() -> None:
    with pytest.raises(UnknownSchemaError, match="Unknown schema"):
        resolve_schema_name("acceptance-scenario.v99")
