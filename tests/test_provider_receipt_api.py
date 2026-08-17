from __future__ import annotations

from copy import deepcopy

import pytest

from robotics_runtime_contracts import (
    ArtifactReceiptValidationError,
    ProviderRequirementError,
    validate_artifact_receipt,
    validate_provider_requirements,
)


def test_provider_requirement_needs_one_complete_scene() -> None:
    requirements = {
        "capabilities": ["simulated_physics"],
        "scene": {
            "semantic_scene_id": "sorting-cell",
            "required_entities": ["camera"],
            "required_interfaces": ["/camera/image"],
            "physical_parameters": {"gravity_m_s2": 9.80665},
        },
    }
    bindings = [
        {
            "capabilities": ["simulated_physics"],
            "scene": {
                "semantic_scene_id": "sorting-cell",
                "entities": ["camera"],
                "interfaces": [],
                "physical_parameters": {"gravity_m_s2": 9.80665},
            },
        },
        {
            "capabilities": [],
            "scene": {
                "semantic_scene_id": "sorting-cell",
                "entities": [],
                "interfaces": ["/camera/image"],
                "physical_parameters": {"gravity_m_s2": 9.80665},
            },
        },
    ]

    with pytest.raises(ProviderRequirementError, match="no single provider scene"):
        validate_provider_requirements(requirements, bindings)


def test_artifact_receipt_binds_the_complete_descriptor() -> None:
    artifact = {
        "uri": "s3://evidence/run/output.mcap?versionId=1",
        "sha256": "a" * 64,
        "size_bytes": 10,
        "media_type": "application/mcap",
        "immutable_revision": "version-id:1",
    }
    receipt = {
        "artifact": artifact,
        "producer": {"identity": "builder", "implementation": "cosign"},
        "statement_sha256": "b" * 64,
        "created_at": "2026-07-11T12:00:02Z",
    }
    verification = {
        "artifact": deepcopy(artifact),
        "producer_identity": "builder",
        "producer_implementation": "cosign",
        "statement_sha256": "b" * 64,
        "trust_policy_sha256": "c" * 64,
        "verification_evidence_sha256": "d" * 64,
        "verified_at": "2026-07-11T12:00:01Z",
    }
    dependencies = {"b" * 64, "c" * 64, "d" * 64}

    assert validate_artifact_receipt(receipt, verification, dependencies) == dependencies

    verification["artifact"]["immutable_revision"] = "version-id:2"
    with pytest.raises(ArtifactReceiptValidationError, match="artifact descriptor"):
        validate_artifact_receipt(receipt, verification, dependencies)
