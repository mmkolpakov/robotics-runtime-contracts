from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

from robotics_runtime_contracts import SemanticValidationError, validate_document

FIXTURE = Path(__file__).parent / "fixtures" / "run" / "valid" / "simulation.yaml"


def load_fixture() -> dict[str, Any]:
    return yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))


def test_acceptance_run_is_valid() -> None:
    validate_document(load_fixture())


def test_acceptance_run_rejects_duplicate_domain_ids() -> None:
    document = load_fixture()
    duplicate = deepcopy(document["domains"][0])
    duplicate["role"] = "secondary-observer"
    document["domains"].append(duplicate)

    with pytest.raises(SemanticValidationError) as caught:
        validate_document(document)

    assert caught.value.json_path == "$.domains"
