from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from secrets import token_hex
from typing import Any
from uuid import uuid4

from json_merge_patch import create_patch, merge  # type: ignore[import-untyped]

from robotics_runtime_contracts import (
    PUBLISHED_SCHEMA_SHA256,
    load_schema,
    resolve_schema_name,
    validate_document,
)


def _resolve_property(
    value: Mapping[str, Any],
    *,
    current_schema: Mapping[str, Any],
) -> Mapping[str, Any]:
    resolved = value
    schema = current_schema
    visited: set[str] = set()
    while "$ref" in resolved:
        reference = str(resolved["$ref"])
        if reference in visited:
            raise ValueError(f"cyclic schema reference: {reference}")
        visited.add(reference)
        schema_id, _, fragment = reference.partition("#")
        if schema_id:
            schema = load_schema(schema_id)
        target: Any = schema
        if fragment:
            if not fragment.startswith("/"):
                raise ValueError(f"unsupported schema fragment: {reference}")
            for token in fragment[1:].split("/"):
                key = token.replace("~1", "/").replace("~0", "~")
                target = target[key]
        if not isinstance(target, Mapping):
            raise ValueError(f"schema reference does not resolve to an object: {reference}")
        resolved = target
    return resolved


def describe_schema(schema_name: str) -> dict[str, Any]:
    """Return a stable, machine-readable summary derived from a published schema."""

    canonical_name = resolve_schema_name(schema_name)
    schema = load_schema(canonical_name)
    properties = schema.get("properties", {})
    return {
        "schema": canonical_name,
        "id": schema["$id"],
        "sha256": PUBLISHED_SCHEMA_SHA256[canonical_name],
        "title": schema.get("title", ""),
        "description": schema.get("description", ""),
        "required": list(schema.get("required", [])),
        "properties": {
            name: {
                key: resolved[key]
                for key in ("type", "description", "const", "enum", "$ref")
                if key in resolved
            }
            for name, value in properties.items()
            for resolved in (_resolve_property(value, current_schema=schema),)
        },
    }


def resolve_merge_patches(
    base: Mapping[str, Any],
    overlays: Sequence[Mapping[str, Any]],
    *,
    extension_schemas: Mapping[str, bytes | str] | None = None,
) -> dict[str, Any]:
    """Materialize RFC 7396 overlays and validate the resulting document."""

    resolved: dict[str, Any] = deepcopy(dict(base))
    for overlay in overlays:
        resolved = merge(resolved, deepcopy(dict(overlay)))
    validate_document(resolved, extension_schemas=extension_schemas)
    return resolved


def semantic_diff(
    source: Mapping[str, Any],
    target: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the minimal RFC 7396 patch from source to target."""

    patch = create_patch(dict(source), dict(target))
    if not isinstance(patch, dict):
        raise ValueError("document roots must remain objects")
    if merge(deepcopy(dict(source)), deepcopy(patch)) != dict(target):
        raise ValueError(
            "target cannot be represented by RFC 7396 because null denotes member removal"
        )
    return patch


def create_execution_permit(
    *,
    scenario_sha256: str,
    image_digest: str,
    trust_policy_sha256: str,
    environment: str,
    target_id: str,
    identity_kind: str,
    identity_sha256: str,
    hardware_scope: Sequence[str],
    operator_id: str,
    approver_id: str,
    interlock_reference: str,
    interlock_sha256: str,
    validity_sec: int = 900,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create a validated, unsigned physical-execution permit predicate."""

    if not 1 <= validity_sec <= 1800:
        raise ValueError("validity_sec must be between 1 and 1800")
    issued_at = (now or datetime.now(UTC)).astimezone(UTC)
    expires_at = issued_at + timedelta(seconds=validity_sec)
    document = {
        "schema_version": "execution-permit.v1",
        "predicate_type": (
            "https://robotics-runtime-contracts.dev/attestations/execution-permit/v1"
        ),
        "permit_id": f"permit-{uuid4()}",
        "scenario_sha256": scenario_sha256,
        "image_digest": image_digest,
        "trust_policy_sha256": trust_policy_sha256,
        "target": {
            "environment": environment,
            "target_id": target_id,
            "identity_kind": identity_kind,
            "identity_sha256": identity_sha256,
        },
        "allowed_physical_effect": "none" if environment == "hil" else "observation",
        "hardware_scope": list(hardware_scope),
        "issued_at": issued_at.isoformat().replace("+00:00", "Z"),
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
        "nonce": token_hex(32),
        "operator_id": operator_id,
        "approver_id": approver_id,
        "interlock_check": {
            "reference": interlock_reference,
            "sha256": interlock_sha256,
            "status": "passed",
            "checked_at": issued_at.isoformat().replace("+00:00", "Z"),
        },
    }
    validate_document(document)
    return document


__all__ = [
    "create_execution_permit",
    "describe_schema",
    "resolve_merge_patches",
    "semantic_diff",
]
