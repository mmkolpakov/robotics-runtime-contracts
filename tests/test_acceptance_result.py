from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from robotics_runtime_contracts import ContractValidationError, load_schema, validate_document

FIXTURES = Path(__file__).parent / "fixtures" / "result"


def load_fixture(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_acceptance_result_satisfies_metaschema() -> None:
    Draft202012Validator.check_schema(load_schema("acceptance-result.v1"))


@pytest.mark.parametrize("fixture", sorted((FIXTURES / "valid").iterdir()))
def test_valid_acceptance_results(fixture: Path) -> None:
    validate_document(load_fixture(fixture))


@pytest.mark.parametrize("fixture", sorted((FIXTURES / "invalid").iterdir()))
def test_invalid_acceptance_results(fixture: Path) -> None:
    with pytest.raises(ContractValidationError):
        validate_document(load_fixture(fixture))
