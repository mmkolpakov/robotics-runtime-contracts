from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from robotics_runtime_contracts import ContractValidationError, load_schema, validate_document

FIXTURE = Path(__file__).parent / "fixtures" / "physical" / "valid" / "hil-permit.yaml"


def load_fixture(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_execution_permit_satisfies_metaschema() -> None:
    Draft202012Validator.check_schema(load_schema("execution-permit.v1"))


def test_valid_execution_permit() -> None:
    validate_document(load_fixture(FIXTURE))


def test_execution_permit_rejects_actuator_scope() -> None:
    permit = deepcopy(load_fixture(FIXTURE))
    permit["hardware_scope"].append("actuator")
    with pytest.raises(ContractValidationError):
        validate_document(permit)
