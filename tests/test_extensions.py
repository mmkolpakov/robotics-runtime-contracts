from __future__ import annotations

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest
import yaml

from robotics_runtime_contracts import (
    ExtensionValidationError,
    migrate_scenario_v1_to_v2,
    validate_document,
)

FIXTURE = Path(__file__).parent / "fixtures" / "scenario" / "valid" / "simulation-realtime.yaml"
SCHEMA_URI = "https://schemas.example.org/sorting-item.v1.schema.json"


def extension_schema() -> bytes:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_URI,
        "type": "object",
        "additionalProperties": False,
        "required": ["item_id"],
        "properties": {"item_id": {"type": "string", "minLength": 1}},
    }
    return json.dumps(schema, separators=(",", ":"), sort_keys=True).encode()


def scenario_with_extension() -> dict[str, object]:
    scenario = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    raw_schema = extension_schema()
    scenario["extension_schemas"] = [
        {
            "namespace": "org.example.sorting",
            "schema_uri": SCHEMA_URI,
            "sha256": sha256(raw_schema).hexdigest(),
        }
    ]
    scenario["extensions"] = {"org.example.sorting": {"item_id": "parcel-42"}}
    return scenario


def migrated_scenario_with_extension() -> dict[str, object]:
    return migrate_scenario_v1_to_v2(
        scenario_with_extension(),
        metric_attributes={"camera-age": {"topic": "/camera/image"}},
        time_authority_min_samples=30,
        max_clock_offset_p50_ms=1,
        max_clock_offset_p95_ms=2,
        max_clock_offset_ms=5,
    )


def test_namespaced_extension_is_validated_from_digest_pinned_json() -> None:
    validate_document(
        scenario_with_extension(),
        extension_schemas={SCHEMA_URI: extension_schema()},
    )


def test_declared_extension_requires_caller_supplied_schema() -> None:
    with pytest.raises(ExtensionValidationError, match="was not supplied"):
        validate_document(scenario_with_extension(), extension_schemas={})


def test_extension_schema_digest_is_verified() -> None:
    with pytest.raises(ExtensionValidationError, match="digest does not match"):
        validate_document(
            scenario_with_extension(),
            extension_schemas={SCHEMA_URI: extension_schema() + b" "},
        )


def test_extension_payload_must_satisfy_its_schema() -> None:
    scenario = scenario_with_extension()
    scenario["extensions"]["org.example.sorting"] = {"item_id": ""}
    with pytest.raises(ExtensionValidationError) as caught:
        validate_document(scenario, extension_schemas={SCHEMA_URI: extension_schema()})
    assert caught.value.json_path == "$.extensions.org.example.sorting.item_id"


def test_migrated_v2_extension_remains_validated() -> None:
    scenario = migrated_scenario_with_extension()
    validate_document(scenario, extension_schemas={SCHEMA_URI: extension_schema()})

    scenario["extensions"]["org.example.sorting"] = {"item_id": ""}
    with pytest.raises(ExtensionValidationError) as caught:
        validate_document(scenario, extension_schemas={SCHEMA_URI: extension_schema()})
    assert caught.value.json_path == "$.extensions.org.example.sorting.item_id"


def test_external_references_are_rejected_without_network_access() -> None:
    scenario = scenario_with_extension()
    unsafe = json.loads(extension_schema())
    unsafe["properties"]["item_id"] = {"$ref": "https://example.org/remote.json"}
    raw_unsafe = json.dumps(unsafe, separators=(",", ":"), sort_keys=True).encode()
    scenario["extension_schemas"][0]["sha256"] = sha256(raw_unsafe).hexdigest()

    with pytest.raises(ExtensionValidationError, match="external schema references"):
        validate_document(scenario, extension_schemas={SCHEMA_URI: raw_unsafe})


def test_extension_cannot_be_registered_without_matching_payload() -> None:
    scenario = deepcopy(scenario_with_extension())
    scenario["extensions"] = {}
    with pytest.raises(ExtensionValidationError, match="exactly match"):
        validate_document(scenario, extension_schemas={SCHEMA_URI: extension_schema()})
