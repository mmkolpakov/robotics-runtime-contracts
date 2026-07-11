from __future__ import annotations

import json
from collections.abc import Mapping
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

SCHEMA_NAME = "acceptance-scenario.v1.schema.json"
SCHEMA_FILES = {
    "acceptance-scenario.v1": SCHEMA_NAME,
    "acceptance-scenario.v2": "acceptance-scenario.v2.schema.json",
    "model-artifact-manifest.v1": "model-artifact-manifest.v1.schema.json",
}
SCHEMA_IDS = {
    "urn:robotics-runtime-contracts:acceptance-scenario:v1": "acceptance-scenario.v1",
    "urn:robotics-runtime-contracts:acceptance-scenario:v2": "acceptance-scenario.v2",
    "urn:robotics-runtime-contracts:model-artifact-manifest:v1": "model-artifact-manifest.v1",
}


class ContractValidationError(ValueError):
    """Raised when a document does not satisfy a public contract."""

    def __init__(self, schema_name: str, error: ValidationError) -> None:
        self.schema_name = schema_name
        self.json_path = error.json_path
        self.validation_message = error.message
        super().__init__(f"{self.json_path}: {self.validation_message}")


class ScenarioValidationError(ContractValidationError):
    """Backward-compatible scenario validation error."""


class UnknownSchemaError(ValueError):
    """Raised when a requested schema version or identifier is not published."""


def schema_names() -> tuple[str, ...]:
    """Return published schema versions in stable order."""

    return tuple(SCHEMA_FILES)


def resolve_schema_name(schema: str) -> str:
    """Resolve a schema version, file name, or canonical identifier."""

    if schema in SCHEMA_FILES:
        return schema
    if schema in SCHEMA_IDS:
        return SCHEMA_IDS[schema]
    for schema_name, file_name in SCHEMA_FILES.items():
        if schema == file_name:
            return schema_name
    raise UnknownSchemaError(f"Unknown schema: {schema}")


def schema_dir() -> Path:
    return Path(str(files("robotics_runtime_contracts").joinpath("schemas")))


def schema_path(schema: str = "acceptance-scenario.v1") -> Path:
    schema_name = resolve_schema_name(schema)
    path = schema_dir() / SCHEMA_FILES[schema_name]
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


@cache
def load_schema(schema: str = "acceptance-scenario.v1") -> dict[str, Any]:
    schema_name = resolve_schema_name(schema)
    return json.loads(schema_path(schema_name).read_text(encoding="utf-8"))


@cache
def _validator(schema: str) -> Draft202012Validator:
    schema_name = resolve_schema_name(schema)
    contract = load_schema(schema_name)
    Draft202012Validator.check_schema(contract)
    return Draft202012Validator(contract)


def validate_document(
    document: Mapping[str, Any],
    schema: str | None = None,
    *,
    error_type: type[ContractValidationError] = ContractValidationError,
) -> None:
    """Validate a document against an explicit or declared schema version."""

    declared_schema = document.get("schema_version")
    selected_schema = schema if schema is not None else declared_schema
    if not isinstance(selected_schema, str):
        raise UnknownSchemaError("Document must declare schema_version")
    schema_name = resolve_schema_name(selected_schema)
    errors = sorted(
        _validator(schema_name).iter_errors(document),
        key=lambda error: tuple(str(part) for part in error.path),
    )
    if errors:
        raise error_type(schema_name, errors[0]) from errors[0]


def validate_scenario(scenario: Mapping[str, Any]) -> None:
    """Validate an acceptance scenario using the backward-compatible API."""

    validate_document(
        scenario,
        schema="acceptance-scenario.v1",
        error_type=ScenarioValidationError,
    )


__all__ = [
    "SCHEMA_FILES",
    "SCHEMA_IDS",
    "SCHEMA_NAME",
    "ContractValidationError",
    "ScenarioValidationError",
    "UnknownSchemaError",
    "load_schema",
    "resolve_schema_name",
    "schema_dir",
    "schema_names",
    "schema_path",
    "validate_document",
    "validate_scenario",
]
