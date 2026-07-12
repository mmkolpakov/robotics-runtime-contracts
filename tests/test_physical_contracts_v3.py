from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

from robotics_runtime_contracts import (
    ContractValidationError,
    SemanticValidationError,
    load_schema,
    validate_document,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures"
FIXTURES = FIXTURE_ROOT / "v3" / "valid"
SCHEMAS = (
    "acceptance-scenario.v3",
    "runtime-manifest.v3",
    "execution-permit.v2",
    "execution-verification.v1",
    "acceptance-result.v3",
)


def load_fixture(name: str) -> dict[str, Any]:
    return yaml.safe_load((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("schema_name", SCHEMAS)
def test_physical_schemas_satisfy_draft_2020_12(schema_name: str) -> None:
    Draft202012Validator.check_schema(load_schema(schema_name))


@pytest.mark.parametrize(
    "fixture_name",
    (
        "hil-scenario.yaml",
        "hil-runtime.yaml",
        "hil-permit.yaml",
        "hil-verification.yaml",
        "hil-result.yaml",
    ),
)
def test_valid_physical_documents(fixture_name: str) -> None:
    validate_document(load_fixture(fixture_name))


def test_v3_accepts_simulation_without_physical_authorization() -> None:
    scenario = yaml.safe_load(
        (FIXTURE_ROOT / "v2" / "valid" / "simulation-realtime.yaml").read_text(encoding="utf-8")
    )
    scenario["schema_version"] = "acceptance-scenario.v3"
    scenario["authorization"] = {"mode": "none"}
    scenario["forbidden_ros_graph"] = {"topics": [], "services": [], "actions": []}

    runtime = yaml.safe_load(
        (FIXTURE_ROOT / "runtime" / "valid" / "no-inference-simulation.yaml").read_text(
            encoding="utf-8"
        )
    )
    runtime["schema_version"] = "runtime-manifest.v3"
    runtime["authorization"] = {"mode": "none"}

    result = yaml.safe_load(
        (FIXTURE_ROOT / "result" / "valid" / "passed-no-inference.yaml").read_text(encoding="utf-8")
    )
    result["schema_version"] = "acceptance-result.v3"
    result["authorization"] = {"mode": "none"}
    result["forbidden_graph_observation"] = {
        "passed": True,
        "checked_topics": [],
        "checked_services": [],
        "checked_actions": [],
        "violations": [],
    }

    validate_document(scenario)
    validate_document(runtime)
    validate_document(result)


def test_v3_accepts_real_target_only_as_observation() -> None:
    scenario = load_fixture("hil-scenario.yaml")
    scenario["execution"]["target_environment"] = "real_robot"
    scenario["execution"]["physical_effect"] = "observation"

    permit = load_fixture("hil-permit.yaml")
    permit["target"]["environment"] = "real_robot"
    permit["allowed_physical_effect"] = "observation"

    runtime = load_fixture("hil-runtime.yaml")
    runtime["execution"]["target_environment"] = "real_robot"

    result = load_fixture("hil-result.yaml")
    result["execution"]["target_environment"] = "real_robot"
    result["authorization"]["target"]["environment"] = "real_robot"

    validate_document(scenario)
    validate_document(permit)
    validate_document(runtime)
    validate_document(result)


def test_physical_scenario_requires_a_forbidden_interface() -> None:
    scenario = load_fixture("hil-scenario.yaml")
    scenario["forbidden_ros_graph"] = {"topics": [], "services": [], "actions": []}

    with pytest.raises(SemanticValidationError, match="at least one forbidden"):
        validate_document(scenario)


def test_runtime_rejects_duplicate_target_identity() -> None:
    runtime = load_fixture("hil-runtime.yaml")
    duplicate = deepcopy(runtime["physical_targets"][0])
    duplicate["target_id"] = "controller-beta"
    runtime["physical_targets"].append(duplicate)

    with pytest.raises(SemanticValidationError, match="identity_sha256 values must be unique"):
        validate_document(runtime)


def test_permit_rejects_same_operator_and_approver() -> None:
    permit = load_fixture("hil-permit.yaml")
    permit["approver_id"] = permit["operator_id"]

    with pytest.raises(SemanticValidationError, match="must differ from operator_id"):
        validate_document(permit)


def test_permit_v2_is_bounded_to_thirty_minutes() -> None:
    permit = load_fixture("hil-permit.yaml")
    permit["expires_at"] = "2026-07-12T10:30:01Z"

    with pytest.raises(SemanticValidationError, match="no more than 30 minutes"):
        validate_document(permit)


@pytest.mark.parametrize(
    ("fixture_name", "mutation"),
    (
        (
            "hil-scenario.yaml",
            lambda document: document["execution"].update({"physical_effect": "actuation"}),
        ),
        (
            "hil-permit.yaml",
            lambda document: document["hardware_scope"].append("actuator"),
        ),
        (
            "hil-runtime.yaml",
            lambda document: document["physical_targets"][0].update({"scope": "actuator"}),
        ),
    ),
)
def test_v3_foundation_rejects_actuation(
    fixture_name: str,
    mutation: Any,
) -> None:
    document = load_fixture(fixture_name)
    mutation(document)

    with pytest.raises(ContractValidationError):
        validate_document(document)


def test_verification_requires_one_signer_for_each_role() -> None:
    verification = load_fixture("hil-verification.yaml")
    verification["signers"][1]["role"] = "operator"

    with pytest.raises(SemanticValidationError, match="one operator and one approver"):
        validate_document(verification)


def test_verification_rejects_reused_signer_identity() -> None:
    verification = load_fixture("hil-verification.yaml")
    verification["signers"][1]["identity"] = verification["signers"][0]["identity"]

    with pytest.raises(SemanticValidationError, match="identity values must be unique"):
        validate_document(verification)


def test_result_target_environment_must_match_execution() -> None:
    result = load_fixture("hil-result.yaml")
    result["authorization"]["target"]["environment"] = "real_robot"

    with pytest.raises(SemanticValidationError, match="must match execution"):
        validate_document(result)


def test_passed_physical_result_requires_timing_within_policy() -> None:
    result = load_fixture("hil-result.yaml")
    result["hardware_clock_observation"]["within_policy"] = False

    with pytest.raises(SemanticValidationError, match="timing within policy"):
        validate_document(result)


def test_hardware_clock_source_must_match_protocol() -> None:
    result = load_fixture("hil-result.yaml")
    result["hardware_clock_observation"]["source"] = "pmc"

    with pytest.raises(SemanticValidationError, match="must match sync_protocol"):
        validate_document(result)


def test_passed_result_rejects_forbidden_interface_violation() -> None:
    result = load_fixture("hil-result.yaml")
    result["forbidden_graph_observation"] = {
        "passed": False,
        "checked_topics": ["/cmd_vel"],
        "checked_services": [],
        "checked_actions": [],
        "violations": [{"kind": "topic", "name": "/cmd_vel"}],
    }

    with pytest.raises(ContractValidationError, match="True was expected"):
        validate_document(result)
