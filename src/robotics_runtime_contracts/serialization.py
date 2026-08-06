from __future__ import annotations

import json
from collections.abc import Mapping
from math import isfinite
from pathlib import Path
from typing import Any

import yaml


class DocumentParseError(ValueError):
    """Raised when a JSON or YAML document cannot be loaded as an object."""


class NonFiniteNumberError(ValueError):
    """Raised when a document contains a number forbidden by RFC 8259."""

    error_id = "input.non_finite_number"


def ensure_finite_numbers(value: Any, path: str = "$") -> None:
    """Reject NaN and infinities before schema or policy evaluation."""

    if isinstance(value, float) and not isfinite(value):
        raise NonFiniteNumberError(f"{path}: non-finite numbers are not valid JSON")
    if isinstance(value, Mapping):
        for key, item in value.items():
            ensure_finite_numbers(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            ensure_finite_numbers(item, f"{path}[{index}]")


def _reject_json_constant(value: str) -> Any:
    raise NonFiniteNumberError(f"non-finite JSON number: {value}")


def loads_mapping(
    source: str | bytes,
    *,
    source_name: str = "document",
) -> dict[str, Any]:
    """Parse a JSON or YAML object while preserving JSON number semantics."""

    text = source.decode("utf-8") if isinstance(source, bytes) else source
    try:
        value = json.loads(text, parse_constant=_reject_json_constant)
    except json.JSONDecodeError:
        try:
            value = yaml.safe_load(text)
        except yaml.YAMLError as error:
            raise DocumentParseError(f"cannot parse {source_name}: {error}") from error
    if not isinstance(value, Mapping):
        raise DocumentParseError(f"{source_name} must contain an object")
    ensure_finite_numbers(value)
    return dict(value)


def load_mapping(path: str | Path) -> dict[str, Any]:
    """Load a JSON or YAML object from disk."""

    document_path = Path(path)
    return loads_mapping(document_path.read_bytes(), source_name=str(document_path))


__all__ = [
    "DocumentParseError",
    "NonFiniteNumberError",
    "ensure_finite_numbers",
    "load_mapping",
    "loads_mapping",
]
