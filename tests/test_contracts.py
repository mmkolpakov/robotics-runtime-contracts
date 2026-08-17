from __future__ import annotations

from itertools import permutations
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator

from robotics_runtime_contracts import (
    ContractValidationError,
    OutcomeStatus,
    UnknownSchemaError,
    contract_roles,
    contract_set,
    load_schema,
    resolve_schema_name,
    role_schemas,
    schema_digest,
    schema_dir,
    schema_for_role,
    schema_names,
    schema_path,
    schema_registry,
    schema_resource_names,
    validate_document,
    worst_status,
)
from tests.support import load_fixture


def test_package_declares_pep561_typing() -> None:
    marker = schema_dir().parent / "py.typed"
    assert marker.is_file()


FIXTURES = Path(__file__).parent / "fixtures" / "scenario"


@pytest.mark.parametrize("schema_name", schema_resource_names())
def test_schemas_satisfy_draft_2020_12_metaschema(schema_name: str) -> None:
    schema = load_schema(schema_name)
    Draft202012Validator.check_schema(schema)
    assert schema["$id"].startswith("urn:robotics-runtime-contracts:v1:")


def test_catalog_defines_one_public_v1_schema_per_role() -> None:
    assert contract_set() == "v1"
    assert contract_roles() == tuple(role_schemas())
    assert set(role_schemas().values()) == set(schema_names())
    assert all(schema_name.endswith(".v1") for schema_name in schema_names())
    for role, schema_name in role_schemas().items():
        assert schema_for_role(role) == schema_name


@pytest.mark.parametrize("schema_name", schema_resource_names())
def test_schema_digest_describes_packaged_bytes(schema_name: str) -> None:
    assert len(schema_digest(schema_name)) == 64


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
    scenario_path = schema_path("acceptance-scenario.v1")
    assert scenario_path.name == "acceptance-scenario.v1.schema.json"
    assert scenario_path.is_file()
    installed = sorted(path.name for path in scenario_path.parent.glob("*.schema.json"))
    assert installed == sorted(f"{name}.schema.json" for name in schema_resource_names())


def test_catalog_resolves_name_file_and_id() -> None:
    canonical_name = "acceptance-scenario.v1"
    canonical_file = f"{canonical_name}.schema.json"
    canonical_id = "urn:robotics-runtime-contracts:v1:acceptance-scenario"
    assert resolve_schema_name(canonical_name) == canonical_name
    assert resolve_schema_name(canonical_file) == canonical_name
    assert resolve_schema_name(canonical_id) == canonical_name
    assert schema_path(canonical_id) == schema_path(canonical_name)
    assert load_schema(canonical_file) == load_schema(canonical_name)


def test_load_schema_returns_an_isolated_copy() -> None:
    schema = load_schema("acceptance-scenario.v1")
    schema["properties"]["schema_version"]["const"] = "poisoned"

    fresh = load_schema("acceptance-scenario.v1")
    assert fresh["properties"]["schema_version"]["const"] == "acceptance-scenario.v1"


def test_current_schema_is_embeddable_with_the_offline_registry() -> None:
    scenario = load_fixture(FIXTURES / "valid" / "simulation-realtime.yaml")
    scenario["schema_version"] = "acceptance-scenario.v1"
    scenario["metric_definitions"] = []
    validator = Draft202012Validator(
        load_schema("acceptance-scenario.v1"),
        registry=schema_registry(),
    )

    assert validator.is_valid(scenario)


def test_public_schema_registry_does_not_share_mutable_resources() -> None:
    schema_id = "urn:robotics-runtime-contracts:v1:acceptance-scenario"
    core_id = "urn:robotics-runtime-contracts:v1:internal:acceptance-scenario-core"
    exposed_registry = schema_registry()
    exposed_schema = cast(dict[str, Any], exposed_registry.contents(schema_id))
    exposed_core = cast(
        dict[str, Any],
        exposed_registry.contents(core_id),
    )
    exposed_schema["title"] = "poisoned"
    exposed_core["allOf"].clear()

    assert load_schema("acceptance-scenario.v1")["title"] != "poisoned"
    fresh_registry = schema_registry()
    fresh_schema = cast(dict[str, Any], fresh_registry.contents(schema_id))
    assert fresh_schema["title"] != "poisoned"
    fresh_core = cast(
        dict[str, Any],
        fresh_registry.contents(core_id),
    )
    assert fresh_core["allOf"]

    scenario = load_fixture(FIXTURES / "valid" / "simulation-realtime.yaml")
    scenario["schema_version"] = "acceptance-scenario.v1"
    scenario["metric_definitions"] = []
    scenario["execution"]["plant_backend"] = "recorded_data"
    validator = Draft202012Validator(
        load_schema("acceptance-scenario.v1"),
        registry=fresh_registry,
    )
    assert not validator.is_valid(scenario)


def test_unknown_schema_is_rejected_before_validation() -> None:
    with pytest.raises(UnknownSchemaError, match="Unknown schema"):
        resolve_schema_name("acceptance-scenario.invalid")


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ((OutcomeStatus.PASSED,), "passed"),
        ((OutcomeStatus.PASSED, OutcomeStatus.SKIPPED), "skipped"),
        ((OutcomeStatus.PASSED, OutcomeStatus.INCOMPLETE), "incomplete"),
        ((OutcomeStatus.PASSED, OutcomeStatus.FAILED), "failed"),
        ((OutcomeStatus.PASSED, OutcomeStatus.ERROR), "error"),
    ],
)
def test_worst_status_is_order_independent(
    statuses: tuple[OutcomeStatus, ...],
    expected: str,
) -> None:
    assert {worst_status(order) for order in permutations(statuses)} == {expected}


def test_worst_status_rejects_missing_or_unknown_statuses() -> None:
    with pytest.raises(ValueError, match="at least one status"):
        worst_status([])
    with pytest.raises(ValueError, match="not-a-status"):
        worst_status(["not-a-status"])
