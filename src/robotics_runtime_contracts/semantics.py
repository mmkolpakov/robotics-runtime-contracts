from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any, NoReturn

from robotics_runtime_contracts.qualification_policy import (
    RESERVED_ASSERTION_IDS,
    RESERVED_METRIC_NAMES,
    channel_observation_status,
)
from robotics_runtime_contracts.status import worst_status


class SemanticValidationError(ValueError):
    """Raised when structurally valid contract fields contradict each other."""

    error_id = "semantic.validation_failed"

    def __init__(self, schema_name: str, json_path: str, message: str) -> None:
        self.schema_name = schema_name
        self.json_path = json_path
        self.validation_message = message
        super().__init__(f"{json_path}: {message}")


def _fail(schema_name: str, path: str, message: str) -> NoReturn:
    raise SemanticValidationError(schema_name, path, message)


def _timestamp(schema_name: str, path: str, value: str) -> datetime:
    try:
        normalized = f"{value[:-1]}+00:00" if value.endswith(("Z", "z")) else value
        return datetime.fromisoformat(normalized)
    except (TypeError, ValueError) as error:
        _fail(schema_name, path, f"must be a valid date-time: {error}")


def _require_unique(
    schema_name: str,
    items: Sequence[Mapping[str, Any]],
    key: str,
    path: str,
) -> None:
    values = [item[key] for item in items]
    if len(values) != len(set(values)):
        _fail(schema_name, path, f"{key} values must be unique")


def _validate_acceptance_scenario(document: Mapping[str, Any]) -> None:
    schema_name = document["schema_version"]
    timeouts = document["timeouts"]
    if timeouts["stable_for_sec"] > timeouts["graph_ready_sec"]:
        _fail(
            schema_name,
            "$.timeouts.stable_for_sec",
            "must not exceed graph_ready_sec",
        )

    graph = document["expected_ros_graph"]
    for key in ("topics", "services", "actions", "lifecycle_nodes"):
        _require_unique(schema_name, graph[key], "name", f"$.expected_ros_graph.{key}")

    assertions = document["assertions"]
    _require_unique(schema_name, assertions, "assertion_id", "$.assertions")
    _require_unique(
        schema_name,
        document["evaluator_requirements"],
        "namespace",
        "$.evaluator_requirements",
    )
    for index, assertion in enumerate(assertions):
        if assertion["assertion_id"] in RESERVED_ASSERTION_IDS:
            _fail(
                schema_name,
                f"$.assertions[{index}].assertion_id",
                "is reserved for a runtime qualification assertion",
            )

    if schema_name == "acceptance-scenario.v1":
        definitions = document["metric_definitions"]
        _require_unique(schema_name, definitions, "metric_name", "$.metric_definitions")
        definition_by_name = {item["metric_name"]: item for item in definitions}
        for index, definition in enumerate(definitions):
            metric_name = definition["metric_name"]
            if metric_name.startswith("robotics.") and metric_name not in RESERVED_METRIC_NAMES:
                _fail(
                    schema_name,
                    f"$.metric_definitions[{index}].metric_name",
                    "uses the reserved robotics.* namespace",
                )
            if not metric_name.startswith("robotics.") and metric_name.count(".") < 2:
                _fail(
                    schema_name,
                    f"$.metric_definitions[{index}].metric_name",
                    "product metrics require a reverse-domain namespace",
                )
            kind = definition["instrument_kind"]
            temporality = definition["temporality"]
            if kind == "gauge" and temporality != "instantaneous":
                _fail(
                    schema_name,
                    f"$.metric_definitions[{index}].temporality",
                    "gauge instruments require instantaneous temporality",
                )
            if kind != "gauge" and temporality == "instantaneous":
                _fail(
                    schema_name,
                    f"$.metric_definitions[{index}].temporality",
                    "sum and histogram instruments require OTLP aggregation temporality",
                )
            if definition.get("monotonic", False) and kind != "sum":
                _fail(
                    schema_name,
                    f"$.metric_definitions[{index}].monotonic",
                    "only sum instruments can be monotonic",
                )
        for index, assertion in enumerate(assertions):
            definition = definition_by_name.get(assertion["metric_name"])
            if definition is None:
                _fail(
                    schema_name,
                    f"$.assertions[{index}].metric_name",
                    "has no metric_definitions entry",
                )
            if assertion["unit"] != definition["unit"]:
                _fail(
                    schema_name,
                    f"$.assertions[{index}].unit",
                    "must match the declared metric unit",
                )
            if assertion["kind"] == "metric_duration":
                if definition["instrument_kind"] != "gauge":
                    _fail(
                        schema_name,
                        f"$.assertions[{index}].metric_name",
                        "duration predicates require a gauge instrument",
                    )
                duration = assertion["duration_requirement"]["duration_sec"]
                if duration > assertion["window_sec"]:
                    _fail(
                        schema_name,
                        f"$.assertions[{index}].duration_requirement.duration_sec",
                        "must not exceed window_sec",
                    )
                if assertion["max_sample_gap_sec"] > assertion["window_sec"]:
                    _fail(
                        schema_name,
                        f"$.assertions[{index}].max_sample_gap_sec",
                        "must not exceed window_sec",
                    )

    evidence = document["evidence_policy"]
    if evidence["max_segment_size_bytes"] > evidence["max_spool_size_bytes"]:
        _fail(
            schema_name,
            "$.evidence_policy.max_segment_size_bytes",
            "must not exceed max_spool_size_bytes",
        )
    remote_upload = evidence["upload_mode"] == "closed_segments_during_run"
    if remote_upload != evidence["remote_sink_allowed"]:
        _fail(
            schema_name,
            "$.evidence_policy.remote_sink_allowed",
            "must match whether upload_mode uses a remote sink",
        )

    forbidden = document["forbidden_ros_graph"]
    physical = document["execution"]["target_environment"] in {"hil", "real_robot"}
    if physical and not any(forbidden.values()):
        _fail(
            schema_name,
            "$.forbidden_ros_graph",
            "physical observation must declare at least one forbidden ROS interface",
        )

    time_policy = document["time_policy"]
    p50 = time_policy["max_time_authority_delivery_latency_p50_ms"]
    p95 = time_policy["max_time_authority_delivery_latency_p95_ms"]
    maximum = time_policy["max_time_authority_delivery_latency_ms"]
    if not p50 <= p95 <= maximum:
        _fail(
            schema_name,
            "$.time_policy",
            "time-authority delivery-latency thresholds must satisfy p50 <= p95 <= max",
        )


def _validate_model_artifact(document: Mapping[str, Any]) -> None:
    schema_name = "model-artifact-manifest.v1"
    source = document["source"]
    compatibility = document["compatibility"]
    numerical = document["numerical_conformance"]

    _require_unique(schema_name, source["inputs"], "name", "$.source.inputs")
    _require_unique(schema_name, source["outputs"], "name", "$.source.outputs")

    if numerical["reference_artifact_sha256"] != source["sha256"]:
        _fail(
            schema_name,
            "$.numerical_conformance.reference_artifact_sha256",
            "must identify the source ONNX artifact",
        )
    if compatibility["portable"] and compatibility["hardware"]:
        _fail(
            schema_name,
            "$.compatibility.hardware",
            "portable artifacts must not declare a hardware allow-list",
        )
    if not compatibility["portable"] and not compatibility["hardware"]:
        _fail(
            schema_name,
            "$.compatibility.hardware",
            "non-portable artifacts require a hardware allow-list",
        )


def _validate_dataset(document: Mapping[str, Any]) -> None:
    schema_name = "dataset-manifest.v1"
    channels = document["channels"]
    time = document["time"]

    _require_unique(schema_name, channels, "topic", "$.channels")
    if time["end_ns"] <= time["start_ns"]:
        _fail(schema_name, "$.time.end_ns", "must be greater than start_ns")
    for index, jump in enumerate(time["clock_jumps"]):
        if not time["start_ns"] <= jump["at_ns"] <= time["end_ns"]:
            _fail(
                schema_name,
                f"$.time.clock_jumps[{index}].at_ns",
                "must fall within the recorded interval",
            )

    channel_names = {item["topic"] for item in channels}
    remap_sources: set[str] = set()
    remap_targets: set[str] = set()
    for index, remap in enumerate(document["topic_remaps"]):
        if remap["from"] not in channel_names:
            _fail(
                schema_name,
                f"$.topic_remaps[{index}].from",
                "must identify a recorded channel",
            )
        if remap["from"] in remap_sources or remap["to"] in remap_targets:
            _fail(schema_name, "$.topic_remaps", "remaps must be one-to-one")
        remap_sources.add(remap["from"])
        remap_targets.add(remap["to"])


def _validate_runtime(document: Mapping[str, Any]) -> None:
    schema_name = document["schema_version"]
    workload = document["workload"]
    inference = workload.get("inference")
    execution = document["execution"]
    data_plane = document["data_plane"]
    security = document["security"]
    clock = document["clock"]

    if inference is not None:
        if inference["requested_provider"] != inference["actual_provider"]:
            _fail(
                schema_name,
                "$.workload.inference.actual_provider",
                "must equal requested_provider; silent fallback is forbidden",
            )
        if inference["fallback_count"] != 0:
            _fail(schema_name, "$.workload.inference.fallback_count", "must be zero")
    if document["ros"]["rmw_implementation"] != data_plane["rmw_implementation"]:
        _fail(
            schema_name,
            "$.data_plane.rmw_implementation",
            "must match the observed ROS RMW implementation",
        )

    source_modes = {
        "simulator": (
            "simulation",
            "simulated_physics",
            {"simulation_realtime", "simulation_stepped"},
        ),
        "recording_playback": ("simulation", "recorded_data", {"playback_clocked"}),
        "live_target": ({"hil", "real_robot"}, "real_hardware", {"hardware_realtime"}),
    }
    source_mode = source_modes.get(execution["data_source"])
    if source_mode is None:
        _fail(schema_name, "$.execution.data_source", "has no semantic execution mapping")
    target, plant, time_modes = source_mode
    allowed_targets = target if isinstance(target, set) else {target}
    if execution["target_environment"] not in allowed_targets:
        _fail(schema_name, "$.execution.target_environment", "contradicts data_source")
    if execution["plant_backend"] != plant:
        _fail(schema_name, "$.execution.plant_backend", "contradicts data_source")
    if execution["time_mode"] not in time_modes:
        _fail(schema_name, "$.execution.time_mode", "contradicts data_source")

    if security["profile"] == "none":
        if security["strategy"] != "none" or security["enclaves"] or security["policy_digests"]:
            _fail(schema_name, "$.security", "unsecured runtime must not claim SROS2 assets")
    elif (
        security["strategy"] != "Enforce"
        or not security["enclaves"]
        or not security["policy_digests"]
    ):
        _fail(
            schema_name,
            "$.security",
            "sros2_enforce requires Enforce, enclaves, and policy digests",
        )

    targets = document["physical_targets"]
    _require_unique(schema_name, targets, "target_id", "$.physical_targets")
    _require_unique(schema_name, targets, "identity_sha256", "$.physical_targets")
    _require_unique(
        schema_name,
        document.get("configuration_artifacts", []),
        "kind",
        "$.configuration_artifacts",
    )
    _require_unique(
        schema_name,
        document["evaluator_bindings"],
        "namespace",
        "$.evaluator_bindings",
    )
    if schema_name == "runtime-manifest.v1":
        registered = {"inference_provider", "host_topology", "runtime_resources"}
        for index, artifact in enumerate(document.get("configuration_artifacts", [])):
            kind = artifact["kind"]
            if kind not in registered and kind.count(".") < 2:
                _fail(
                    schema_name,
                    f"$.configuration_artifacts[{index}].kind",
                    "unregistered kinds require a reverse-domain namespace",
                )

    expected_clock = {
        "simulation_realtime": "sim_clock",
        "simulation_stepped": "sim_clock",
        "playback_clocked": "playback_clock",
    }.get(execution["time_mode"])
    if expected_clock is not None and clock["sync_protocol"] != expected_clock:
        _fail(schema_name, "$.clock.sync_protocol", "contradicts time_mode")

    if document["render"]["mode"] == "egl" and any(
        marker in document["render"]["renderer"].lower() for marker in ("llvmpipe", "softpipe")
    ):
        _fail(schema_name, "$.render.renderer", "EGL mode must use a hardware renderer")


def _validate_permit(document: Mapping[str, Any]) -> None:
    schema_name = document["schema_version"]
    issued_at = _timestamp(schema_name, "$.issued_at", document["issued_at"])
    expires_at = _timestamp(schema_name, "$.expires_at", document["expires_at"])
    checked_at = _timestamp(
        schema_name,
        "$.interlock_check.checked_at",
        document["interlock_check"]["checked_at"],
    )

    if expires_at <= issued_at:
        _fail(schema_name, "$.expires_at", "must be later than issued_at")
    if checked_at > issued_at:
        _fail(schema_name, "$.interlock_check.checked_at", "must not be later than issued_at")
    if document["operator_id"] == document["approver_id"]:
        _fail(schema_name, "$.approver_id", "must differ from operator_id")
    if (expires_at - issued_at).total_seconds() > 1800:
        _fail(schema_name, "$.expires_at", "must be no more than 30 minutes after issued_at")


def _validate_execution_verification(document: Mapping[str, Any]) -> None:
    schema_name = "execution-verification.v1"
    signers = document["signers"]
    roles = {signer["role"] for signer in signers}
    if roles != {"operator", "approver"}:
        _fail(schema_name, "$.signers", "must contain exactly one operator and one approver")
    _require_unique(schema_name, signers, "identity", "$.signers")
    _require_unique(schema_name, signers, "bundle_sha256", "$.signers")


def _validate_result(document: Mapping[str, Any]) -> None:
    schema_name = document["schema_version"]
    started_at = _timestamp(schema_name, "$.started_at", document["started_at"])
    finished_at = _timestamp(schema_name, "$.finished_at", document["finished_at"])
    if finished_at < started_at:
        _fail(schema_name, "$.finished_at", "must not be earlier than started_at")

    _require_unique(
        schema_name,
        document["assertion_results"],
        "assertion_id",
        "$.assertion_results",
    )
    _require_unique(schema_name, document["evaluators"], "namespace", "$.evaluators")
    assertion_results = document["assertion_results"]
    if (
        assertion_results
        and worst_status([document["status"], *(item["status"] for item in assertion_results)])
        != document["status"]
    ):
        _fail(
            schema_name,
            "$.status",
            "must not be less severe than an assertion result",
        )
    graph = document["observed_ros_graph"]
    for key in ("topics", "services", "actions"):
        _require_unique(schema_name, graph[key], "name", f"$.observed_ros_graph.{key}")
    lifecycle_keys = [
        (item["node"], item["observed_at_ns"]) for item in document["lifecycle_states"]
    ]
    if len(lifecycle_keys) != len(set(lifecycle_keys)):
        _fail(
            schema_name,
            "$.lifecycle_states",
            "node and observed_at_ns pairs must be unique",
        )
    evidence_digests = {item["sha256"] for item in document["evidence"]}
    if schema_name == "acceptance-result.v1":
        if (
            any(item["status"] == "skipped" for item in document["assertion_results"])
            and document["status"] == "passed"
        ):
            _fail(
                schema_name,
                "$.status",
                "skipped assertions require an incomplete or worse verdict",
            )
        if document["evaluation_mode"] == "offline":
            required_unevaluated = {
                "$.clock_observation",
                "$.forbidden_graph_observation",
                "$.observed_ros_graph",
                "$.shutdown",
            }
            missing_unevaluated = required_unevaluated - set(document["unevaluated"])
            if missing_unevaluated:
                _fail(
                    schema_name,
                    "$.unevaluated",
                    f"offline evaluation must declare {sorted(missing_unevaluated)}",
                )
            if document["status"] == "passed":
                _fail(
                    schema_name,
                    "$.status",
                    "offline evaluation cannot claim a complete passed verdict",
                )
        for index, assertion in enumerate(document["assertion_results"]):
            if assertion["source"] == "core":
                if "namespace" in assertion:
                    _fail(
                        schema_name,
                        f"$.assertion_results[{index}].namespace",
                        "core assertions must not claim a product namespace",
                    )
                continue
            namespace = assertion["namespace"]
            if not assertion["assertion_id"].startswith(f"{namespace}."):
                _fail(
                    schema_name,
                    f"$.assertion_results[{index}].assertion_id",
                    "product assertion_id must be owned by its namespace",
                )
            missing = set(assertion["evidence_sha256"]) - evidence_digests
            if missing:
                _fail(
                    schema_name,
                    f"$.assertion_results[{index}].evidence_sha256",
                    f"references evidence not listed in the result: {sorted(missing)}",
                )

    forbidden = document["forbidden_graph_observation"]
    violation_keys = [(item["kind"], item["name"]) for item in forbidden["violations"]]
    if len(violation_keys) != len(set(violation_keys)):
        _fail(
            schema_name,
            "$.forbidden_graph_observation.violations",
            "violations must be unique by kind and name",
        )
    if forbidden["passed"] != (not forbidden["violations"]):
        _fail(
            schema_name,
            "$.forbidden_graph_observation.passed",
            "must equal whether violations is empty",
        )

    target_environment = document["execution"]["target_environment"]
    if target_environment in {"hil", "real_robot"}:
        authorization = document["authorization"]
        if authorization["target"]["environment"] != target_environment:
            _fail(
                schema_name,
                "$.authorization.target.environment",
                "must match execution.target_environment",
            )
        clock = document["hardware_clock_observation"]
        expected_sources = {
            "ptp": {"pmc"},
            "chrony_ntp": {"chronyc_tracking"},
            "mavlink_timesync": {"mavlink_timesync_status"},
            "micro_xrce_dds": {"controller_telemetry"},
            "external": {"external_attestation"},
        }
        protocol_sources = expected_sources.get(clock["sync_protocol"])
        if protocol_sources is None:
            _fail(
                schema_name,
                "$.hardware_clock_observation.sync_protocol",
                "has no semantic source mapping",
            )
        if clock["source"] not in protocol_sources:
            _fail(
                schema_name,
                "$.hardware_clock_observation.source",
                "must match sync_protocol",
            )
        if clock["evidence_sha256"] not in evidence_digests:
            _fail(
                schema_name,
                "$.hardware_clock_observation.evidence_sha256",
                "must identify an item listed in evidence",
            )
        measured_at = _timestamp(
            schema_name,
            "$.hardware_clock_observation.measured_at",
            clock["measured_at"],
        )
        if not started_at <= measured_at <= finished_at:
            _fail(
                schema_name,
                "$.hardware_clock_observation.measured_at",
                "must fall within the observed interval",
            )

    if document["status"] == "passed":
        workload = document["workload"]
        if workload["kind"] == "inference" and workload["fallback_count"] != 0:
            _fail(
                schema_name,
                "$.workload.fallback_count",
                "passed result cannot include fallback",
            )
        if not document["clock_observation"]["monotonic"]:
            _fail(
                schema_name,
                "$.clock_observation.monotonic",
                "passed result requires monotonic time",
            )
        if not all(document["shutdown"].values()):
            _fail(
                schema_name,
                "$.shutdown",
                "passed result requires finalized evidence and shutdown",
            )
        if (
            document["execution"]["target_environment"] in {"hil", "real_robot"}
            and not (document["hardware_clock_observation"]["within_policy"])
        ):
            _fail(
                schema_name,
                "$.hardware_clock_observation.within_policy",
                "passed physical result requires hardware timing within policy",
            )
        if not document["time_authority_observation"]["within_policy"]:
            _fail(
                schema_name,
                "$.time_authority_observation.within_policy",
                "passed result requires time-authority evidence within policy",
            )

    observation = document["time_authority_observation"]
    if observation["window_end_ns"] < observation["window_start_ns"]:
        _fail(
            schema_name,
            "$.time_authority_observation.window_end_ns",
            "must not be earlier than window_start_ns",
        )
    p50 = observation["p50_delivery_latency_ms"]
    p95 = observation["p95_delivery_latency_ms"]
    maximum = observation["max_delivery_latency_ms"]
    if not p50 <= p95 <= maximum:
        _fail(
            schema_name,
            "$.time_authority_observation",
            "delivery-latency statistics must satisfy p50 <= p95 <= max",
        )
    evidence_sha256 = observation.get("evidence_sha256")
    if evidence_sha256 is not None and evidence_sha256 not in evidence_digests:
        _fail(
            schema_name,
            "$.time_authority_observation.evidence_sha256",
            "must identify an item listed in evidence",
        )

    segment_keys: set[tuple[str, int]] = set()
    for index, item in enumerate(document["evidence"]):
        if "segment_index" not in item:
            continue
        segment_key = (item["uri"], item["segment_index"])
        if segment_key in segment_keys:
            _fail(schema_name, f"$.evidence[{index}]", "duplicate evidence segment")
        segment_keys.add(segment_key)


def _validate_evidence_index(document: Mapping[str, Any]) -> None:
    schema_name = document["schema_version"]
    artifacts = document["artifacts"]
    _require_unique(schema_name, artifacts, "artifact_id", "$.artifacts")
    identities: set[tuple[str, str]] = set()
    for index, artifact in enumerate(artifacts):
        identity = (artifact["uri"], artifact.get("immutable_revision", ""))
        if identity in identities:
            _fail(schema_name, f"$.artifacts[{index}].uri", "evidence object is duplicated")
        identities.add(identity)


def _validate_acceptance_aggregate(document: Mapping[str, Any]) -> None:
    schema_name = document["schema_version"]
    results = document["per_domain_results"]
    _require_unique(schema_name, results, "domain_id", "$.per_domain_results")
    _require_unique(schema_name, results, "result_id", "$.per_domain_results")
    expected = worst_status(item["status"] for item in results)
    if document["per_domain_aggregate"] != expected:
        _fail(
            schema_name,
            "$.per_domain_aggregate",
            f"must equal the aggregate domain status {expected!r}",
        )
    cross_domain = document["cross_domain_e2e"]
    if cross_domain["status"] == "unevaluated":
        return
    qualification_status = cross_domain["transport_qualification"]["status"]
    expected_cross_domain = worst_status(
        (expected, qualification_status),
        collapse_cancelled=True,
    )
    if cross_domain["status"] != expected_cross_domain:
        _fail(
            schema_name,
            "$.cross_domain_e2e.status",
            f"must equal the combined domain and transport status {expected_cross_domain!r}",
        )


def _validate_transport_qualification(document: Mapping[str, Any]) -> None:
    schema_name = document["schema_version"]
    result_domains = {
        domain_id
        for item in document["channel_contracts"]
        for domain_id in (item["source_domain_id"], item["destination_domain_id"])
    }

    trace_evidence = document["trace_evidence"]
    _require_unique(schema_name, trace_evidence, "domain_id", "$.trace_evidence")
    if {item["domain_id"] for item in trace_evidence} != result_domains:
        _fail(
            schema_name,
            "$.trace_evidence",
            "must contain exactly one trace file for every qualification domain",
        )

    contracts = document["channel_contracts"]
    _require_unique(schema_name, contracts, "channel_id", "$.channel_contracts")
    contract_ids = {item["channel_id"] for item in contracts}
    contract_by_id = {item["channel_id"]: item for item in contracts}
    for contract_index, contract in enumerate(contracts):
        if contract["source_domain_id"] == contract["destination_domain_id"]:
            _fail(
                schema_name,
                f"$.channel_contracts[{contract_index}]",
                "cross-domain channel requires distinct source and destination domains",
            )
    clock_relations = document.get("clock_relations", [])
    _require_unique(schema_name, clock_relations, "relation_id", "$.clock_relations")
    relation_by_domains = {
        (item["source_domain_id"], item["destination_domain_id"]): item for item in clock_relations
    }
    if len(relation_by_domains) != len(clock_relations):
        _fail(
            schema_name,
            "$.clock_relations",
            "source and destination domain pairs must be unique",
        )
    expected_relations = {
        (item["source_domain_id"], item["destination_domain_id"]) for item in contracts
    }
    if not set(relation_by_domains) <= expected_relations:
        _fail(
            schema_name,
            "$.clock_relations",
            "contains a relation outside the channel domain pairs",
        )
    observations = document["channel_observations"]
    _require_unique(schema_name, observations, "channel_id", "$.channel_observations")
    if {item["channel_id"] for item in observations} != contract_ids:
        _fail(
            schema_name,
            "$.channel_observations",
            "must contain exactly one observation for every channel contract",
        )
    chains = document["causal_chains"]
    _require_unique(schema_name, chains, "chain_id", "$.causal_chains")
    chain_contracts = document["causal_chain_contracts"]
    _require_unique(
        schema_name,
        chain_contracts,
        "chain_id",
        "$.causal_chain_contracts",
    )
    chain_contract_by_id = {item["chain_id"]: item for item in chain_contracts}
    chain_ids = {item["chain_id"] for item in chains}
    if chain_ids != set(chain_contract_by_id):
        _fail(
            schema_name,
            "$.causal_chains",
            "must contain exactly one result for every causal chain contract",
        )
    covered_channel_ids: set[str] = set()
    for index, chain in enumerate(chains):
        unknown = set(chain["channel_ids"]) - contract_ids
        if unknown:
            _fail(
                schema_name,
                f"$.causal_chains[{index}].channel_ids",
                f"unknown channel contracts: {sorted(unknown)}",
            )
        covered_channel_ids.update(chain["channel_ids"])
        expected_contract = chain_contract_by_id[chain["chain_id"]]
        if chain["expected_contract_sha256"] != expected_contract["sha256"]:
            _fail(
                schema_name,
                f"$.causal_chains[{index}].expected_contract_sha256",
                "must match the referenced causal chain contract sha256",
            )
        for channel_index, channel_id in enumerate(chain["channel_ids"][1:], start=1):
            previous_id = chain["channel_ids"][channel_index - 1]
            previous = contract_by_id[previous_id]
            current = contract_by_id[channel_id]
            if previous["destination_domain_id"] != current["source_domain_id"]:
                _fail(
                    schema_name,
                    f"$.causal_chains[{index}].channel_ids[{channel_index}]",
                    "must continue from the preceding channel destination",
                )
        hop_ids = [hop["channel_id"] for hop in chain["hops"]]
        if len(hop_ids) != len(set(hop_ids)):
            _fail(
                schema_name,
                f"$.causal_chains[{index}].hops",
                "channel_id values must be unique",
            )
        if chain["status"] == "passed" and hop_ids != chain["channel_ids"]:
            _fail(
                schema_name,
                f"$.causal_chains[{index}].hops",
                "passed requires one ordered hop for every channel",
            )
        if any(hop["status"] != "passed" for hop in chain["hops"]) and chain["status"] == "passed":
            _fail(
                schema_name,
                f"$.causal_chains[{index}].status",
                "passed requires every observed hop to pass",
            )
        if chain["status"] == "passed":
            trace_ids = set(chain["trace_ids"])
            if chain["root_trace_id"] not in trace_ids:
                _fail(
                    schema_name,
                    f"$.causal_chains[{index}].root_trace_id",
                    "must be present in trace_ids",
                )
            observed_trace_ids = {
                reference["trace_id"]
                for hop in chain["hops"]
                for reference in (hop["producer"], hop["consumer"])
            }
            if observed_trace_ids != trace_ids:
                _fail(
                    schema_name,
                    f"$.causal_chains[{index}].trace_ids",
                    "must equal the trace IDs used by the verified hops",
                )
            transition_ids: set[tuple[tuple[str, str], tuple[str, str]]] = set()
            for hop_index, hop in enumerate(chain["hops"]):
                channel_contract = contract_by_id[hop["channel_id"]]
                referenced_domains = {
                    hop["producer"]["domain_id"],
                    hop["consumer"]["domain_id"],
                }
                unknown_domains = referenced_domains - result_domains
                if unknown_domains:
                    _fail(
                        schema_name,
                        f"$.causal_chains[{index}].hops[{hop_index}]",
                        f"references unknown qualification domains: {sorted(unknown_domains)}",
                    )
                if hop["producer"]["domain_id"] == hop["consumer"]["domain_id"]:
                    _fail(
                        schema_name,
                        f"$.causal_chains[{index}].hops[{hop_index}]",
                        "cross-domain hop requires distinct producer and consumer domains",
                    )
                if (
                    hop["producer"]["domain_id"] != channel_contract["source_domain_id"]
                    or hop["consumer"]["domain_id"] != channel_contract["destination_domain_id"]
                ):
                    _fail(
                        schema_name,
                        f"$.causal_chains[{index}].hops[{hop_index}]",
                        "observed domains must match the referenced channel direction",
                    )
                producer_span = (
                    hop["producer"]["trace_id"],
                    hop["producer"]["span_id"],
                )
                consumer_span = (
                    hop["consumer"]["trace_id"],
                    hop["consumer"]["span_id"],
                )
                transition_id = (producer_span, consumer_span)
                if transition_id in transition_ids:
                    _fail(
                        schema_name,
                        f"$.causal_chains[{index}].hops[{hop_index}]",
                        "observed span transition is duplicated across channels",
                    )
                transition_ids.add(transition_id)
                if producer_span == consumer_span:
                    _fail(
                        schema_name,
                        f"$.causal_chains[{index}].hops[{hop_index}]",
                        "producer and consumer must identify distinct spans",
                    )
                if hop["producer"]["message_id"] != hop["consumer"]["message_id"]:
                    _fail(
                        schema_name,
                        f"$.causal_chains[{index}].hops[{hop_index}]",
                        "producer and consumer message_id values must match",
                    )
                if (
                    hop["relationship"] == "parent"
                    and hop["producer"]["trace_id"] != hop["consumer"]["trace_id"]
                ):
                    _fail(
                        schema_name,
                        f"$.causal_chains[{index}].hops[{hop_index}]",
                        "parent relationship requires producer and consumer to share trace_id",
                    )
    if covered_channel_ids != contract_ids:
        _fail(
            schema_name,
            "$.causal_chains",
            "must collectively cover every channel contract",
        )

    verdict = document["verdict"]
    passed_chains = sum(chain["status"] == "passed" for chain in chains)
    failed_chains = sum(chain["status"] == "failed" for chain in chains)
    incomplete_chains = sum(chain["status"] == "incomplete" for chain in chains)
    error_chains = sum(chain["status"] == "error" for chain in chains)
    if verdict["chain_count"] != len(chains):
        _fail(
            schema_name,
            "$.verdict.chain_count",
            "must equal the number of causal chains",
        )
    if verdict["passed_chain_count"] != passed_chains:
        _fail(
            schema_name,
            "$.verdict.passed_chain_count",
            "must equal the number of passed causal chains",
        )
    if verdict["failed_chain_count"] != failed_chains:
        _fail(
            schema_name,
            "$.verdict.failed_chain_count",
            "must equal the number of failed causal chains",
        )
    if verdict["incomplete_chain_count"] != incomplete_chains:
        _fail(
            schema_name,
            "$.verdict.incomplete_chain_count",
            "must equal the number of incomplete causal chains",
        )
    if verdict["error_chain_count"] != error_chains:
        _fail(
            schema_name,
            "$.verdict.error_chain_count",
            "must equal the number of errored causal chains",
        )
    missing_clock_relations = set(relation_by_domains) != expected_relations
    expected_e2e = worst_status(
        (
            "passed",
            *(("incomplete",) if missing_clock_relations else ()),
            *(item["status"] for item in clock_relations),
            *(item["status"] for item in observations),
            *(item["status"] for item in chains),
        ),
        collapse_cancelled=True,
    )
    if verdict["status"] != expected_e2e:
        _fail(
            schema_name,
            "$.verdict.status",
            f"must equal the aggregate transport status {expected_e2e!r}",
        )


def _validate_clock_relation(document: Mapping[str, Any]) -> None:
    schema_name = "clock-relation.v1"
    if document["source_domain_id"] == document["destination_domain_id"]:
        _fail(
            schema_name,
            "$.destination_domain_id",
            "must differ from source_domain_id",
        )
    started = _timestamp(schema_name, "$.started_at", document["started_at"])
    finished = _timestamp(schema_name, "$.finished_at", document["finished_at"])
    if finished <= started:
        _fail(schema_name, "$.finished_at", "must be later than started_at")
    expected_violations: set[str] = set()
    if document["method"] == "measured_skew":
        policy = document["policy"]
        if document["sample_count"] < policy["minimum_samples"]:
            expected_violations.add("insufficient_samples")
        if document["max_absolute_skew_ms"] > policy["maximum_absolute_skew_ms"]:
            expected_violations.add("clock_skew_exceeded")
    reported = set(document["violations"])
    if "invalid_observation" in reported:
        expected_violations.add("invalid_observation")
    status_codes = {
        "insufficient_samples": "insufficient_messages",
        "clock_skew_exceeded": "clock_skew_exceeded",
        "invalid_observation": "invalid_observation",
    }
    expected_status = channel_observation_status(status_codes[code] for code in expected_violations)
    if reported != expected_violations or document["status"] != expected_status:
        _fail(schema_name, "$.status", "contradicts measured clock skew and violations")


def _validate_campaign_summary(document: Mapping[str, Any]) -> None:
    schema_name = "campaign-summary.v1"
    runs = document["runs"]
    _require_unique(schema_name, runs, "run_id", "$.runs")
    _require_unique(schema_name, runs, "acceptance_run_sha256", "$.runs")
    _require_unique(schema_name, runs, "aggregate_sha256", "$.runs")
    counts = {
        status: sum(item["status"] == status for item in runs)
        for status in ("passed", "failed", "incomplete", "error")
    }
    verdict = document["verdict"]
    for field, expected in (
        ("total_runs", len(runs)),
        ("passed_runs", counts["passed"]),
        ("failed_runs", counts["failed"]),
        ("incomplete_runs", counts["incomplete"]),
        ("error_runs", counts["error"]),
    ):
        if verdict[field] != expected:
            _fail(schema_name, f"$.verdict.{field}", f"must equal {expected}")
    acceptance = document["acceptance"]
    passed = (
        counts["passed"] >= acceptance["minimum_passed_runs"]
        and counts["failed"] <= acceptance["maximum_failed_runs"]
        and counts["incomplete"] <= acceptance["maximum_incomplete_runs"]
        and counts["error"] <= acceptance["maximum_error_runs"]
    )
    expected_status = "passed" if passed else worst_status(item["status"] for item in runs)
    if expected_status == "passed" and not passed:
        expected_status = "failed"
    if verdict["status"] != expected_status:
        _fail(
            schema_name,
            "$.verdict.status",
            f"must equal campaign policy verdict {expected_status!r}",
        )


def _validate_transport_channel(document: Mapping[str, Any]) -> None:
    schema_name = "transport-channel.v1"
    source = document["source"]
    destination = document["destination"]
    if source["domain_id"] == destination["domain_id"]:
        _fail(
            schema_name,
            "$.destination.domain_id",
            "must differ from source.domain_id",
        )
    if source["ros_domain_id"] == destination["ros_domain_id"]:
        _fail(
            schema_name,
            "$.destination.ros_domain_id",
            "must differ from source.ros_domain_id",
        )
    if source["message_type"] != destination["message_type"]:
        _fail(
            schema_name,
            "$.destination.message_type",
            "must equal source.message_type",
        )
    if source["type_hash"] != destination["type_hash"]:
        _fail(
            schema_name,
            "$.destination.type_hash",
            "must equal source.type_hash",
        )
    trace = document["trace"]
    if trace["producer_span_name"] == trace["consumer_span_name"]:
        _fail(
            schema_name,
            "$.trace.consumer_span_name",
            "must differ from producer_span_name",
        )


def _validate_transport_channel_observation(document: Mapping[str, Any]) -> None:
    schema_name = "transport-channel-observation.v1"
    started_at = _timestamp(schema_name, "$.started_at", document["started_at"])
    finished_at = _timestamp(schema_name, "$.finished_at", document["finished_at"])
    if finished_at <= started_at:
        _fail(schema_name, "$.finished_at", "must be later than started_at")
    sent = document["sent_count"]
    received = document["received_count"]
    lost = document["lost_count"]
    duplicates = document["duplicate_count"]
    if lost > sent:
        _fail(schema_name, "$.lost_count", "must not exceed sent_count")
    expected_received = sent - lost + duplicates
    if received != expected_received:
        _fail(
            schema_name,
            "$.received_count",
            "must equal sent_count - lost_count + duplicate_count",
        )
    matched_count = sent - lost
    if document["out_of_order_count"] > matched_count:
        _fail(
            schema_name,
            "$.out_of_order_count",
            "must not exceed the number of matched messages",
        )
    if document["status"] == "passed" and sent == 0:
        _fail(
            schema_name,
            "$.status",
            "passed observation requires at least one source message",
        )
    expected_ratio = lost / sent if sent else 0.0
    if abs(document["loss_ratio"] - expected_ratio) > 1e-12:
        _fail(
            schema_name,
            "$.loss_ratio",
            "must equal lost_count / sent_count",
        )


def _validate_causal_chain(document: Mapping[str, Any]) -> None:
    schema_name = "causal-chain.v1"
    contracts = document["channel_contracts"]
    _require_unique(schema_name, contracts, "channel_id", "$.channel_contracts")


def _validate_qualification_bundle(document: Mapping[str, Any]) -> None:
    schema_name = "qualification-bundle.v1"
    subjects = document["subject"]
    _require_unique(schema_name, subjects, "name", "$.subject")
    subject_names = {item["name"] for item in subjects}
    artifacts = document["predicate"]["artifacts"]
    _require_unique(schema_name, artifacts, "subject_name", "$.predicate.artifacts")
    artifact_names = {item["subject_name"] for item in artifacts}
    if artifact_names != subject_names:
        _fail(
            schema_name,
            "$.predicate.artifacts",
            "must classify every statement subject exactly once",
        )
    kinds = {item["kind"] for item in artifacts}
    required = {
        "scenario",
        "runtime_manifest",
        "acceptance_run",
        "domain_result",
        "acceptance_aggregate",
        "evidence_index",
    }
    missing = required - kinds
    if missing:
        _fail(
            schema_name,
            "$.predicate.artifacts",
            f"missing required artifact kinds: {sorted(missing)}",
        )


def _validate_recording_summary(document: Mapping[str, Any]) -> None:
    schema_name = "recording-summary.v1"
    channels = document["channels"]
    _require_unique(schema_name, channels, "topic", "$.channels")
    statistics = document["statistics"]
    if statistics["channel_count"] != len(channels):
        _fail(
            schema_name,
            "$.statistics.channel_count",
            "must equal the number of summarized channels",
        )
    if statistics["message_end_time_ns"] < statistics["message_start_time_ns"]:
        _fail(
            schema_name,
            "$.statistics.message_end_time_ns",
            "must not be earlier than message_start_time_ns",
        )


def _validate_acceptance_observation(document: Mapping[str, Any]) -> None:
    schema_name = "acceptance-observation.v1"
    started_at = _timestamp(schema_name, "$.started_at", document["started_at"])
    finished_at = _timestamp(schema_name, "$.finished_at", document["finished_at"])
    if finished_at <= started_at:
        _fail(schema_name, "$.finished_at", "must be later than started_at")


def _validate_conformance_result(document: Mapping[str, Any]) -> None:
    schema_name = "conformance-result.v1"
    checks = document["checks"]
    _require_unique(schema_name, checks, "check_id", "$.checks")
    expected = worst_status(item["status"] for item in checks)
    if document["status"] != expected:
        _fail(schema_name, "$.status", f"must equal the worst check status {expected!r}")


def _validate_qualification_profile(document: Mapping[str, Any]) -> None:
    _require_unique(
        "qualification-profile.v1",
        document["requirements"],
        "capability",
        "$.requirements",
    )


def _validate_acceptance_run(document: Mapping[str, Any]) -> None:
    _require_unique(
        "acceptance-run.v1",
        document["domains"],
        "domain_id",
        "$.domains",
    )


_VALIDATORS: dict[str, Callable[[Mapping[str, Any]], None]] = {
    "acceptance-observation.v1": _validate_acceptance_observation,
    "acceptance-scenario.v1": _validate_acceptance_scenario,
    "model-artifact-manifest.v1": _validate_model_artifact,
    "dataset-manifest.v1": _validate_dataset,
    "runtime-manifest.v1": _validate_runtime,
    "execution-permit.v1": _validate_permit,
    "execution-verification.v1": _validate_execution_verification,
    "acceptance-result.v1": _validate_result,
    "evidence-index.v1": _validate_evidence_index,
    "acceptance-run.v1": _validate_acceptance_run,
    "acceptance-aggregate.v1": _validate_acceptance_aggregate,
    "recording-summary.v1": _validate_recording_summary,
    "qualification-bundle.v1": _validate_qualification_bundle,
    "transport-channel.v1": _validate_transport_channel,
    "transport-channel-observation.v1": _validate_transport_channel_observation,
    "causal-chain.v1": _validate_causal_chain,
    "transport-qualification-result.v1": _validate_transport_qualification,
    "clock-relation.v1": _validate_clock_relation,
    "conformance-result.v1": _validate_conformance_result,
    "qualification-profile.v1": _validate_qualification_profile,
    "campaign-summary.v1": _validate_campaign_summary,
}


def validate_semantics(schema_name: str, document: Mapping[str, Any]) -> None:
    """Validate cross-field invariants that JSON Schema cannot express."""

    validator = _VALIDATORS.get(schema_name)
    if validator is not None:
        validator(document)


__all__ = ["SemanticValidationError", "validate_semantics"]
