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

from robotics_runtime_contracts.extensions import ExtensionValidationError, validate_extensions
from robotics_runtime_contracts.migration import migrate_scenario_v1_to_v2
from robotics_runtime_contracts.semantics import SemanticValidationError, validate_semantics

SCHEMA_NAME = "acceptance-scenario.v1.schema.json"
SCHEMA_FILES = {
    "acceptance-scenario.v1": SCHEMA_NAME,
    "acceptance-scenario.v2": "acceptance-scenario.v2.schema.json",
    "model-artifact-manifest.v1": "model-artifact-manifest.v1.schema.json",
    "dataset-manifest.v1": "dataset-manifest.v1.schema.json",
    "runtime-manifest.v1": "runtime-manifest.v1.schema.json",
    "execution-permit.v1": "execution-permit.v1.schema.json",
    "execution-verification.v1": "execution-verification.v1.schema.json",
    "acceptance-result.v1": "acceptance-result.v1.schema.json",
    "acceptance-result.v2": "acceptance-result.v2.schema.json",
    "evidence-index.v1": "evidence-index.v1.schema.json",
    "evidence-index.v2": "evidence-index.v2.schema.json",
    "acceptance-run.v1": "acceptance-run.v1.schema.json",
    "acceptance-aggregate.v1": "acceptance-aggregate.v1.schema.json",
    "acceptance-aggregate.v2": "acceptance-aggregate.v2.schema.json",
    "mcap-summary.v1": "mcap-summary.v1.schema.json",
    "causal-chain.v1": "causal-chain.v1.schema.json",
    "qualification-bundle.v1": "qualification-bundle.v1.schema.json",
    "qualification-policy.v1": "qualification-policy.v1.schema.json",
    "zenoh-channel.v1": "zenoh-channel.v1.schema.json",
    "zenoh-channel-observation.v1": "zenoh-channel-observation.v1.schema.json",
}
SCHEMA_IDS = {
    "urn:robotics-runtime-contracts:acceptance-scenario:v1": "acceptance-scenario.v1",
    "urn:robotics-runtime-contracts:acceptance-scenario:v2": "acceptance-scenario.v2",
    "urn:robotics-runtime-contracts:model-artifact-manifest:v1": "model-artifact-manifest.v1",
    "urn:robotics-runtime-contracts:dataset-manifest:v1": "dataset-manifest.v1",
    "urn:robotics-runtime-contracts:runtime-manifest:v1": "runtime-manifest.v1",
    "urn:robotics-runtime-contracts:execution-permit:v1": "execution-permit.v1",
    "urn:robotics-runtime-contracts:execution-verification:v1": "execution-verification.v1",
    "urn:robotics-runtime-contracts:acceptance-result:v1": "acceptance-result.v1",
    "urn:robotics-runtime-contracts:acceptance-result:v2": "acceptance-result.v2",
    "urn:robotics-runtime-contracts:evidence-index:v1": "evidence-index.v1",
    "urn:robotics-runtime-contracts:evidence-index:v2": "evidence-index.v2",
    "urn:robotics-runtime-contracts:acceptance-run:v1": "acceptance-run.v1",
    "urn:robotics-runtime-contracts:acceptance-aggregate:v1": "acceptance-aggregate.v1",
    "urn:robotics-runtime-contracts:acceptance-aggregate:v2": "acceptance-aggregate.v2",
    "urn:robotics-runtime-contracts:mcap-summary:v1": "mcap-summary.v1",
    "urn:robotics-runtime-contracts:causal-chain:v1": "causal-chain.v1",
    "urn:robotics-runtime-contracts:qualification-bundle:v1": "qualification-bundle.v1",
    "urn:robotics-runtime-contracts:qualification-policy:v1": "qualification-policy.v1",
    "urn:robotics-runtime-contracts:zenoh-channel:v1": "zenoh-channel.v1",
    "urn:robotics-runtime-contracts:zenoh-channel-observation:v1": ("zenoh-channel-observation.v1"),
}
PUBLISHED_SCHEMA_SHA256 = {
    "acceptance-aggregate.v1": ("8e540fd5ee307767cd95d998ac1339d70a760da99e2840dd79bc71a047d9c322"),
    "acceptance-aggregate.v2": "1aa05fcfde950b27ae70e167287527cd3bbc61ecb972fd2381dc716c15704b7a",
    "acceptance-run.v1": "541e5594aba482f14b2f644d9195c2fa6356be60aa8e5a9c1ce8c41d3e13e6c2",
    "acceptance-result.v1": "ce2322787a615839c3a3e21b00ce51ea08236d780ba4c482d205fb7330d0ba0a",
    "acceptance-result.v2": "6a5f7f9083dc2cf370afe1d4098ee99d74779509cf5f6af558aa152ed0b3d1fd",
    "acceptance-scenario.v1": "9d8958b44affce2f9058658e073f8342ac4280b87e3232c10d5bf86ad4f9ce34",
    "acceptance-scenario.v2": "eeaceba3f1ba9e212b97e4b4f98e49acfedc19c42600dd07bc3b1465f1ae53eb",
    "dataset-manifest.v1": "b768eb96ee26e4c646eac2ba8743ba4a25bc2b668f7fe1453a474de7c10c8f08",
    "evidence-index.v1": "29b8d93a5ead7cea35d6a7c4b8c66cffccb43a9202694781767b3550895b21af",
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
    "qualification-bundle.v1": "3ccb3f8651b8cdfb2d1de661cdc03e0004d3b3bd4929d1ab2f6e4ddc3287defc",
    "qualification-policy.v1": "4804d7035b5d1c8cf99bb3028a0d37b333b7d0da873cc90d6f81c1cb8baf528a",
    "runtime-manifest.v1": "0af0870a80c8071d2904423e50aa10af5643ce9ec2ca6afd6e07b0a586071a9d",
    "zenoh-channel.v1": "2febfa242150f1ceda98d4efac4b9ecfaa4c74bbba873d22d41810a619ca185b",
    "zenoh-channel-observation.v1": (
        "3596ee9478e74d27d5403536a88366ec335e77a22543cad83266db48b0f1c45f"
    ),
}


class ContractValidationError(ValueError):
    """Raised when a document does not satisfy a public contract."""

    def __init__(self, schema_name: str, error: ValidationError) -> None:
        self.schema_name = schema_name
        self.json_path = error.json_path
        self.validation_message = error.message
        super().__init__(f"{self.json_path}: {self.validation_message}")


class ScenarioValidationError(ContractValidationError):
    """Raised when an acceptance scenario does not satisfy its contract."""


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
def _load_schema(schema: str) -> dict[str, Any]:
    schema_name = resolve_schema_name(schema)
    return cast(
        dict[str, Any],
        json.loads(schema_path(schema_name).read_text(encoding="utf-8")),
    )


def load_schema(schema: str = "acceptance-scenario.v1") -> dict[str, Any]:
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
        first_error = errors[0]
        raise error_type(schema_name, first_error) from first_error
    validate_semantics(schema_name, document)
    validate_extensions(schema_name, document, extension_schemas)


def validate_scenario(scenario: Mapping[str, Any]) -> None:
    """Validate an acceptance scenario."""

    schema_version = scenario.get("schema_version")
    if schema_version not in {"acceptance-scenario.v1", "acceptance-scenario.v2"}:
        raise UnknownSchemaError(f"Unknown acceptance scenario schema: {schema_version}")
    validate_document(
        scenario,
        schema=schema_version,
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
    "migrate_scenario_v1_to_v2",
    "resolve_schema_name",
    "schema_dir",
    "schema_names",
    "schema_path",
    "validate_document",
    "validate_extensions",
    "validate_semantics",
    "validate_scenario",
]
