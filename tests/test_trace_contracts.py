from __future__ import annotations

from copy import deepcopy

import pytest

from robotics_runtime_contracts import (
    ContractValidationError,
    SemanticValidationError,
    validate_document,
)

SHA = "a" * 64
TYPE_HASH = f"RIHS01_{'1' * 64}"


def zenoh_channel() -> dict[str, object]:
    return {
        "schema_version": "zenoh-channel.v1",
        "channel_id": "control.commands",
        "source": {
            "domain_id": "control",
            "ros_domain_id": 10,
            "topic": "/commands",
            "message_type": "example_interfaces/msg/String",
            "type_hash": TYPE_HASH,
        },
        "destination": {
            "domain_id": "worker",
            "ros_domain_id": 20,
            "topic": "/commands",
            "message_type": "example_interfaces/msg/String",
            "type_hash": TYPE_HASH,
        },
        "bridge": {
            "implementation": "zenoh-bridge-ros2dds",
            "version": "1.9.0",
            "configuration_sha256": "2" * 64,
            "dds_discovery_scope": "local_domain_only",
            "zenoh_key_expression": "robotics/control/commands",
        },
        "qos": {
            "reliability": "reliable",
            "durability": "volatile",
            "history": "keep_last",
            "depth": 10,
            "liveliness": "automatic",
            "liveliness_lease_duration_ms": "infinite",
            "deadline_ms": 100,
            "lifespan_ms": 500,
        },
        "delivery": {
            "observation_window_sec": 30,
            "minimum_source_messages": 20,
            "message_id_attribute": "messaging.message.id",
            "max_loss_ratio": 0,
            "max_duplicate_count": 0,
            "max_out_of_order_count": 0,
            "max_message_age_ms": 100,
        },
        "trace": {
            "carrier_field": "trace_context",
            "relationship": "link",
            "producer_span_name": "commands publish",
            "consumer_span_name": "commands receive",
        },
    }


def channel_observation() -> dict[str, object]:
    return {
        "schema_version": "zenoh-channel-observation.v1",
        "observation_id": "observation-00000000-0000-4000-8000-000000000001",
        "run_id": "run-00000000-0000-4000-8000-000000000001",
        "channel_id": "control.commands",
        "channel_contract_sha256": "f" * 64,
        "started_at": "2026-07-26T12:00:00Z",
        "finished_at": "2026-07-26T12:00:30Z",
        "sent_count": 20,
        "received_count": 20,
        "lost_count": 0,
        "duplicate_count": 0,
        "out_of_order_count": 0,
        "loss_ratio": 0,
        "max_message_age_ms": 10,
        "status": "passed",
        "violations": [],
    }


def causal_chain() -> dict[str, object]:
    return {
        "schema_version": "causal-chain.v1",
        "chain_id": "control-to-worker",
        "required_domain_ids": ["control", "worker"],
        "channel_contracts": [
            {
                "channel_id": "control.commands",
                "sha256": "f" * 64,
            }
        ],
        "require_connected_trace_graph": True,
        "missing_evidence_status": "incomplete",
        "broken_relationship_status": "failed",
    }


def transport_qualification() -> dict[str, object]:
    trace_id = "1" * 32
    message_id = "message-1"
    return {
        "schema_version": "transport-qualification-result.v1",
        "qualification_id": "qualification-00000000-0000-4000-8000-000000000001",
        "run_id": "run-00000000-0000-4000-8000-000000000001",
        "generated_at": "2026-07-26T12:00:00Z",
        "evaluator": {
            "implementation": "robotics-acceptance-harness",
            "version": "0.1.0",
        },
        "trace_evidence": [
            {
                "domain_id": domain_id,
                "evidence_index_sha256": digest * 64,
                "segment_index": 3,
                "uri": f"file:///evidence/{domain_id}.otlp.jsonl",
                "media_type": "application/x-ndjson",
                "format": "otlp-jsonl",
                "signal": "traces",
                "sha256": trace_digest * 64,
                "size_bytes": 100,
            }
            for domain_id, digest, trace_digest in (
                ("control", "d", "6"),
                ("worker", "e", "7"),
            )
        ],
        "causal_chain_contracts": [
            {
                "chain_id": "control-to-worker",
                "sha256": "8" * 64,
            }
        ],
        "channel_contracts": [
            {
                "channel_id": "control.commands",
                "source_domain_id": "control",
                "destination_domain_id": "worker",
                "sha256": "f" * 64,
            }
        ],
        "channel_observations": [
            {
                "channel_id": "control.commands",
                "observation_id": "observation-00000000-0000-4000-8000-000000000001",
                "sha256": "5" * 64,
                "status": "passed",
            }
        ],
        "causal_chains": [
            {
                "chain_id": "control-to-worker",
                "expected_contract_sha256": "8" * 64,
                "root_trace_id": trace_id,
                "trace_ids": [trace_id],
                "channel_ids": ["control.commands"],
                "status": "passed",
                "hops": [
                    {
                        "channel_id": "control.commands",
                        "relationship": "link",
                        "producer": {
                            "domain_id": "control",
                            "trace_id": trace_id,
                            "span_id": "2" * 16,
                            "message_id": message_id,
                        },
                        "consumer": {
                            "domain_id": "worker",
                            "trace_id": trace_id,
                            "span_id": "3" * 16,
                            "message_id": message_id,
                        },
                        "status": "passed",
                        "violations": [],
                    }
                ],
                "violations": [],
            }
        ],
        "verdict": {
            "status": "passed",
            "evaluated_at": "2026-07-26T12:01:00Z",
            "chain_count": 1,
            "passed_chain_count": 1,
            "failed_chain_count": 0,
            "incomplete_chain_count": 0,
            "error_chain_count": 0,
        },
    }


def acceptance_aggregate() -> dict[str, object]:
    return {
        "schema_version": "acceptance-aggregate.v4",
        "aggregate_id": "aggregate-00000000-0000-4000-8000-000000000001",
        "run_id": "run-00000000-0000-4000-8000-000000000001",
        "acceptance_run_sha256": SHA,
        "generated_at": "2026-07-26T12:02:00Z",
        "per_domain_results": [
            {
                "domain_id": "control",
                "result_id": "result-00000000-0000-4000-8000-000000000001",
                "result_sha256": "b" * 64,
                "status": "passed",
            },
            {
                "domain_id": "worker",
                "result_id": "result-00000000-0000-4000-8000-000000000002",
                "result_sha256": "c" * 64,
                "status": "passed",
            },
        ],
        "per_domain_aggregate": "passed",
        "cross_domain_e2e": {
            "status": "passed",
            "transport_qualification": {
                "qualification_id": "qualification-00000000-0000-4000-8000-000000000001",
                "result_sha256": "9" * 64,
                "status": "passed",
            },
        },
    }


def qualification_bundle() -> dict[str, object]:
    artifact_kinds = (
        "scenario",
        "runtime_manifest",
        "acceptance_run",
        "domain_result",
        "acceptance_aggregate",
        "transport_qualification",
        "evidence_index",
        "mcap_summary",
    )
    subjects = [
        {
            "name": f"artifacts/{kind}.json",
            "digest": {"sha256": f"{index:x}" * 64},
        }
        for index, kind in enumerate(artifact_kinds, start=1)
    ]
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": subjects,
        "predicateType": (
            "https://robotics-runtime-contracts.dev/attestations/qualification-bundle/v2"
        ),
        "predicate": {
            "schema_version": "qualification-bundle.v2",
            "run_id": "run-00000000-0000-4000-8000-000000000001",
            "generated_at": "2026-07-26T12:00:00Z",
            "artifacts": [
                {
                    "kind": kind,
                    "subject_name": f"artifacts/{kind}.json",
                }
                for kind in artifact_kinds
            ],
        },
    }


def qualification_policy() -> dict[str, object]:
    return {
        "schema_version": "qualification-policy.v2",
        "policy_id": "github-release-main",
        "predicate_type": (
            "https://robotics-runtime-contracts.dev/attestations/qualification-bundle/v2"
        ),
        "certificate_identities": [
            (
                "https://github.com/example/robotics/.github/workflows/"
                "qualification.yml@refs/heads/main"
            )
        ],
        "certificate_oidc_issuer": "https://token.actions.githubusercontent.com",
        "trusted_root_sha256": "a" * 64,
        "required_artifact_kinds": [
            "scenario",
            "runtime_manifest",
            "acceptance_run",
            "domain_result",
            "acceptance_aggregate",
            "evidence_index",
            "mcap_summary",
        ],
    }


def test_zenoh_channel_contract_is_valid() -> None:
    validate_document(zenoh_channel())


def test_zenoh_channel_rejects_same_source_and_destination() -> None:
    document = zenoh_channel()
    destination = document["destination"]
    assert isinstance(destination, dict)
    destination["domain_id"] = "control"

    with pytest.raises(SemanticValidationError, match="must differ from source.domain_id"):
        validate_document(document)


def test_zenoh_channel_rejects_type_hash_mismatch() -> None:
    document = zenoh_channel()
    destination = document["destination"]
    assert isinstance(destination, dict)
    destination["type_hash"] = f"RIHS01_{'2' * 64}"

    with pytest.raises(SemanticValidationError, match="must equal source.type_hash"):
        validate_document(document)


def test_zenoh_keep_all_rejects_depth() -> None:
    document = zenoh_channel()
    qos = document["qos"]
    assert isinstance(qos, dict)
    qos["history"] = "keep_all"

    with pytest.raises(ContractValidationError):
        validate_document(document)


def test_channel_observation_is_valid() -> None:
    validate_document(channel_observation())


def test_channel_observation_rejects_incorrect_loss_ratio() -> None:
    document = channel_observation()
    document["sent_count"] = 20
    document["received_count"] = 19
    document["lost_count"] = 1

    with pytest.raises(SemanticValidationError, match="lost_count / sent_count"):
        validate_document(document)


def test_channel_observation_rejects_unbalanced_counters() -> None:
    document = channel_observation()
    document["received_count"] = 0

    with pytest.raises(
        SemanticValidationError,
        match="sent_count - lost_count \\+ duplicate_count",
    ):
        validate_document(document)


def test_channel_observation_rejects_empty_pass() -> None:
    document = channel_observation()
    document.update(
        sent_count=0,
        received_count=0,
        lost_count=0,
        duplicate_count=0,
    )

    with pytest.raises(SemanticValidationError, match="at least one source message"):
        validate_document(document)


def test_channel_observation_rejects_impossible_reordering_count() -> None:
    document = channel_observation()
    document["out_of_order_count"] = 21

    with pytest.raises(SemanticValidationError, match="matched messages"):
        validate_document(document)


@pytest.mark.parametrize(
    "code",
    ["observation_window_exceeded", "ambiguous_message_id"],
)
def test_channel_observation_accepts_emitted_error_codes(code: str) -> None:
    document = channel_observation()
    document["status"] = "error"
    document["violations"] = [{"code": code, "message": "measured violation"}]

    validate_document(document)


def test_causal_chain_contract_is_valid() -> None:
    validate_document(causal_chain())


def test_causal_chain_rejects_duplicate_channel() -> None:
    document = causal_chain()
    contracts = document["channel_contracts"]
    assert isinstance(contracts, list)
    contracts.append(deepcopy(contracts[0]))

    with pytest.raises(SemanticValidationError, match="channel_id values must be unique"):
        validate_document(document)


def test_cross_domain_aggregate_is_valid() -> None:
    validate_document(acceptance_aggregate())


def test_cross_domain_aggregate_rejects_incorrect_domain_status() -> None:
    document = acceptance_aggregate()
    document["per_domain_results"][0]["status"] = "failed"

    with pytest.raises(SemanticValidationError, match="aggregate domain status"):
        validate_document(document)


def test_cross_domain_aggregate_rejects_incorrect_combined_status() -> None:
    document = acceptance_aggregate()
    document["cross_domain_e2e"]["transport_qualification"]["status"] = "failed"

    with pytest.raises(SemanticValidationError, match="combined domain and transport status"):
        validate_document(document)


def test_transport_qualification_requires_trace_for_every_domain() -> None:
    document = transport_qualification()
    document["trace_evidence"] = document["trace_evidence"][:1]

    with pytest.raises(ContractValidationError):
        validate_document(document)


def test_transport_qualification_rejects_uncovered_channel() -> None:
    document = transport_qualification()
    contracts = document["channel_contracts"]
    assert isinstance(contracts, list)
    contracts.append(
        {
            "channel_id": "worker.feedback",
            "source_domain_id": "worker",
            "destination_domain_id": "control",
            "sha256": "4" * 64,
        }
    )
    observations = document["channel_observations"]
    assert isinstance(observations, list)
    observations.append(
        {
            "channel_id": "worker.feedback",
            "observation_id": "observation-00000000-0000-4000-8000-000000000002",
            "sha256": "3" * 64,
            "status": "passed",
        }
    )

    with pytest.raises(SemanticValidationError, match="collectively cover"):
        validate_document(document)


def test_transport_qualification_rejects_cross_trace_parent_relationship() -> None:
    document = deepcopy(transport_qualification())
    hop = document["causal_chains"][0]["hops"][0]
    hop["relationship"] = "parent"
    hop["consumer"]["trace_id"] = "2" * 32
    document["causal_chains"][0]["trace_ids"] = ["1" * 32, "2" * 32]

    with pytest.raises(SemanticValidationError, match="share trace_id"):
        validate_document(document)


def test_transport_qualification_rejects_unknown_hop_domain() -> None:
    document = deepcopy(transport_qualification())
    document["causal_chains"][0]["hops"][0]["producer"]["domain_id"] = "ghost-control"

    with pytest.raises(SemanticValidationError, match="unknown qualification domains"):
        validate_document(document)


def test_transport_qualification_rejects_same_domain_hop() -> None:
    document = deepcopy(transport_qualification())
    document["causal_chains"][0]["hops"][0]["consumer"]["domain_id"] = "control"

    with pytest.raises(SemanticValidationError, match="distinct producer and consumer"):
        validate_document(document)


def test_transport_qualification_rejects_one_span_as_both_endpoints() -> None:
    document = deepcopy(transport_qualification())
    producer = document["causal_chains"][0]["hops"][0]["producer"]
    consumer = document["causal_chains"][0]["hops"][0]["consumer"]
    consumer["trace_id"] = producer["trace_id"]
    consumer["span_id"] = producer["span_id"]

    with pytest.raises(SemanticValidationError, match="distinct spans"):
        validate_document(document)


def test_transport_qualification_rejects_transition_reused_for_another_channel() -> None:
    document = deepcopy(transport_qualification())
    document["channel_contracts"].append(
        {
            "channel_id": "control.retry",
            "source_domain_id": "worker",
            "destination_domain_id": "control",
            "sha256": "4" * 64,
        }
    )
    document["channel_observations"].append(
        {
            "channel_id": "control.retry",
            "observation_id": "observation-00000000-0000-4000-8000-000000000002",
            "sha256": "3" * 64,
            "status": "passed",
        }
    )
    duplicate_hop = deepcopy(document["causal_chains"][0]["hops"][0])
    duplicate_hop["channel_id"] = "control.retry"
    duplicate_hop["producer"]["domain_id"] = "worker"
    duplicate_hop["consumer"]["domain_id"] = "control"
    document["causal_chains"][0]["channel_ids"].append("control.retry")
    document["causal_chains"][0]["hops"].append(duplicate_hop)

    with pytest.raises(SemanticValidationError, match="transition is duplicated"):
        validate_document(document)


def test_transport_qualification_rejects_disconnected_channel_sequence() -> None:
    document = deepcopy(transport_qualification())
    document["trace_evidence"].extend(
        [
            {
                "domain_id": "isolated-source",
                "evidence_index_sha256": "3" * 64,
                "segment_index": 3,
                "uri": "file:///evidence/isolated-source.otlp.jsonl",
                "media_type": "application/x-ndjson",
                "format": "otlp-jsonl",
                "signal": "traces",
                "sha256": "4" * 64,
                "size_bytes": 100,
            },
            {
                "domain_id": "isolated-target",
                "evidence_index_sha256": "5" * 64,
                "segment_index": 3,
                "uri": "file:///evidence/isolated-target.otlp.jsonl",
                "media_type": "application/x-ndjson",
                "format": "otlp-jsonl",
                "signal": "traces",
                "sha256": "6" * 64,
                "size_bytes": 100,
            },
        ]
    )
    document["channel_contracts"].append(
        {
            "channel_id": "isolated.commands",
            "source_domain_id": "isolated-source",
            "destination_domain_id": "isolated-target",
            "sha256": "7" * 64,
        }
    )
    document["channel_observations"].append(
        {
            "channel_id": "isolated.commands",
            "observation_id": "observation-00000000-0000-4000-8000-000000000002",
            "sha256": "8" * 64,
            "status": "passed",
        }
    )
    second_hop = deepcopy(document["causal_chains"][0]["hops"][0])
    second_hop["channel_id"] = "isolated.commands"
    second_hop["producer"]["domain_id"] = "isolated-source"
    second_hop["producer"]["span_id"] = "4" * 16
    second_hop["consumer"]["domain_id"] = "isolated-target"
    second_hop["consumer"]["span_id"] = "5" * 16
    document["causal_chains"][0]["channel_ids"].append("isolated.commands")
    document["causal_chains"][0]["hops"].append(second_hop)

    with pytest.raises(SemanticValidationError, match="preceding channel destination"):
        validate_document(document)


def test_transport_qualification_accepts_branching_chains() -> None:
    document = deepcopy(transport_qualification())
    document["trace_evidence"].append(
        {
            "domain_id": "observer",
            "evidence_index_sha256": "2" * 64,
            "segment_index": 3,
            "uri": "file:///evidence/observer.otlp.jsonl",
            "media_type": "application/x-ndjson",
            "format": "otlp-jsonl",
            "signal": "traces",
            "sha256": "3" * 64,
            "size_bytes": 100,
        }
    )
    document["causal_chain_contracts"].append(
        {
            "chain_id": "control-to-observer",
            "sha256": "4" * 64,
        }
    )
    document["channel_contracts"].append(
        {
            "channel_id": "control.observations",
            "source_domain_id": "control",
            "destination_domain_id": "observer",
            "sha256": "5" * 64,
        }
    )
    document["channel_observations"].append(
        {
            "channel_id": "control.observations",
            "observation_id": "observation-00000000-0000-4000-8000-000000000002",
            "sha256": "6" * 64,
            "status": "passed",
        }
    )
    second_chain = deepcopy(document["causal_chains"][0])
    second_chain["chain_id"] = "control-to-observer"
    second_chain["expected_contract_sha256"] = "4" * 64
    second_chain["channel_ids"] = ["control.observations"]
    second_chain["hops"][0]["channel_id"] = "control.observations"
    second_chain["hops"][0]["consumer"]["domain_id"] = "observer"
    second_chain["hops"][0]["consumer"]["span_id"] = "4" * 16
    document["causal_chains"].append(second_chain)
    document["verdict"].update(
        chain_count=2,
        passed_chain_count=2,
    )

    validate_document(document)


def test_transport_passed_rejects_failed_chain() -> None:
    document = deepcopy(transport_qualification())
    chains = document["causal_chains"]
    assert isinstance(chains, list)
    chains[0]["status"] = "failed"
    chains[0]["violations"] = [
        {
            "code": "relationship_mismatch",
            "channel_id": "control.commands",
            "message": "producer relationship differs",
        }
    ]
    verdict = document["verdict"]
    assert isinstance(verdict, dict)
    verdict["passed_chain_count"] = 0
    verdict["failed_chain_count"] = 1

    with pytest.raises(SemanticValidationError, match="aggregate transport status"):
        validate_document(document)


def test_transport_qualification_is_domain_neutral_and_valid() -> None:
    document = transport_qualification()

    validate_document(document)

    assert "per_domain_results" not in document
    assert "acceptance_run_sha256" not in document
    assert "runtime_manifest_sha256" not in document


def test_transport_qualification_requires_trace_for_every_channel_domain() -> None:
    document = transport_qualification()
    document["trace_evidence"][1]["domain_id"] = "observer"

    with pytest.raises(SemanticValidationError, match="qualification domain"):
        validate_document(document)


def test_transport_qualification_rejects_incorrect_verdict() -> None:
    document = transport_qualification()
    document["causal_chains"][0]["status"] = "failed"
    document["causal_chains"][0]["hops"] = []
    document["causal_chains"][0]["violations"] = [
        {
            "code": "relationship_mismatch",
            "channel_id": "control.commands",
            "message": "producer relationship differs",
        }
    ]
    document["verdict"].update(
        passed_chain_count=0,
        failed_chain_count=1,
    )

    with pytest.raises(SemanticValidationError, match="aggregate transport status"):
        validate_document(document)


def test_transport_qualification_rejects_domain_acceptance_fields() -> None:
    document = transport_qualification()
    document["per_domain_aggregate"] = "passed"

    with pytest.raises(ContractValidationError):
        validate_document(document)


def test_qualification_bundle_is_an_in_toto_statement() -> None:
    validate_document(qualification_bundle(), schema="qualification-bundle.v2")


def test_qualification_bundle_rejects_embedded_trust_policy() -> None:
    document = qualification_bundle()
    predicate = document["predicate"]
    assert isinstance(predicate, dict)
    predicate["trust_policy"] = {"certificate_identity": "self-authorized"}

    with pytest.raises(ContractValidationError):
        validate_document(document, schema="qualification-bundle.v2")


def test_qualification_policy_is_independent_and_valid() -> None:
    validate_document(qualification_policy())


def test_qualification_bundle_classifies_every_subject() -> None:
    document = qualification_bundle()
    subjects = document["subject"]
    assert isinstance(subjects, list)
    subjects[-1]["name"] = "artifacts/unclassified.json"

    with pytest.raises(SemanticValidationError, match="classify every statement subject"):
        validate_document(document, schema="qualification-bundle.v2")
