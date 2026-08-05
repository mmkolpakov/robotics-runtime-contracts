from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from robotics_runtime_contracts.extensions import (
    ExtensionValidationError,
)
from robotics_runtime_contracts.extensions import (
    validate_extensions as _validate_extensions,
)
from robotics_runtime_contracts.qualification_policy import (
    CHANNEL_ERROR_VIOLATIONS,
    CHANNEL_INCOMPLETE_VIOLATIONS,
    RESERVED_ASSERTION_IDS,
    ChannelObservationStatus,
    channel_observation_status,
    hardware_clock_within_policy,
)
from robotics_runtime_contracts.semantics import (
    SemanticValidationError,
)
from robotics_runtime_contracts.semantics import (
    validate_semantics as _validate_semantics,
)

PUBLISHED_SCHEMA_SHA256 = {
    "acceptance-aggregate.v4": "d68fa8bd7dee83411f920c90a325247938da4f634dc4c840167b13831b664c4d",
    "acceptance-run.v1": "541e5594aba482f14b2f644d9195c2fa6356be60aa8e5a9c1ce8c41d3e13e6c2",
    "acceptance-result.v4": "e794245312ae763169296dcb0449c3947e3fa5dcd97ba2f588608c2045579107",
    "acceptance-scenario.v4": "e1c7e2479112c33a3d67ff5de3e5c48499389a2cf9fde765af5c06af6c8a3bff",
    "dataset-manifest.v1": "b768eb96ee26e4c646eac2ba8743ba4a25bc2b668f7fe1453a474de7c10c8f08",
    "evidence-index.v2": "c71cb01eaea93909048a15c06821d6ccc484ca5c45bac1dd614f97c86ec75509",
    "execution-permit.v1": "001b125fcc66dd7e01bb044ea858edbf9e2925ca20cfde75fd228b500be57c07",
    "execution-verification.v1": (
        "916a2f164393c5ae54bfe28127b2bb85c1285aa25c93faa49766e73707c237de"
    ),
    "model-artifact-manifest.v1": (
        "eed0440e05b1846db93958db9bc7fba4bb45b451a907200b5f98f843a3577063"
    ),
    "mcap-summary.v1": "e2c8ff63268cedaf699649d39bd2fa7a6a9e49873502af72855b284a22511ccf",
    "causal-chain.v1": "67a66bec2c59956e22c4534e1300adba4c63d8fd950d7e20681e63f060ec3777",
    "qualification-bundle.v2": "66f1f2869c25e61e465aeb8eac30707f77d77458db810a98252b61e59f72fa53",
    "qualification-policy.v2": "24101fbd567dfb550c5c154a41f64460653ad512ea0332c5244b97a2aadcf265",
    "runtime-manifest.v1": "0af0870a80c8071d2904423e50aa10af5643ce9ec2ca6afd6e07b0a586071a9d",
    "runtime-manifest.v2": "509a216b7d24010f19cf1781d6c4a7307315390060eb52e6ad128f6825e740e1",
    "zenoh-channel.v1": "2febfa242150f1ceda98d4efac4b9ecfaa4c74bbba873d22d41810a619ca185b",
    "zenoh-channel-observation.v1": (
        "3596ee9478e74d27d5403536a88366ec335e77a22543cad83266db48b0f1c45f"
    ),
    "transport-qualification-result.v1": (
        "3dc2bd38f2b9ea1015fb66f28b4569cac344f30b86c6af3e2d8434bcb73a897e"
    ),
}
_SCHEMA_FILES = {name: f"{name}.schema.json" for name in PUBLISHED_SCHEMA_SHA256}
_SCHEMA_IDS = {
    f"urn:robotics-runtime-contracts:{name.replace('.', ':', 1)}": name
    for name in PUBLISHED_SCHEMA_SHA256
}


class ContractValidationError(ValueError):
    """Raised when a document does not satisfy a public contract."""

    def __init__(self, schema_name: str, error: ValidationError) -> None:
        self.schema_name = schema_name
        self.json_path = error.json_path
        self.validation_message = error.message
        super().__init__(f"{self.json_path}: {self.validation_message}")


class UnknownSchemaError(ValueError):
    """Raised when a requested schema version or identifier is not published."""


def schema_names() -> tuple[str, ...]:
    """Return published schema versions in stable order."""

    return tuple(_SCHEMA_FILES)


def resolve_schema_name(schema: str) -> str:
    """Resolve a schema version, file name, or canonical identifier."""

    if schema in _SCHEMA_FILES:
        return schema
    if schema in _SCHEMA_IDS:
        return _SCHEMA_IDS[schema]
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
    )


def validate_document(
    document: Mapping[str, Any],
    schema: str | None = None,
    *,
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
        first_error = errors[0]
        raise ContractValidationError(schema_name, first_error) from first_error
    _validate_semantics(schema_name, document)
    _validate_extensions(schema_name, document, extension_schemas)


__all__ = [
    "CHANNEL_ERROR_VIOLATIONS",
    "CHANNEL_INCOMPLETE_VIOLATIONS",
    "PUBLISHED_SCHEMA_SHA256",
    "RESERVED_ASSERTION_IDS",
    "ChannelObservationStatus",
    "ContractValidationError",
    "ExtensionValidationError",
    "SemanticValidationError",
    "UnknownSchemaError",
    "load_schema",
    "resolve_schema_name",
    "schema_dir",
    "schema_names",
    "schema_path",
    "channel_observation_status",
    "hardware_clock_within_policy",
    "validate_document",
]
