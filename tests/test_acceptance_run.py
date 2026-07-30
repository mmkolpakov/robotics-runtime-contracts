from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from robotics_runtime_contracts import SemanticValidationError, validate_document
from tests.support import load_fixture

FIXTURE = Path(__file__).parent / "fixtures" / "run" / "valid" / "simulation.yaml"


def test_acceptance_run_rejects_duplicate_domain_ids() -> None:
    document = load_fixture(FIXTURE)
    duplicate = deepcopy(document["domains"][0])
    duplicate["role"] = "secondary-observer"
    document["domains"].append(duplicate)

    with pytest.raises(SemanticValidationError) as caught:
        validate_document(document)

    assert caught.value.json_path == "$.domains"
