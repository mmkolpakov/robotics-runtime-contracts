from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from robotics_runtime_contracts import ContractValidationError, load_schema, validate_document

FIXTURES = Path(__file__).parent / "fixtures" / "v2"


def load_fixture(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_acceptance_scenario_v2_satisfies_metaschema() -> None:
    schema = load_schema("acceptance-scenario.v2")
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:robotics-runtime-contracts:acceptance-scenario:v2"


@pytest.mark.parametrize("fixture", sorted((FIXTURES / "valid").iterdir()))
def test_valid_v2_scenarios(fixture: Path) -> None:
    validate_document(load_fixture(fixture))


@pytest.mark.parametrize("fixture", sorted((FIXTURES / "invalid").iterdir()))
def test_invalid_v2_combinations(fixture: Path) -> None:
    with pytest.raises(ContractValidationError):
        validate_document(load_fixture(fixture))
