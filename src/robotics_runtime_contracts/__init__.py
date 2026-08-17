from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from functools import cache
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError
from referencing import Registry
from referencing.jsonschema import DRAFT202012, SchemaRegistry

from robotics_runtime_contracts.catalog import (
    UnknownContractRoleError,
    contract_roles,
    contract_set,
    internal_schema_names,
    role_schemas,
    schema_for_role,
)
from robotics_runtime_contracts.extensions import (
    ExtensionValidationError,
)
from robotics_runtime_contracts.extensions import (
    validate_extensions as _validate_extensions,
)
from robotics_runtime_contracts.providers import (
    ProviderRequirementError,
    scene_satisfies,
    validate_provider_requirements,
)
from robotics_runtime_contracts.qualification_policy import (
    CHANNEL_ERROR_VIOLATIONS,
    CHANNEL_INCOMPLETE_VIOLATIONS,
    RESERVED_ASSERTION_IDS,
    RESERVED_METRIC_NAMES,
    ChannelObservationStatus,
    ClockEvidenceValidationError,
    channel_observation_status,
    derive_channel_violations,
    hardware_clock_within_policy,
    validate_clock_relation_evidence,
)
from robotics_runtime_contracts.receipts import (
    ArtifactReceiptValidationError,
    validate_artifact_receipt,
)
from robotics_runtime_contracts.semantics import (
    SemanticValidationError,
)
from robotics_runtime_contracts.semantics import (
    validate_semantics as _validate_semantics,
)
from robotics_runtime_contracts.serialization import (
    DocumentParseError,
    NonFiniteNumberError,
    ensure_finite_numbers,
    load_mapping,
    loads_mapping,
)
from robotics_runtime_contracts.status import OutcomeStatus, worst_status

_PUBLIC_SCHEMA_FILES = {name: f"{name}.schema.json" for name in role_schemas().values()}
_INTERNAL_SCHEMA_FILES = {name: f"{name}.schema.json" for name in internal_schema_names()}
_SCHEMA_FILES = _PUBLIC_SCHEMA_FILES | _INTERNAL_SCHEMA_FILES


class ContractValidationError(ValueError):
    """Raised when a document does not satisfy a public contract."""

    error_id = "schema.validation_failed"

    def __init__(self, schema_name: str, error: ValidationError) -> None:
        self.schema_name = schema_name
        self.json_path = error.json_path
        self.validation_message = error.message
        super().__init__(f"{self.json_path}: {self.validation_message}")


class UnknownSchemaError(ValueError):
    """Raised when a requested schema version or identifier is not published."""

    error_id = "schema.unknown"


def schema_names() -> tuple[str, ...]:
    """Return canonical public schemas in stable role order."""

    return tuple(_PUBLIC_SCHEMA_FILES)


def schema_resource_names() -> tuple[str, ...]:
    """Return public and internal resources used by the offline registry."""

    return tuple(_SCHEMA_FILES)


@cache
def _schema_ids() -> dict[str, str]:
    return {
        cast(str, json.loads((schema_dir() / file_name).read_text(encoding="utf-8"))["$id"]): name
        for name, file_name in _SCHEMA_FILES.items()
    }


def resolve_schema_name(schema: str) -> str:
    """Resolve a schema version, file name, or canonical identifier."""

    if schema in _SCHEMA_FILES:
        return schema
    if schema in _schema_ids():
        return _schema_ids()[schema]
    for schema_name, file_name in _SCHEMA_FILES.items():
        if schema == file_name:
            return schema_name
    raise UnknownSchemaError(f"Unknown schema: {schema}")


def schema_dir() -> Path:
    return Path(str(files("robotics_runtime_contracts").joinpath("schemas")))


def schema_path(schema: str) -> Path:
    schema_name = resolve_schema_name(schema)
    path = schema_dir() / _SCHEMA_FILES[schema_name]
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def schema_digest(schema: str) -> str:
    """Return the SHA-256 digest of the packaged schema resource."""

    return sha256(schema_path(schema).read_bytes()).hexdigest()


@cache
def _load_schema(schema: str) -> dict[str, Any]:
    schema_name = resolve_schema_name(schema)
    return cast(
        dict[str, Any],
        json.loads(schema_path(schema_name).read_text(encoding="utf-8")),
    )


def load_schema(schema: str) -> dict[str, Any]:
    """Return an isolated copy of a published schema."""

    return deepcopy(_load_schema(resolve_schema_name(schema)))


@cache
def _validator(schema: str) -> Draft202012Validator:
    schema_name = resolve_schema_name(schema)
    contract = _load_schema(schema_name)
    Draft202012Validator.check_schema(contract)
    return Draft202012Validator(
        contract,
        format_checker=FormatChecker(),
        registry=_schema_registry(),
    )


@cache
def _schema_registry() -> SchemaRegistry:
    return Registry().with_resources(
        (
            schema["$id"],
            DRAFT202012.create_resource(schema),
        )
        for name in _SCHEMA_FILES
        for schema in (_load_schema(name),)
    )


def schema_registry() -> SchemaRegistry:
    """Return an isolated offline registry for all published schema IDs."""

    return Registry().with_resources(
        (
            schema["$id"],
            DRAFT202012.create_resource(schema),
        )
        for name in _SCHEMA_FILES
        for schema in (load_schema(name),)
    )


def validate_document(
    document: Mapping[str, Any],
    schema: str | None = None,
    *,
    extension_schemas: Mapping[str, bytes | str] | None = None,
) -> None:
    """Validate a document against an explicit or declared schema version."""

    ensure_finite_numbers(document)
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
        first_error = errors[0]
        raise ContractValidationError(schema_name, first_error) from first_error
    _validate_semantics(schema_name, document)
    _validate_extensions(schema_name, document, extension_schemas)


def validate_role(
    document: Mapping[str, Any],
    role: str,
    *,
    extension_schemas: Mapping[str, bytes | str] | None = None,
) -> None:
    """Validate a document against the canonical schema for its role."""

    validate_document(document, schema_for_role(role), extension_schemas=extension_schemas)


__all__ = [
    "CHANNEL_ERROR_VIOLATIONS",
    "CHANNEL_INCOMPLETE_VIOLATIONS",
    "OutcomeStatus",
    "RESERVED_ASSERTION_IDS",
    "RESERVED_METRIC_NAMES",
    "ChannelObservationStatus",
    "ClockEvidenceValidationError",
    "ContractValidationError",
    "ArtifactReceiptValidationError",
    "DocumentParseError",
    "ExtensionValidationError",
    "NonFiniteNumberError",
    "ProviderRequirementError",
    "SemanticValidationError",
    "UnknownContractRoleError",
    "UnknownSchemaError",
    "contract_roles",
    "contract_set",
    "ensure_finite_numbers",
    "load_schema",
    "load_mapping",
    "loads_mapping",
    "resolve_schema_name",
    "role_schemas",
    "schema_digest",
    "schema_dir",
    "schema_for_role",
    "schema_names",
    "schema_path",
    "schema_registry",
    "schema_resource_names",
    "scene_satisfies",
    "channel_observation_status",
    "derive_channel_violations",
    "hardware_clock_within_policy",
    "validate_clock_relation_evidence",
    "validate_artifact_receipt",
    "validate_document",
    "validate_provider_requirements",
    "validate_role",
    "worst_status",
]
