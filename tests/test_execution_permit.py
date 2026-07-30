from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from robotics_runtime_contracts import ContractValidationError, validate_document
from tests.support import load_fixture

FIXTURE = Path(__file__).parent / "fixtures" / "physical" / "valid" / "hil-permit.yaml"


def test_execution_permit_rejects_actuator_scope() -> None:
    permit = deepcopy(load_fixture(FIXTURE))
    permit["hardware_scope"].append("actuator")
    with pytest.raises(ContractValidationError):
        validate_document(permit)
