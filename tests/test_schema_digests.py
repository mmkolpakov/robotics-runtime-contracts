import json
from hashlib import sha256
from pathlib import Path

import pytest

from robotics_runtime_contracts import schema_digest, schema_dir, schema_resource_names

SNAPSHOT = Path(__file__).parents[1] / "docs" / "schema-digests.json"
PUBLISHED_DIGESTS: dict[str, str] = json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def test_published_resource_inventory_matches_snapshot() -> None:
    installed = {path.name for path in schema_dir().glob("*.json")}
    registered = {f"{name}.schema.json" for name in schema_resource_names()} | {"catalog.v1.json"}
    assert installed == registered == set(PUBLISHED_DIGESTS)


@pytest.mark.parametrize("file_name,expected_digest", sorted(PUBLISHED_DIGESTS.items()))
def test_published_resource_bytes_match_snapshot(file_name: str, expected_digest: str) -> None:
    actual_digest = sha256((schema_dir() / file_name).read_bytes()).hexdigest()
    assert actual_digest == expected_digest, (
        f"Published resource changed: {file_name}. Review compatibility before updating {SNAPSHOT}."
    )
    if file_name.endswith(".schema.json"):
        assert schema_digest(file_name) == expected_digest
