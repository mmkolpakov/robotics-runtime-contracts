from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from robotics_runtime_contracts import (
    ContractValidationError,
    SemanticValidationError,
    load_schema,
    validate_document,
)

FIXTURES = Path(__file__).parent / "fixtures" / "evidence-index"


def load_fixture(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_evidence_index_satisfies_metaschema() -> None:
    Draft202012Validator.check_schema(load_schema("evidence-index.v1"))


@pytest.mark.parametrize("fixture", sorted((FIXTURES / "valid").iterdir()))
def test_valid_evidence_indexes(fixture: Path) -> None:
    validate_document(load_fixture(fixture))


@pytest.mark.parametrize("fixture", sorted((FIXTURES / "invalid").iterdir()))
def test_invalid_evidence_indexes(fixture: Path) -> None:
    with pytest.raises(ContractValidationError):
        validate_document(load_fixture(fixture))


@pytest.mark.parametrize("field", ["segment_index", "uri"])
def test_evidence_segments_are_unique(field: str) -> None:
    document = load_fixture(FIXTURES / "valid" / "mixed.yaml")
    segments = document["segments"]
    assert isinstance(segments, list)
    first, second = segments
    assert isinstance(first, dict)
    assert isinstance(second, dict)
    second[field] = first[field]
    if field == "uri":
        second.pop("version_id", None)

    with pytest.raises(SemanticValidationError):
        validate_document(document)
