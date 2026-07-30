from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from robotics_runtime_contracts import (
    ContractValidationError,
    SemanticValidationError,
    validate_document,
)
from tests.support import load_fixture

FIXTURES = Path(__file__).parent / "fixtures" / "evidence-index"


@pytest.mark.parametrize("field", ["segment_index", "uri"])
def test_evidence_segments_are_unique(field: str) -> None:
    document = load_fixture(FIXTURES / "valid" / "mixed.yaml")
    segments = document["segments"]
    assert isinstance(segments, list)
    first, second = segments
    assert isinstance(first, dict)
    assert isinstance(second, dict)
    second[field] = first[field]
    if field == "uri":
        second.pop("version_id", None)

    with pytest.raises(SemanticValidationError):
        validate_document(document)


def test_mcap_segment_requires_a_deterministic_summary() -> None:
    document = load_fixture(FIXTURES / "valid" / "mixed.yaml")
    document["segments"][0].pop("mcap_summary")

    with pytest.raises(ContractValidationError) as caught:
        validate_document(document)

    assert caught.value.json_path == "$.segments[0]"


def test_mcap_summary_requires_a_consistent_channel_count() -> None:
    summary = {
        "schema_version": "mcap-summary.v1",
        "source_sha256": "a" * 64,
        "compressions": ["zstd"],
        "statistics": {
            "message_count": 10,
            "schema_count": 1,
            "channel_count": 1,
            "attachment_count": 0,
            "metadata_count": 1,
            "chunk_count": 1,
            "message_start_time_ns": 1,
            "message_end_time_ns": 2,
        },
        "channels": [
            {
                "topic": "/camera/image",
                "message_encoding": "cdr",
                "schema_name": "sensor_msgs/msg/Image",
                "message_count": 10,
            }
        ],
    }
    validate_document(summary)

    invalid = deepcopy(summary)
    invalid["statistics"]["channel_count"] = 2
    with pytest.raises(SemanticValidationError, match="summarized channels"):
        validate_document(invalid)
