from __future__ import annotations

import json
from collections.abc import Mapping
from hashlib import sha256
from typing import Any, NoReturn

from jsonschema import Draft202012Validator, FormatChecker

from robotics_runtime_contracts.semantics import SemanticValidationError


class ExtensionValidationError(SemanticValidationError):
    """Raised when a declared domain extension cannot be verified."""


def _fail(schema_name: str, path: str, message: str) -> NoReturn:
    raise ExtensionValidationError(schema_name, path, message)


def _reject_external_references(schema_name: str, value: object, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in {"$ref", "$dynamicRef"} and (
                not isinstance(child, str) or not child.startswith("#")
            ):
                _fail(schema_name, child_path, "external schema references are not allowed")
            _reject_external_references(schema_name, child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_external_references(schema_name, child, f"{path}[{index}]")


def validate_extensions(
    schema_name: str,
    document: Mapping[str, Any],
    schema_documents: Mapping[str, bytes | str] | None,
) -> None:
    """Validate declared scenario extensions without performing network access."""

    if not schema_name.startswith("acceptance-scenario."):
        return

    declarations = document.get("extension_schemas", [])
    extensions = document.get("extensions", {})
    if not declarations and not extensions:
        return
    if not isinstance(schema_documents, Mapping):
        _fail(
            schema_name,
            "$.extension_schemas",
            "declared extensions require supplied schema documents",
        )

    declared_namespaces = [item["namespace"] for item in declarations]
    if len(declared_namespaces) != len(set(declared_namespaces)):
        _fail(schema_name, "$.extension_schemas", "namespaces must be unique")
    if set(declared_namespaces) != set(extensions):
        _fail(
            schema_name,
            "$.extensions",
            "extension payload namespaces must exactly match extension_schemas",
        )

    for index, declaration in enumerate(declarations):
        namespace = declaration["namespace"]
        uri = declaration["schema_uri"]
        try:
            raw_document = schema_documents[uri]
        except KeyError:
            _fail(
                schema_name,
                f"$.extension_schemas[{index}].schema_uri",
                "schema document was not supplied",
            )
        raw_bytes = (
            raw_document if isinstance(raw_document, bytes) else raw_document.encode("utf-8")
        )
        if sha256(raw_bytes).hexdigest() != declaration["sha256"]:
            _fail(
                schema_name,
                f"$.extension_schemas[{index}].sha256",
                "schema digest does not match",
            )

        try:
            extension_schema = json.loads(raw_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            _fail(
                schema_name,
                f"$.extension_schemas[{index}]",
                f"schema must be UTF-8 JSON: {error}",
            )
        if not isinstance(extension_schema, dict):
            _fail(schema_name, f"$.extension_schemas[{index}]", "schema root must be an object")
        if extension_schema.get("$id") != uri:
            _fail(
                schema_name,
                f"$.extension_schemas[{index}].schema_uri",
                "must match the schema $id",
            )

        _reject_external_references(schema_name, extension_schema)
        try:
            Draft202012Validator.check_schema(extension_schema)
        except Exception as error:
            _fail(
                schema_name,
                f"$.extension_schemas[{index}]",
                f"invalid Draft 2020-12 schema: {error}",
            )

        errors = sorted(
            Draft202012Validator(
                extension_schema,
                format_checker=FormatChecker(),
            ).iter_errors(extensions[namespace]),
            key=lambda error: tuple(str(part) for part in error.path),
        )
        if errors:
            validation_error = errors[0]
            suffix = validation_error.json_path.removeprefix("$")
            _fail(
                schema_name,
                f"$.extensions.{namespace}{suffix}",
                validation_error.message,
            )


__all__ = ["ExtensionValidationError", "validate_extensions"]
