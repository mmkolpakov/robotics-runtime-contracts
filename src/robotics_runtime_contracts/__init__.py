from __future__ import annotations

import json
from collections.abc import Mapping
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource

from robotics_runtime_contracts.extensions import ExtensionValidationError, validate_extensions
from robotics_runtime_contracts.semantics import SemanticValidationError, validate_semantics

SCHEMA_NAME = "acceptance-scenario.v1.schema.json"
SCHEMA_FILES = {
    "acceptance-scenario.v1": SCHEMA_NAME,
    "acceptance-scenario.v2": "acceptance-scenario.v2.schema.json",
    "model-artifact-manifest.v1": "model-artifact-manifest.v1.schema.json",
    "dataset-manifest.v1": "dataset-manifest.v1.schema.json",
    "runtime-manifest.v1": "runtime-manifest.v1.schema.json",
    "runtime-manifest.v2": "runtime-manifest.v2.schema.json",
    "execution-permit.v1": "execution-permit.v1.schema.json",
    "acceptance-result.v1": "acceptance-result.v1.schema.json",
    "acceptance-result.v2": "acceptance-result.v2.schema.json",
}
SCHEMA_IDS = {
    "urn:robotics-runtime-contracts:acceptance-scenario:v1": "acceptance-scenario.v1",
    "urn:robotics-runtime-contracts:acceptance-scenario:v2": "acceptance-scenario.v2",
    "urn:robotics-runtime-contracts:model-artifact-manifest:v1": "model-artifact-manifest.v1",
    "urn:robotics-runtime-contracts:dataset-manifest:v1": "dataset-manifest.v1",
    "urn:robotics-runtime-contracts:runtime-manifest:v1": "runtime-manifest.v1",
    "urn:robotics-runtime-contracts:runtime-manifest:v2": "runtime-manifest.v2",
    "urn:robotics-runtime-contracts:execution-permit:v1": "execution-permit.v1",
    "urn:robotics-runtime-contracts:acceptance-result:v1": "acceptance-result.v1",
    "urn:robotics-runtime-contracts:acceptance-result:v2": "acceptance-result.v2",
}
PUBLISHED_SCHEMA_SHA256 = {
    "acceptance-result.v1": "179a4a1d9f2b1dd339e5dfdc9c8a2bde1801d1adc6c3a65b5a67dec9468d8256",
    "acceptance-result.v2": "af3c13a25a88c60d7ac474c675b61f2974318379e4b5e26c0a6ae9ebc059a041",
    "acceptance-scenario.v1": "e134f3f8b5a24a80177a5bc79e81ee4330e68b8d32416cb043e1f94db6efcb66",
    "acceptance-scenario.v2": "de15aa20118aee430b1501dbbf543e9144c4f0cbe4ff74a17b6d82c263c79dfb",
    "dataset-manifest.v1": "b768eb96ee26e4c646eac2ba8743ba4a25bc2b668f7fe1453a474de7c10c8f08",
    "execution-permit.v1": "0b29e024ab8581b04b866ff6bfe4d29d527eb553e22ed43228fb0920887e8d19",
    "model-artifact-manifest.v1": (
        "eed0440e05b1846db93958db9bc7fba4bb45b451a907200b5f98f843a3577063"
    ),
    "runtime-manifest.v1": "6eb3d6aba3fcbb2dfb9a06f138e9a8267760b3357410f729ec1486d2f64cf72d",
    "runtime-manifest.v2": "a93a1cce7a2a85b0e9fb5d7b237935ced1c0db78947ef4da1468f536e2ada45e",
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
    return Draft202012Validator(
        contract,
        registry=_registry(),
        format_checker=FormatChecker(),
    )


@cache
def _registry() -> Registry:
    resources = (
        (contract["$id"], Resource.from_contents(contract))
        for contract in (load_schema(name) for name in schema_names())
    )
    return Registry().with_resources(resources)


def validate_document(
    document: Mapping[str, Any],
    schema: str | None = None,
    *,
    error_type: type[ContractValidationError] = ContractValidationError,
    extension_schemas: Mapping[str, bytes | str] | None = None,
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
    validate_semantics(schema_name, document)
    validate_extensions(schema_name, document, extension_schemas)


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
    "PUBLISHED_SCHEMA_SHA256",
    "ContractValidationError",
    "ExtensionValidationError",
    "ScenarioValidationError",
    "SemanticValidationError",
    "UnknownSchemaError",
    "load_schema",
    "resolve_schema_name",
    "schema_dir",
    "schema_names",
    "schema_path",
    "validate_document",
    "validate_extensions",
    "validate_semantics",
    "validate_scenario",
]
