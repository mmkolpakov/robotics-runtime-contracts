from __future__ import annotations

import json
from functools import cache
from importlib.resources import files
from types import MappingProxyType
from typing import Any, cast


class UnknownContractRoleError(ValueError):
    """Raised when a caller requests an unpublished document role."""

    error_id = "schema.role_unknown"


@cache
def _catalog() -> dict[str, Any]:
    resource = files("robotics_runtime_contracts").joinpath("schemas", "catalog.v1.json")
    return cast(dict[str, Any], json.loads(resource.read_text(encoding="utf-8")))


def contract_set() -> str:
    """Return the single published contract-set identifier."""

    return str(_catalog()["contract_set"])


def role_schemas() -> MappingProxyType[str, str]:
    """Return the immutable role-to-schema catalog."""

    return MappingProxyType(dict(_catalog()["roles"]))


def contract_roles() -> tuple[str, ...]:
    """Return published document roles in stable order."""

    return tuple(role_schemas())


def schema_for_role(role: str) -> str:
    """Resolve a public document role to its canonical schema."""

    try:
        return role_schemas()[role]
    except KeyError as error:
        raise UnknownContractRoleError(f"Unknown contract role: {role}") from error


def internal_schema_names() -> tuple[str, ...]:
    """Return schema resources used only for modular references."""

    return tuple(str(item) for item in _catalog()["internal_resources"])
