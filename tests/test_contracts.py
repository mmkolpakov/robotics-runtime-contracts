from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator

from robotics_runtime_contracts import (
    PUBLISHED_SCHEMA_SHA256,
    ContractValidationError,
    UnknownSchemaError,
    load_schema,
    resolve_schema_name,
    schema_dir,
    schema_names,
    schema_path,
    schema_registry,
    validate_document,
)
from tests.support import load_fixture


def test_package_declares_pep561_typing() -> None:
    marker = schema_dir().parent / "py.typed"
    assert marker.is_file()


FIXTURES = Path(__file__).parent / "fixtures" / "scenario"


@pytest.mark.parametrize("schema_name", schema_names())
def test_schemas_satisfy_draft_2020_12_metaschema(schema_name: str) -> None:
    schema = load_schema(schema_name)
    Draft202012Validator.check_schema(schema)
    family, version = schema_name.rsplit(".", 1)
    assert schema["$id"] == f"urn:robotics-runtime-contracts:{family}:{version}"


def test_all_published_schemas_are_byte_for_byte_stable() -> None:
    for schema_name, expected_digest in PUBLISHED_SCHEMA_SHA256.items():
        assert sha256(schema_path(schema_name).read_bytes()).hexdigest() == expected_digest


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
    with pytest.raises(ContractValidationError) as caught:
        validate_document(scenario)

    assert caught.value.json_path == expected_path
    assert str(caught.value).startswith(f"{expected_path}:")


def test_package_exposes_registered_schemas() -> None:
    scenario_path = schema_path("acceptance-scenario.v4")
    assert scenario_path.name == "acceptance-scenario.v4.schema.json"
    assert scenario_path.is_file()
    installed = sorted(path.name for path in scenario_path.parent.glob("*.schema.json"))
    assert installed == sorted(f"{name}.schema.json" for name in schema_names())


def test_catalog_resolves_name_file_and_id() -> None:
    canonical_name = "acceptance-scenario.v4"
    canonical_file = f"{canonical_name}.schema.json"
    canonical_id = "urn:robotics-runtime-contracts:acceptance-scenario:v4"
    assert resolve_schema_name(canonical_name) == canonical_name
    assert resolve_schema_name(canonical_file) == canonical_name
    assert resolve_schema_name(canonical_id) == canonical_name
    assert schema_path(canonical_id) == schema_path(canonical_name)
    assert load_schema(canonical_file) == load_schema(canonical_name)


def test_load_schema_returns_an_isolated_copy() -> None:
    schema = load_schema("acceptance-scenario.v4")
    schema["properties"]["schema_version"]["const"] = "poisoned"

    fresh = load_schema("acceptance-scenario.v4")
    assert fresh["properties"]["schema_version"]["const"] == "acceptance-scenario.v4"


def test_current_schema_is_embeddable_with_the_offline_registry() -> None:
    scenario = load_fixture(FIXTURES / "valid" / "simulation-realtime.yaml")
    scenario["schema_version"] = "acceptance-scenario.v5"
    scenario["metric_definitions"] = []
    validator = Draft202012Validator(
        load_schema("acceptance-scenario.v5"),
        registry=schema_registry(),
    )

    assert validator.is_valid(scenario)


def test_public_schema_registry_does_not_share_mutable_resources() -> None:
    schema_id = "urn:robotics-runtime-contracts:acceptance-scenario:v5"
    predecessor_id = "urn:robotics-runtime-contracts:acceptance-scenario:v4"
    exposed_registry = schema_registry()
    exposed_schema = cast(dict[str, Any], exposed_registry.contents(schema_id))
    exposed_predecessor = cast(
        dict[str, Any],
        exposed_registry.contents(predecessor_id),
    )
    exposed_schema["title"] = "poisoned"
    exposed_predecessor["allOf"].clear()

    assert load_schema("acceptance-scenario.v5")["title"] != "poisoned"
    fresh_registry = schema_registry()
    fresh_schema = cast(dict[str, Any], fresh_registry.contents(schema_id))
    assert fresh_schema["title"] != "poisoned"
    fresh_predecessor = cast(
        dict[str, Any],
        fresh_registry.contents(predecessor_id),
    )
    assert fresh_predecessor["allOf"]

    scenario = load_fixture(FIXTURES / "valid" / "simulation-realtime.yaml")
    scenario["schema_version"] = "acceptance-scenario.v5"
    scenario["metric_definitions"] = []
    scenario["execution"]["plant_backend"] = "recorded_data"
    validator = Draft202012Validator(
        load_schema("acceptance-scenario.v5"),
        registry=fresh_registry,
    )
    assert not validator.is_valid(scenario)


def test_unknown_schema_is_rejected_before_validation() -> None:
    with pytest.raises(UnknownSchemaError, match="Unknown schema"):
        resolve_schema_name("acceptance-scenario.v99")
