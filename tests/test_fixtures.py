from pathlib import Path

import pytest

from robotics_runtime_contracts import (
    ContractValidationError,
    SemanticValidationError,
    validate_document,
)
from tests.support import load_fixture

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_files(kind: str) -> list[Path]:
    return sorted(
        path for path in FIXTURES.rglob("*") if path.is_file() and path.parent.name == kind
    )


@pytest.mark.parametrize("fixture", fixture_files("valid"), ids=str)
def test_valid_contract_fixtures(fixture: Path) -> None:
    validate_document(load_fixture(fixture))


@pytest.mark.parametrize("fixture", fixture_files("invalid"), ids=str)
def test_invalid_contract_fixtures(fixture: Path) -> None:
    with pytest.raises((ContractValidationError, SemanticValidationError)):
        validate_document(load_fixture(fixture))
