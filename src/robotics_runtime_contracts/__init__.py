from __future__ import annotations

import json
from collections.abc import Mapping
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

SCHEMA_NAME = "acceptance-scenario.v1.schema.json"


class ScenarioValidationError(ValueError):
    """Raised when an acceptance scenario does not satisfy the public contract."""

    def __init__(self, error: ValidationError) -> None:
        self.json_path = error.json_path
        self.validation_message = error.message
        super().__init__(f"{self.json_path}: {self.validation_message}")


def schema_dir() -> Path:
    return Path(str(files("robotics_runtime_contracts").joinpath("schemas")))


def schema_path() -> Path:
    path = schema_dir() / SCHEMA_NAME
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


@lru_cache(maxsize=1)
def load_schema() -> dict[str, Any]:
    return json.loads(
        files("robotics_runtime_contracts")
        .joinpath("schemas", SCHEMA_NAME)
        .read_text(encoding="utf-8")
    )


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = load_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_scenario(scenario: Mapping[str, Any]) -> None:
    """Validate a scenario and report the first failure with its JSON path."""

    errors = sorted(
        _validator().iter_errors(scenario),
        key=lambda error: tuple(str(part) for part in error.path),
    )
    if errors:
        raise ScenarioValidationError(errors[0]) from errors[0]


__all__ = [
    "SCHEMA_NAME",
    "ScenarioValidationError",
    "load_schema",
    "schema_dir",
    "schema_path",
    "validate_scenario",
]
