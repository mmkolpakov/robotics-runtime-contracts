from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
import yaml

from robotics_runtime_contracts import validate_document

EXAMPLES = Path(__file__).parents[1] / "consumer-examples"
MINIMAL_SIMULATION = EXAMPLES / "minimal-simulation"
DOCUMENTS = sorted(EXAMPLES.rglob("*.yaml"))


def load_document(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda path: str(path.relative_to(EXAMPLES)))
def test_consumer_example(path: Path) -> None:
    validate_document(load_document(path))


def test_consumer_catalog_is_not_empty() -> None:
    assert DOCUMENTS


def test_minimal_simulation_uses_actual_artifact_digest_chain() -> None:
    scenario_path = MINIMAL_SIMULATION / "scenario.yaml"
    runtime_path = MINIMAL_SIMULATION / "runtime-manifest.yaml"
    run_path = MINIMAL_SIMULATION / "acceptance-run.yaml"
    result_path = MINIMAL_SIMULATION / "acceptance-result.yaml"
    evidence_index_path = MINIMAL_SIMULATION / "evidence-index.yaml"
    time_evidence_path = MINIMAL_SIMULATION / "evidence" / "time-authority.json"

    scenario = load_document(scenario_path)
    runtime = load_document(runtime_path)
    run = load_document(run_path)
    result = load_document(result_path)
    aggregate = load_document(MINIMAL_SIMULATION / "acceptance-aggregate.yaml")
    evidence_index = load_document(evidence_index_path)

    assert run["scenario_id"] == scenario["scenario_id"] == result["scenario_id"]
    assert run["run_id"] == result["run_id"] == aggregate["run_id"] == evidence_index["run_id"]
    assert {item["domain_id"] for item in run["domains"]} == {result["domain_id"]}
    assert aggregate["per_domain_results"][0]["domain_id"] == result["domain_id"]
    assert aggregate["per_domain_results"][0]["result_id"] == result["result_id"]

    assert run["scenario_sha256"] == file_sha256(scenario_path)
    assert result["scenario_sha256"] == file_sha256(scenario_path)
    assert result["runtime_manifest_sha256"] == file_sha256(runtime_path)
    assert aggregate["acceptance_run_sha256"] == file_sha256(run_path)
    assert aggregate["per_domain_results"][0]["result_sha256"] == file_sha256(result_path)

    time_evidence_sha256 = file_sha256(time_evidence_path)
    time_evidence_size = time_evidence_path.stat().st_size
    result_evidence = result["evidence"][0]
    indexed_evidence = evidence_index["segments"][0]
    assert result["time_authority_observation"]["evidence_sha256"] == time_evidence_sha256
    assert result_evidence["sha256"] == indexed_evidence["sha256"] == time_evidence_sha256
    assert result_evidence["size_bytes"] == indexed_evidence["size_bytes"] == time_evidence_size
    assert result_evidence["uri"] == indexed_evidence["uri"]

    linked_digests = {
        run["scenario_sha256"],
        result["runtime_manifest_sha256"],
        aggregate["acceptance_run_sha256"],
        aggregate["per_domain_results"][0]["result_sha256"],
        time_evidence_sha256,
    }
    assert len(linked_digests) == 5
    assert runtime["schema_version"] == "runtime-manifest.v1"


def test_minimal_simulation_observed_graph_satisfies_expected_graph() -> None:
    scenario = load_document(MINIMAL_SIMULATION / "scenario.yaml")
    result = load_document(MINIMAL_SIMULATION / "acceptance-result.yaml")
    observed_topics = {item["name"]: item for item in result["observed_ros_graph"]["topics"]}

    for expected in scenario["expected_ros_graph"]["topics"]:
        observed = observed_topics[expected["name"]]
        assert observed["type"] == expected["type"]
        assert observed["publishers"] >= expected["min_publishers"]
        assert observed["subscribers"] >= expected["min_subscribers"]

    assert {item["assertion_id"] for item in result["assertion_results"]} == {
        item["assertion_id"] for item in scenario["assertions"]
    }
