from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any


class SemanticValidationError(ValueError):
    """Raised when structurally valid contract fields contradict each other."""

    def __init__(self, schema_name: str, json_path: str, message: str) -> None:
        self.schema_name = schema_name
        self.json_path = json_path
        self.validation_message = message
        super().__init__(f"{json_path}: {message}")


def _fail(schema_name: str, path: str, message: str) -> None:
    raise SemanticValidationError(schema_name, path, message)


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


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
    schema_name = "acceptance-scenario.v2"
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


def _validate_model_artifact(document: Mapping[str, Any]) -> None:
    schema_name = "model-artifact-manifest.v1"
    source = document["source"]
    target = document["target"]
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

    expected_vendor = {
        "tensorrt_engine": "nvidia",
        "rknn": "rockchip",
    }.get(target["format"])
    if expected_vendor is not None and any(
        item["vendor"] != expected_vendor for item in compatibility["hardware"]
    ):
        _fail(
            schema_name,
            "$.compatibility.hardware",
            f"{target['format']} artifacts require {expected_vendor} hardware entries",
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
    schema_name = "runtime-manifest.v1"
    inference = document["inference"]
    execution = document["execution"]
    data_plane = document["data_plane"]
    security = document["security"]
    clock = document["clock"]

    if inference["requested_provider"] != inference["actual_provider"]:
        _fail(
            schema_name,
            "$.inference.actual_provider",
            "must equal requested_provider; silent fallback is forbidden",
        )
    if inference["fallback_count"] != 0:
        _fail(schema_name, "$.inference.fallback_count", "must be zero")
    if document["ros"]["rmw_implementation"] != data_plane["rmw_implementation"]:
        _fail(
            schema_name,
            "$.data_plane.rmw_implementation",
            "must match the observed ROS RMW implementation",
        )

    source_modes = {
        "gazebo": ("simulation", "gazebo_physics", {"simulation_realtime", "simulation_stepped"}),
        "mcap_playback": ("simulation", "recorded_data", {"playback_clocked"}),
        "live_target": ({"hil", "real_robot"}, "real_hardware", {"hardware_realtime"}),
    }
    target, plant, time_modes = source_modes[execution["data_source"]]
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

    if execution["target_environment"] == "simulation" and document["physical_targets"]:
        _fail(schema_name, "$.physical_targets", "simulation must not claim physical targets")

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

    expected_vendor = {
        "CUDAExecutionProvider": "nvidia",
        "TensorrtExecutionProvider": "nvidia",
        "MIGraphXExecutionProvider": "amd",
        "RKNPU2": "rockchip",
        "CoreMLExecutionProvider": "apple",
    }.get(inference["actual_provider"])
    if expected_vendor is not None and document["accelerator"]["vendor"] != expected_vendor:
        _fail(
            schema_name,
            "$.accelerator.vendor",
            f"{inference['actual_provider']} requires vendor {expected_vendor}",
        )


def _validate_permit(document: Mapping[str, Any]) -> None:
    schema_name = "execution-permit.v1"
    issued_at = _timestamp(document["issued_at"])
    expires_at = _timestamp(document["expires_at"])
    checked_at = _timestamp(document["interlock_check"]["checked_at"])

    if expires_at <= issued_at:
        _fail(schema_name, "$.expires_at", "must be later than issued_at")
    if checked_at > issued_at:
        _fail(schema_name, "$.interlock_check.checked_at", "must not be later than issued_at")
    if document["operator_id"] == document["approver_id"]:
        _fail(schema_name, "$.approver_id", "must differ from operator_id")


def _validate_result(document: Mapping[str, Any]) -> None:
    schema_name = "acceptance-result.v1"
    if _timestamp(document["finished_at"]) < _timestamp(document["started_at"]):
        _fail(schema_name, "$.finished_at", "must not be earlier than started_at")

    _require_unique(
        schema_name,
        document["assertion_results"],
        "assertion_id",
        "$.assertion_results",
    )
    graph = document["observed_ros_graph"]
    for key in ("topics", "services", "actions"):
        _require_unique(schema_name, graph[key], "name", f"$.observed_ros_graph.{key}")

    if document["status"] == "passed":
        if document["inference"]["fallback_count"] != 0:
            _fail(
                schema_name,
                "$.inference.fallback_count",
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

    segment_keys: set[tuple[str, int]] = set()
    for index, item in enumerate(document["evidence"]):
        if "segment_index" not in item:
            continue
        key = (item["uri"], item["segment_index"])
        if key in segment_keys:
            _fail(schema_name, f"$.evidence[{index}]", "duplicate evidence segment")
        segment_keys.add(key)


_VALIDATORS: dict[str, Callable[[Mapping[str, Any]], None]] = {
    "acceptance-scenario.v2": _validate_acceptance_scenario,
    "model-artifact-manifest.v1": _validate_model_artifact,
    "dataset-manifest.v1": _validate_dataset,
    "runtime-manifest.v1": _validate_runtime,
    "execution-permit.v1": _validate_permit,
    "acceptance-result.v1": _validate_result,
}


def validate_semantics(schema_name: str, document: Mapping[str, Any]) -> None:
    """Validate cross-field invariants that JSON Schema cannot express."""

    validator = _VALIDATORS.get(schema_name)
    if validator is not None:
        validator(document)


__all__ = ["SemanticValidationError", "validate_semantics"]
