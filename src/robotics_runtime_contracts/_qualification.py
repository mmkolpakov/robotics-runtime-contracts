from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

from robotics_runtime_contracts import (
    ClockEvidenceValidationError,
    loads_mapping,
    schema_for_role,
    validate_clock_relation_evidence,
    validate_document,
)
from robotics_runtime_contracts.qualification_policy import (
    channel_observation_status,
    derive_channel_violations,
    hardware_clock_within_policy,
)

_ARTIFACT_ROLES = {
    "scenario": "acceptance_scenario",
    "acceptance_observation": "acceptance_observation",
    "runtime_manifest": "runtime_manifest",
    "acceptance_run": "acceptance_run",
    "domain_result": "acceptance_result",
    "acceptance_aggregate": "acceptance_aggregate",
    "transport_qualification": "transport_qualification_result",
    "causal_chain_contract": "causal_chain",
    "channel_contract": "transport_channel",
    "channel_observation": "transport_channel_observation",
    "clock_relation": "clock_relation",
    "provider_conformance": "conformance_result",
    "artifact_receipt": "artifact_receipt",
    "artifact_verification": "artifact_verification",
    "qualification_profile": "qualification_profile",
    "evidence_index": "evidence_index",
    "recording_summary": "recording_summary",
    "model_manifest": "model_artifact_manifest",
    "dataset_manifest": "dataset_manifest",
    "execution_permit": "execution_permit",
    "execution_verification": "execution_verification",
}
_CONTRACT_SCHEMAS = {
    kind: frozenset({schema_for_role(role)}) for kind, role in _ARTIFACT_ROLES.items()
}
_RAW_ARTIFACT_KINDS = frozenset(
    {
        "metrics",
        "traces",
        "junit",
        "other_evidence",
        "policy",
        "package",
        "attestation",
        "verification",
        "recording",
    }
)
_SUBJECT_NAME = re.compile(r"^[a-z0-9][a-z0-9._/-]{0,1023}$")
_EXECUTION_FIELDS = (
    "target_environment",
    "data_source",
    "plant_backend",
    "time_mode",
    "data_plane_profile",
)


class QualificationError(ValueError):
    """Raised when individually valid qualification documents contradict each other."""

    error_id = "qualification.invalid"

    def __init__(
        self,
        message: str,
        *,
        error_id: str | None = None,
        json_path: str | None = None,
    ) -> None:
        if error_id is not None:
            self.error_id = error_id
        self.json_path = json_path
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class _Artifact:
    kind: str
    subject_name: str
    sha256: str
    size_bytes: int
    document: Mapping[str, Any] | None


def _fail(message: str) -> NoReturn:
    raise QualificationError(message)


def _document(artifact: _Artifact) -> Mapping[str, Any]:
    if artifact.document is None:
        _fail(f"{artifact.kind} requires a contract document")
    return artifact.document


def _timestamp(value: str) -> datetime:
    normalized = f"{value[:-1]}+00:00" if value.endswith(("Z", "z")) else value
    return datetime.fromisoformat(normalized)


def _require_time_order(label: str, *values: str) -> None:
    timestamps = [_timestamp(value) for value in values]
    if timestamps != sorted(timestamps):
        _fail(f"{label} is not chronologically ordered")


def _require_equal(label: str, expected: Any, actual: Any) -> None:
    if expected != actual:
        _fail(f"{label} does not match: expected {expected!r}, received {actual!r}")


def _json_scalar_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    return bool(left == right)


def _project_fields(item: Mapping[str, Any], fields: Sequence[str]) -> dict[str, Any]:
    return {field: item[field] for field in fields if field in item}


def _require_fields(
    label: str,
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
    fields: Sequence[str],
) -> None:
    for field in fields:
        _require_equal(f"{label}.{field}", expected[field], actual[field])


def _one(
    grouped: Mapping[str, Sequence[_Artifact]],
    kind: str,
    subject_name: str,
) -> _Artifact:
    artifacts = grouped.get(kind, ())
    if len(artifacts) != 1 or artifacts[0].subject_name != subject_name:
        _fail(f"qualification requires exactly one {kind} named {subject_name}")
    return artifacts[0]


def _labeled(
    grouped: Mapping[str, Sequence[_Artifact]],
    kind: str,
    prefix: str,
) -> dict[str, _Artifact]:
    result: dict[str, _Artifact] = {}
    for artifact in grouped.get(kind, ()):
        name = artifact.subject_name
        if not name.startswith(prefix) or not name.endswith(".json"):
            _fail(f"non-canonical {kind} subject name: {name}")
        label = name[len(prefix) : -len(".json")]
        if not label:
            _fail(f"empty {kind} label")
        result[label] = artifact
    return result


def _artifact_by_digest(
    grouped: Mapping[str, Sequence[_Artifact]],
    kind: str,
    digest: str,
    label: str,
) -> _Artifact:
    matches = [artifact for artifact in grouped.get(kind, ()) if artifact.sha256 == digest]
    if len(matches) != 1:
        _fail(f"{label} does not identify exactly one {kind}")
    return matches[0]


def _optional_artifact(
    grouped: Mapping[str, Sequence[_Artifact]],
    kind: str,
    digest: str | None,
    label: str,
) -> _Artifact | None:
    artifacts = grouped.get(kind, ())
    if digest is None:
        if artifacts:
            _fail(f"qualification includes {kind} not declared by the scenario")
        return None
    artifact = _artifact_by_digest(grouped, kind, digest, label)
    if len(artifacts) != 1:
        _fail(f"qualification includes unreferenced {kind} subjects")
    return artifact


def _raw_artifacts(
    grouped: Mapping[str, Sequence[_Artifact]],
    kinds: Sequence[str] | None = None,
) -> list[_Artifact]:
    selected = kinds or tuple(_RAW_ARTIFACT_KINDS)
    return [artifact for kind in selected for artifact in grouped.get(kind, ())]


def _require_raw(
    grouped: Mapping[str, Sequence[_Artifact]],
    digest: str,
    label: str,
    *,
    kinds: Sequence[str] | None = None,
    size_bytes: int | None = None,
) -> _Artifact:
    matches = [
        artifact
        for artifact in _raw_artifacts(grouped, kinds)
        if artifact.sha256 == digest and (size_bytes is None or artifact.size_bytes == size_bytes)
    ]
    if len(matches) != 1:
        suffix = " with the indexed size" if size_bytes is not None else ""
        _fail(f"{label} does not identify exactly one retained raw artifact{suffix}")
    return matches[0]


def _validate_execution_alignment(
    scenario: Mapping[str, Any],
    acceptance_run: Mapping[str, Any],
    runtime: Mapping[str, Any],
    result: Mapping[str, Any],
    domain_id: str,
) -> None:
    expected = scenario["execution"]
    _require_fields(
        f"runtime manifest {domain_id} execution",
        expected,
        runtime["execution"],
        _EXECUTION_FIELDS,
    )
    _require_fields(
        f"result {domain_id} execution",
        expected,
        result["execution"],
        _EXECUTION_FIELDS,
    )
    _require_equal(
        f"runtime manifest {domain_id} security profile",
        expected["security_profile"],
        runtime["security"]["profile"],
    )
    _require_fields(
        f"runtime manifest {domain_id} data_plane",
        scenario["data_plane_policy"],
        runtime["data_plane"],
        ("shm_transport", "data_sharing", "private_ipc"),
    )
    _require_equal(
        f"result {domain_id} workload kind",
        runtime["workload"]["kind"],
        result["workload"]["kind"],
    )
    if runtime["workload"]["kind"] == "inference":
        runtime_inference = runtime["workload"]["inference"]
        result_workload = result["workload"]
        _require_fields(
            f"result {domain_id} workload",
            runtime_inference,
            result_workload,
            ("runtime_family", "actual_provider", "fallback_count"),
        )
        _require_equal(
            f"result {domain_id} workload.model_format",
            runtime["workload"]["model"]["format"],
            result_workload["model_format"],
        )

    observed_runtime = result["runtime_observation"]
    _require_equal(
        f"result {domain_id} execution subject",
        runtime["execution_subject"]["digest"],
        observed_runtime["execution_subject_digest"],
    )
    for field in ("domain_id", "rmw_implementation", "rmw_version"):
        _require_equal(
            f"result {domain_id} observed ROS {field}",
            runtime["ros"][field],
            observed_runtime[field if field != "domain_id" else "ros_domain_id"],
        )
    _require_equal(
        f"result {domain_id} observed middleware configuration",
        runtime["data_plane"].get("middleware_configuration_sha256"),
        observed_runtime.get("middleware_configuration_sha256"),
    )
    _require_equal(
        f"result {domain_id} observed security state",
        runtime["security"]["profile"] != "none",
        observed_runtime["security_enabled"],
    )
    _require_equal(
        f"result {domain_id} observed security strategy",
        runtime["security"]["strategy"],
        observed_runtime["security_strategy"],
    )
    _require_equal(
        f"runtime manifest {domain_id} evaluator bindings",
        scenario["evaluator_requirements"],
        runtime["evaluator_bindings"],
    )
    _require_equal(
        f"result {domain_id} evaluator observations",
        scenario["evaluator_requirements"],
        result["evaluators"],
    )

    time_authority = acceptance_run["time_authority"]
    runtime_clock = runtime["clock"]
    observation = result["time_authority_observation"]
    _require_equal(
        f"runtime manifest {domain_id} clock protocol",
        time_authority["kind"],
        runtime_clock["sync_protocol"],
    )
    _require_equal(
        f"result {domain_id} time-authority source",
        time_authority["source_id"],
        observation["source_id"],
    )
    time_policy = scenario["time_policy"]
    within_policy = (
        observation["sample_count"] >= time_policy["time_authority_min_samples"]
        and observation["p50_delivery_latency_ms"]
        <= time_policy["max_time_authority_delivery_latency_p50_ms"]
        and observation["p95_delivery_latency_ms"]
        <= time_policy["max_time_authority_delivery_latency_p95_ms"]
        and observation["max_delivery_latency_ms"]
        <= time_policy["max_time_authority_delivery_latency_ms"]
    )
    _require_equal(
        f"result {domain_id} time-authority policy verdict",
        within_policy,
        observation["within_policy"],
    )
    clock_observation = result["clock_observation"]
    realtime_within_policy = clock_observation["real_time_factor"] >= time_policy.get(
        "min_realtime_factor", 0
    ) and clock_observation["deadline_miss_ratio"] <= time_policy.get("max_deadline_miss_ratio", 1)
    if result["status"] == "passed" and not realtime_within_policy:
        _fail(f"result {domain_id} violates its real-time policy")

    hardware_clock = result.get("hardware_clock_observation")
    if hardware_clock is not None:
        expected_protocol = time_policy["clock_sync_protocol"]
        for label, expected_value, actual_value in (
            ("runtime clock protocol", expected_protocol, runtime_clock["sync_protocol"]),
            ("hardware clock protocol", expected_protocol, hardware_clock["sync_protocol"]),
            ("hardware clock offset", runtime_clock["offset_ms"], hardware_clock["offset_ms"]),
            ("hardware clock drift", runtime_clock["drift_ppm"], hardware_clock["drift_ppm"]),
        ):
            _require_equal(f"result {domain_id} {label}", expected_value, actual_value)
        hardware_within_policy = hardware_clock_within_policy(
            time_policy,
            hardware_clock,
            monotonic=clock_observation["monotonic"],
        )
        _require_equal(
            f"result {domain_id} hardware-clock policy verdict",
            hardware_within_policy,
            hardware_clock["within_policy"],
        )


def _validate_model_and_dataset(
    grouped: Mapping[str, Sequence[_Artifact]],
    scenario: Mapping[str, Any],
    runtimes: Mapping[str, _Artifact],
    results: Mapping[str, _Artifact],
) -> None:
    model_digest = scenario.get("model_manifest_sha256")
    dataset_digest = scenario.get("dataset_manifest_sha256")
    model = _optional_artifact(grouped, "model_manifest", model_digest, "scenario model")
    dataset = _optional_artifact(grouped, "dataset_manifest", dataset_digest, "scenario dataset")

    for domain_id, result_artifact in results.items():
        result = _document(result_artifact)
        for name, digest in (("model", model_digest), ("dataset", dataset_digest)):
            _require_equal(
                f"result {domain_id} {name}_manifest_sha256",
                digest,
                result.get(f"{name}_manifest_sha256"),
            )

    if model is None:
        for domain_id, runtime_artifact in runtimes.items():
            if _document(runtime_artifact)["workload"]["kind"] == "inference":
                _fail(f"runtime manifest {domain_id} reports inference without a model manifest")
    else:
        model_document = _document(model)
        target = model_document["target"]
        numerical = model_document["numerical_conformance"]
        for label, digest in (
            ("model source artifact", model_document["source"]["sha256"]),
            ("model target artifact", target["sha256"]),
            ("model conformance report", numerical["report_sha256"]),
            ("model conformance dataset", numerical["sample_dataset_sha256"]),
        ):
            _require_raw(grouped, digest, label)
        calibration = model_document["build"].get("calibration_dataset_sha256")
        if calibration is not None:
            _require_raw(grouped, calibration, "model calibration dataset")
        for domain_id, runtime_artifact in runtimes.items():
            workload = _document(runtime_artifact)["workload"]
            if workload["kind"] != "inference":
                _fail(f"runtime manifest {domain_id} omits the scenario inference workload")
            _require_equal(
                f"runtime manifest {domain_id} model manifest",
                model.sha256,
                workload["model"]["manifest_sha256"],
            )
            observed_model = {
                "sha256": workload["model"]["artifact_sha256"],
                "format": workload["model"]["format"],
                "runtime_family": workload["inference"]["runtime_family"],
                "execution_provider": workload["inference"]["actual_provider"],
            }
            _require_fields(
                f"runtime manifest {domain_id} model",
                target,
                observed_model,
                tuple(observed_model),
            )

    if dataset is not None:
        dataset_document = _document(dataset)
        source = dataset_document["artifact"]
        _require_raw(
            grouped,
            source["sha256"],
            "dataset recording",
            kinds=("recording",),
            size_bytes=source["size_bytes"],
        )
        qos_digest = dataset_document["time"].get("qos_overrides_sha256")
        if qos_digest is not None:
            _require_raw(grouped, qos_digest, "dataset QoS overrides")


def _validate_provider_bindings(
    grouped: Mapping[str, Sequence[_Artifact]],
    scenario: Mapping[str, Any],
    run_id: str,
    runtimes: Mapping[str, _Artifact],
    run_created_at: str,
) -> None:
    used_profiles: set[str] = set()
    used_results: set[str] = set()
    requirements = scenario["provider_requirements"]
    scenario_capabilities = set(requirements["capabilities"])
    scene_requirement = requirements.get("scene")

    def scene_satisfies(scene: Mapping[str, Any]) -> bool:
        if scene_requirement is None:
            return True
        return (
            scene["semantic_scene_id"] == scene_requirement["semantic_scene_id"]
            and set(scene_requirement["required_entities"]) <= set(scene["entities"])
            and set(scene_requirement["required_interfaces"]) <= set(scene["interfaces"])
            and all(
                _json_scalar_equal(scene["physical_parameters"].get(key), value)
                for key, value in scene_requirement.get("physical_parameters", {}).items()
            )
        )

    for domain_id, runtime_artifact in runtimes.items():
        runtime = _document(runtime_artifact)
        domain_capabilities: set[str] = set()
        domain_scenes: list[Mapping[str, Any]] = []
        for binding in runtime["provider_bindings"]:
            profile_artifact = _artifact_by_digest(
                grouped,
                "qualification_profile",
                binding["qualification_profile_sha256"],
                f"runtime manifest {domain_id} provider profile",
            )
            result_artifact = _artifact_by_digest(
                grouped,
                "provider_conformance",
                binding["conformance_result_sha256"],
                f"runtime manifest {domain_id} provider conformance",
            )
            used_profiles.add(profile_artifact.sha256)
            used_results.add(result_artifact.sha256)
            profile = _document(profile_artifact)
            result = _document(result_artifact)
            for label, expected, actual in (
                ("run_id", run_id, result["run_id"]),
                ("target_id", binding["target_id"], result["target_id"]),
                (
                    "execution subject",
                    runtime["execution_subject"]["digest"],
                    result["execution_subject_digest"],
                ),
                (
                    "qualification profile",
                    profile_artifact.sha256,
                    result["qualification_profile_sha256"],
                ),
                ("provider", binding["provider"], result["provider"]),
                ("capabilities", set(binding["capabilities"]), set(result["capabilities"])),
                ("provider kind", binding["provider"]["kind"], profile["provider_kind"]),
                ("scene", binding.get("scene"), result.get("scene")),
            ):
                _require_equal(f"provider binding {domain_id} {label}", expected, actual)
            if result["status"] != "passed":
                _fail(f"provider binding {domain_id} references non-passing conformance")
            _require_time_order(
                f"provider binding {domain_id} timeline",
                run_created_at,
                result["generated_at"],
                runtime["generated_at"],
            )
            profile_capabilities = {
                item["capability"] for item in profile["requirements"] if item["required"]
            }
            if not profile_capabilities <= set(result["capabilities"]):
                _fail(f"provider binding {domain_id} omits required profile capabilities")
            _require_raw(
                grouped,
                binding["provider"]["configuration_sha256"],
                f"provider binding {domain_id} configuration",
            )
            scene = binding.get("scene")
            if scene is not None:
                domain_scenes.append(scene)
            for index, evidence in enumerate(result["evidence"]):
                _require_raw(
                    grouped,
                    evidence["sha256"],
                    f"provider binding {domain_id} evidence {index}",
                    size_bytes=evidence["size_bytes"],
                )
            domain_capabilities.update(binding["capabilities"])
        if not scenario_capabilities <= domain_capabilities:
            _fail(f"runtime provider bindings for {domain_id} do not satisfy capabilities")
        if scene_requirement is not None and not any(map(scene_satisfies, domain_scenes)):
            _fail(f"runtime provider bindings for {domain_id} do not satisfy the scene")

    supplied_profiles = {artifact.sha256 for artifact in grouped.get("qualification_profile", ())}
    supplied_results = {artifact.sha256 for artifact in grouped.get("provider_conformance", ())}
    if used_profiles != supplied_profiles or used_results != supplied_results:
        _fail("provider qualification artifacts must match runtime bindings")


def _validate_receipts(
    grouped: Mapping[str, Sequence[_Artifact]],
    scenario: Mapping[str, Any],
    run_id: str,
    evidence_indexes: Mapping[str, _Artifact],
    run_created_at: str,
    aggregate_generated_at: str,
) -> None:
    used_receipts: set[str] = set()
    used_verifications: set[str] = set()

    def receipt_for(digest: str, label: str) -> Mapping[str, Any]:
        artifact = _artifact_by_digest(grouped, "artifact_receipt", digest, label)
        used_receipts.add(artifact.sha256)
        receipt = _document(artifact)
        _require_raw(
            grouped,
            receipt["statement_sha256"],
            f"{label} statement",
            kinds=("attestation",),
        )
        verification_artifact = _artifact_by_digest(
            grouped,
            "artifact_verification",
            receipt["verification_sha256"],
            f"{label} verification",
        )
        used_verifications.add(verification_artifact.sha256)
        verification = _document(verification_artifact)
        for field, expected, actual in (
            ("statement", receipt["statement_sha256"], verification["statement_sha256"]),
            ("artifact descriptor", receipt["artifact"], verification["artifact"]),
            ("producer", receipt["producer"]["identity"], verification["producer_identity"]),
            (
                "producer implementation",
                receipt["producer"]["implementation"],
                verification["producer_implementation"],
            ),
        ):
            _require_equal(f"{label} {field}", expected, actual)
        if _timestamp(verification["verified_at"]) > _timestamp(receipt["created_at"]):
            _fail(f"{label} was created before its verification")
        if "run_id" in receipt:
            _require_time_order(
                f"{label} timeline",
                run_created_at,
                verification["verified_at"],
                receipt["created_at"],
                aggregate_generated_at,
            )
        _require_raw(
            grouped,
            verification["trust_policy_sha256"],
            f"{label} trust policy",
            kinds=("policy",),
        )
        _require_raw(
            grouped,
            verification["verification_evidence_sha256"],
            f"{label} verification evidence",
            kinds=("verification",),
        )
        content_manifest_sha256 = verification.get("content_manifest_sha256")
        if content_manifest_sha256 is not None:
            _require_raw(
                grouped,
                content_manifest_sha256,
                f"{label} content manifest",
            )
        return receipt

    for domain_id, index_artifact in evidence_indexes.items():
        for artifact in _document(index_artifact)["artifacts"]:
            if artifact["storage_state"] != "retained":
                continue
            receipt = receipt_for(
                artifact["receipt_sha256"],
                f"evidence index {domain_id} artifact {artifact['artifact_id']} receipt",
            )
            if receipt.get("run_id") != run_id:
                _fail(f"evidence index {domain_id} receipt belongs to another run")
            expected = {
                field: artifact[field]
                for field in ("uri", "sha256", "size_bytes", "media_type", "immutable_revision")
            }
            if receipt["artifact"] != expected:
                _fail(f"evidence index {domain_id} receipt describes different bytes")

    for requirement in scenario["evaluator_requirements"]:
        package = _require_raw(
            grouped,
            requirement["artifact_sha256"],
            f"evaluator {requirement['namespace']} package",
            kinds=("package",),
        )
        receipt = receipt_for(
            requirement["receipt_sha256"],
            f"evaluator {requirement['namespace']} receipt",
        )
        if (
            receipt["artifact"]["sha256"] != package.sha256
            or receipt["artifact"]["size_bytes"] != package.size_bytes
        ):
            _fail(f"evaluator {requirement['namespace']} receipt describes another package")

    supplied_receipts = {artifact.sha256 for artifact in grouped.get("artifact_receipt", ())}
    if used_receipts != supplied_receipts:
        _fail("artifact receipts must match retained evidence and evaluators")
    supplied_verifications = {
        artifact.sha256 for artifact in grouped.get("artifact_verification", ())
    }
    if used_verifications != supplied_verifications:
        _fail("artifact verifications must match retained evidence and evaluators")


def _validate_retained_configuration(
    grouped: Mapping[str, Sequence[_Artifact]],
    scenario: Mapping[str, Any],
    acceptance_run: Mapping[str, Any],
    runtimes: Mapping[str, _Artifact],
) -> None:
    for label, digest in (
        (
            "time-authority configuration",
            acceptance_run["time_authority"].get("configuration_sha256"),
        ),
        ("scenario QoS overrides", scenario["time_policy"].get("qos_overrides_sha256")),
    ):
        if digest is not None:
            _require_raw(grouped, digest, label)
    expected_middleware = scenario["data_plane_policy"].get("middleware_configuration_sha256")
    if expected_middleware is not None:
        _require_raw(grouped, expected_middleware, "scenario middleware configuration")
    for domain_id, artifact in runtimes.items():
        runtime = _document(artifact)
        observed_middleware = runtime["data_plane"].get("middleware_configuration_sha256")
        if expected_middleware is not None:
            _require_equal(
                f"runtime manifest {domain_id} middleware configuration",
                expected_middleware,
                observed_middleware,
            )
        for configuration in runtime.get("configuration_artifacts", []):
            _require_raw(
                grouped,
                configuration["sha256"],
                f"runtime manifest {domain_id} {configuration['kind']} configuration",
            )
        if observed_middleware is not None:
            _require_raw(
                grouped,
                observed_middleware,
                f"runtime manifest {domain_id} middleware configuration",
            )


def _validate_physical_authorization(
    grouped: Mapping[str, Sequence[_Artifact]],
    scenario_artifact: _Artifact,
    runtimes: Mapping[str, _Artifact],
    results: Mapping[str, _Artifact],
) -> None:
    scenario = _document(scenario_artifact)
    physical = scenario["execution"]["target_environment"] in {"hil", "real_robot"}
    permits = {artifact.sha256: artifact for artifact in grouped.get("execution_permit", ())}
    verifications = {
        artifact.sha256: artifact for artifact in grouped.get("execution_verification", ())
    }
    if not physical:
        if permits or verifications:
            _fail("simulation qualification must not include physical authorization subjects")
        return

    trust_policy = scenario["authorization"]["trust_policy_sha256"]
    _require_raw(grouped, trust_policy, "scenario trust policy", kinds=("policy",))
    used_permits: set[str] = set()
    used_verifications: set[str] = set()
    scenario_scope = set(scenario["execution"]["hardware_scope"])

    for domain_id, runtime_artifact in runtimes.items():
        runtime = _document(runtime_artifact)
        result = _document(results[domain_id])
        runtime_authorization = runtime["authorization"]
        result_authorization = result["authorization"]
        _require_fields(
            f"result {domain_id} authorization",
            runtime_authorization,
            result_authorization,
            ("permit_sha256", "execution_verification_sha256", "trust_policy_sha256"),
        )
        _require_equal(
            f"runtime manifest {domain_id} authorization trust policy",
            trust_policy,
            runtime_authorization["trust_policy_sha256"],
        )

        permit_digest = runtime_authorization["permit_sha256"]
        verification_digest = runtime_authorization["execution_verification_sha256"]
        permit_artifact = permits.get(permit_digest)
        verification_artifact = verifications.get(verification_digest)
        if permit_artifact is None or verification_artifact is None:
            _fail(f"physical domain {domain_id} lacks its typed permit or verification subject")
        used_permits.add(permit_digest)
        used_verifications.add(verification_digest)
        permit = _document(permit_artifact)
        verification = _document(verification_artifact)

        for label, expected_value, actual_value in (
            ("scenario", scenario_artifact.sha256, permit["scenario_sha256"]),
            ("image", runtime["execution_subject"]["digest"], permit["subject_digest"]),
            ("trust policy", trust_policy, permit["trust_policy_sha256"]),
            ("verification permit", permit_digest, verification["permit_sha256"]),
            ("verification trust policy", trust_policy, verification["trust_policy_sha256"]),
            ("verification target", permit["target"], verification["target"]),
            ("result target", permit["target"], result_authorization["target"]),
            (
                "physical effect",
                scenario["execution"]["physical_effect"],
                permit["allowed_physical_effect"],
            ),
        ):
            _require_equal(f"permit for {domain_id} {label}", expected_value, actual_value)
        if not scenario_scope.issubset(set(permit["hardware_scope"])):
            _fail(f"permit for {domain_id} does not cover scenario hardware scope")

        runtime_targets = {target["target_id"]: target for target in runtime["physical_targets"]}
        target = runtime_targets.get(permit["target"]["target_id"])
        if target is None:
            _fail(f"runtime manifest {domain_id} omits the permitted physical target")
        _require_fields(
            f"runtime manifest {domain_id} target",
            permit["target"],
            target,
            ("identity_kind", "identity_sha256"),
        )
        _require_equal(
            f"runtime manifest {domain_id} preflight evidence",
            permit["interlock_check"]["sha256"],
            target["preflight_evidence_sha256"],
        )
        if not scenario_scope.issubset({item["scope"] for item in runtime["physical_targets"]}):
            _fail(f"runtime manifest {domain_id} does not cover scenario hardware scope")

        signers = {signer["role"]: signer for signer in verification["signers"]}
        for role in ("operator", "approver"):
            _require_equal(
                f"verification for {domain_id} {role}",
                permit[f"{role}_id"],
                signers[role]["identity"],
            )
        if not (
            _timestamp(permit["issued_at"])
            <= _timestamp(verification["verified_at"])
            <= _timestamp(result["started_at"])
            <= _timestamp(result["finished_at"])
            < _timestamp(permit["expires_at"])
        ):
            _fail(f"physical domain {domain_id} ran outside its verified permit interval")

        _require_raw(grouped, permit["interlock_check"]["sha256"], f"permit {domain_id} interlock")
        _require_raw(
            grouped, verification["statement_sha256"], f"verification {domain_id} statement"
        )
        _require_raw(
            grouped,
            verification["policy_sha256"],
            f"verification {domain_id} execution policy",
            kinds=("policy",),
        )
        for signer in verification["signers"]:
            _require_raw(
                grouped,
                signer["bundle_sha256"],
                f"verification {domain_id} {signer['role']} bundle",
            )
        for policy_digest in runtime["security"]["policy_digests"]:
            _require_raw(
                grouped,
                policy_digest,
                f"runtime manifest {domain_id} security policy",
                kinds=("policy",),
            )
        for physical_target in runtime["physical_targets"]:
            _require_raw(
                grouped,
                physical_target["preflight_evidence_sha256"],
                f"runtime manifest {domain_id} target preflight evidence",
            )

        forbidden = result["forbidden_graph_observation"]
        for kind in ("topics", "services", "actions"):
            _require_equal(
                f"result {domain_id} checked forbidden {kind}",
                set(scenario["forbidden_ros_graph"][kind]),
                set(forbidden[f"checked_{kind}"]),
            )

    if used_permits != set(permits) or used_verifications != set(verifications):
        _fail("qualification includes unreferenced physical authorization subjects")


def _transport_sources(
    grouped: Mapping[str, Sequence[_Artifact]],
    run_id: str,
) -> tuple[dict[str, _Artifact], dict[str, _Artifact], dict[str, _Artifact]]:
    channels: dict[str, _Artifact] = {}
    for artifact in grouped.get("channel_contract", ()):
        channel_id = _document(artifact)["channel_id"]
        if channel_id in channels:
            _fail(f"duplicate channel contract: {channel_id}")
        channels[channel_id] = artifact

    observations: dict[str, _Artifact] = {}
    for artifact in grouped.get("channel_observation", ()):
        document = _document(artifact)
        observation_id = document["observation_id"]
        channel_id = document["channel_id"]
        if observation_id in observations:
            _fail(f"duplicate channel observation: {observation_id}")
        if document["run_id"] != run_id:
            _fail(f"channel observation {observation_id} has a foreign run_id")
        channel = channels.get(channel_id)
        if channel is None:
            _fail(f"channel observation {observation_id} references an absent channel")
        if document["channel_contract_sha256"] != channel.sha256:
            _fail(f"channel observation {observation_id} references foreign channel bytes")
        observations[observation_id] = artifact

    chains: dict[str, _Artifact] = {}
    for artifact in grouped.get("causal_chain_contract", ()):
        document = _document(artifact)
        chain_id = document["chain_id"]
        if chain_id in chains:
            _fail(f"duplicate causal-chain contract: {chain_id}")
        for reference in document["channel_contracts"]:
            channel = channels.get(reference["channel_id"])
            if channel is None or reference["sha256"] != channel.sha256:
                _fail(f"causal-chain contract {chain_id} references foreign channel bytes")
        chains[chain_id] = artifact
    return chains, channels, observations


def _validate_channel_delivery(channel: Mapping[str, Any], observation: Mapping[str, Any]) -> None:
    delivery = channel["delivery"]
    duration = (
        _timestamp(observation["finished_at"]) - _timestamp(observation["started_at"])
    ).total_seconds()
    reported = {item["code"] for item in observation["violations"]}
    expected_violations = derive_channel_violations(
        delivery,
        sent_count=observation["sent_count"],
        loss_ratio=observation["loss_ratio"],
        duplicate_count=observation["duplicate_count"],
        out_of_order_count=observation["out_of_order_count"],
        max_message_age_ms=observation["max_message_age_ms"],
        observation_duration_sec=duration,
        reported_violation_codes=reported,
    )
    expected_status = channel_observation_status(expected_violations)
    if observation["status"] != expected_status or reported != expected_violations:
        _fail(f"channel observation {observation['observation_id']} contradicts its contract")


def _validate_transport(
    grouped: Mapping[str, Sequence[_Artifact]],
    run_id: str,
    run_domains: set[str],
    scenario_artifact: _Artifact,
    aggregate: Mapping[str, Any],
    evidence_indexes: Mapping[str, _Artifact],
    results: Mapping[str, _Artifact],
    run_created_at: str,
    aggregate_generated_at: str,
) -> None:
    transport_artifacts = grouped.get("transport_qualification", ())
    has_sources = any(
        grouped.get(kind)
        for kind in (
            "causal_chain_contract",
            "channel_contract",
            "channel_observation",
            "clock_relation",
        )
    )
    cross_domain = aggregate["cross_domain_e2e"]
    if cross_domain["status"] == "unevaluated":
        if transport_artifacts or has_sources:
            _fail("unevaluated aggregate must not include transport evidence")
        return
    if len(transport_artifacts) != 1:
        _fail("evaluated aggregate requires exactly one transport qualification")
    transport = transport_artifacts[0]
    if transport.subject_name != "transport-qualification.json":
        _fail("non-canonical transport qualification subject name")
    transport_document = _document(transport)
    if transport_document["run_id"] != run_id:
        _fail("transport qualification has a foreign run_id")
    evaluated_at = transport_document["verdict"]["evaluated_at"]
    _require_time_order(
        "transport qualification timeline",
        run_created_at,
        evaluated_at,
        transport_document["generated_at"],
        aggregate_generated_at,
    )
    for domain_id, result_artifact in results.items():
        _require_time_order(
            f"transport qualification after domain {domain_id}",
            _document(result_artifact)["finished_at"],
            evaluated_at,
            transport_document["generated_at"],
            aggregate_generated_at,
        )
    expected_pointer = {
        "qualification_id": transport_document["qualification_id"],
        "result_sha256": transport.sha256,
        "status": transport_document["verdict"]["status"],
    }
    if cross_domain["transport_qualification"] != expected_pointer:
        _fail("aggregate transport qualification pointer does not match local result")

    chains, channels, observations = _transport_sources(grouped, run_id)
    relation_artifacts = grouped.get("clock_relation", ())
    scenario = _document(scenario_artifact)
    _require_equal(
        "transport qualification scenario digest",
        scenario_artifact.sha256,
        transport_document["scenario_sha256"],
    )
    clock_policy = scenario["time_policy"].get("cross_domain_clock")
    if clock_policy is None:
        _fail("evaluated cross-domain transport requires time_policy.cross_domain_clock")
    relations: dict[str, _Artifact] = {}
    evidence_sha256_by_domain = {
        domain_id: {str(item["sha256"]) for item in _document(artifact)["artifacts"]}
        for domain_id, artifact in evidence_indexes.items()
    }
    for artifact in relation_artifacts:
        relation = _document(artifact)
        relation_id = relation["relation_id"]
        if relation_id in relations:
            _fail(f"duplicate clock relation: {relation_id}")
        if relation["run_id"] != run_id:
            _fail(f"clock relation {relation_id} has a foreign run_id")
        _require_time_order(
            f"clock relation {relation_id} timeline",
            run_created_at,
            relation["started_at"],
            relation["finished_at"],
            evaluated_at,
        )
        for domain_id in (relation["source_domain_id"], relation["destination_domain_id"]):
            domain_result = _document(results[domain_id])
            _require_time_order(
                f"clock relation {relation_id} domain {domain_id} window",
                domain_result["started_at"],
                relation["started_at"],
                relation["finished_at"],
                domain_result["finished_at"],
            )
        _require_equal(
            f"clock relation {relation_id} scenario digest",
            scenario_artifact.sha256,
            relation["scenario_sha256"],
        )
        _require_equal(
            f"clock relation {relation_id} policy",
            clock_policy,
            relation["policy"],
        )
        try:
            validate_clock_relation_evidence(relation, evidence_sha256_by_domain)
        except ClockEvidenceValidationError as error:
            _fail(f"clock relation {relation_id}: {error}")
        relations[relation_id] = artifact
    projection = {
        relation_id: {
            "relation_id": relation_id,
            "source_domain_id": _document(artifact)["source_domain_id"],
            "destination_domain_id": _document(artifact)["destination_domain_id"],
            "sha256": artifact.sha256,
            "status": _document(artifact)["status"],
        }
        for relation_id, artifact in relations.items()
    }
    declared = {item["relation_id"]: item for item in transport_document["clock_relations"]}
    if projection != declared:
        _fail("transport clock relations do not match local subjects")
    required_pairs = {
        (
            _document(artifact)["source"]["domain_id"],
            _document(artifact)["destination"]["domain_id"],
        )
        for artifact in channels.values()
    }
    relation_pairs = {
        (
            _document(artifact)["source_domain_id"],
            _document(artifact)["destination_domain_id"],
        )
        for artifact in relations.values()
    }
    if not relation_pairs <= required_pairs:
        _fail("transport includes a clock relation outside channel domain pairs")
    if relation_pairs != required_pairs and transport_document["verdict"]["status"] not in {
        "incomplete",
        "error",
    }:
        _fail("missing clock relations require an incomplete transport verdict")
    chain_projection = {chain_id: artifact.sha256 for chain_id, artifact in chains.items()}
    if chain_projection != {
        item["chain_id"]: item["sha256"] for item in transport_document["causal_chain_contracts"]
    }:
        _fail("transport causal-chain contracts do not match local subjects")
    channel_projection = {
        channel_id: (
            _document(artifact)["source"]["domain_id"],
            _document(artifact)["destination"]["domain_id"],
            artifact.sha256,
        )
        for channel_id, artifact in channels.items()
    }
    if channel_projection != {
        item["channel_id"]: (
            item["source_domain_id"],
            item["destination_domain_id"],
            item["sha256"],
        )
        for item in transport_document["channel_contracts"]
    }:
        _fail("transport channel contracts do not match local subjects")
    observation_projection = {
        observation_id: (
            _document(artifact)["channel_id"],
            _document(artifact)["status"],
            artifact.sha256,
        )
        for observation_id, artifact in observations.items()
    }
    if observation_projection != {
        item["observation_id"]: (item["channel_id"], item["status"], item["sha256"])
        for item in transport_document["channel_observations"]
    }:
        _fail("transport channel observations do not match local subjects")

    for artifact in channels.values():
        _require_raw(
            grouped,
            _document(artifact)["implementation_binding"]["configuration_sha256"],
            f"channel {_document(artifact)['channel_id']} bridge configuration",
        )
    for artifact in observations.values():
        observation = _document(artifact)
        _require_time_order(
            f"channel observation {observation['observation_id']} timeline",
            run_created_at,
            observation["started_at"],
            observation["finished_at"],
            evaluated_at,
        )
        channel = _document(channels[observation["channel_id"]])
        for endpoint in (channel["source"], channel["destination"]):
            domain_id = endpoint["domain_id"]
            domain_result = _document(results[domain_id])
            _require_time_order(
                f"channel observation {observation['observation_id']} domain {domain_id} window",
                domain_result["started_at"],
                observation["started_at"],
                observation["finished_at"],
                domain_result["finished_at"],
            )
        _validate_channel_delivery(channel, observation)

    chain_results = {item["chain_id"]: item for item in transport_document["causal_chains"]}
    for chain_id, artifact in chains.items():
        chain = _document(artifact)
        expected_channels = [item["channel_id"] for item in chain["channel_contracts"]]
        _require_equal(
            f"transport causal chain {chain_id} channel order",
            expected_channels,
            chain_results[chain_id]["channel_ids"],
        )
        endpoint_domains = {
            domain_id
            for channel_id in expected_channels
            for domain_id in (
                _document(channels[channel_id])["source"]["domain_id"],
                _document(channels[channel_id])["destination"]["domain_id"],
            )
        }
        _require_equal(
            f"causal-chain contract {chain_id} required domains",
            set(chain["required_domain_ids"]),
            endpoint_domains,
        )
        for hop in chain_results[chain_id]["hops"]:
            _require_equal(
                f"transport hop {hop['channel_id']} relationship",
                _document(channels[hop["channel_id"]])["trace"]["relationship"],
                hop["relationship"],
            )

    trace_evidence = {item["domain_id"]: item for item in transport_document["trace_evidence"]}
    if set(trace_evidence) != run_domains:
        _fail("transport trace evidence does not equal acceptance run domains")
    for domain_id, artifact in evidence_indexes.items():
        trace = trace_evidence[domain_id]
        if trace["evidence_index_sha256"] != artifact.sha256:
            _fail(f"transport evidence index digest does not match domain {domain_id}")
        if not any(
            indexed["artifact_id"] == trace["artifact_id"]
            and indexed["uri"] == trace["uri"]
            and indexed["sha256"] == trace["sha256"]
            and indexed["size_bytes"] == trace["size_bytes"]
            and indexed["media_type"] == trace["media_type"]
            and (
                "segment_index" not in trace
                or indexed.get("segment_index") == trace["segment_index"]
            )
            for indexed in _document(artifact)["artifacts"]
        ):
            _fail(f"transport trace does not match evidence index for domain {domain_id}")


def _validate_evidence(
    grouped: Mapping[str, Sequence[_Artifact]],
    evidence_indexes: Mapping[str, _Artifact],
    recording_summaries: Mapping[str, _Artifact],
) -> None:
    referenced_summaries: dict[str, tuple[str, int]] = {}
    for domain_id, index_artifact in evidence_indexes.items():
        for artifact in _document(index_artifact)["artifacts"]:
            kinds = ("recording",) if artifact["kind"] == "recording" else None
            _require_raw(
                grouped,
                artifact["sha256"],
                f"evidence index {domain_id} artifact {artifact['artifact_id']}",
                kinds=kinds,
                size_bytes=artifact["size_bytes"],
            )
            if "recording_summary" in artifact:
                summary = artifact["recording_summary"]
                reference = (
                    artifact["sha256"],
                    summary["size_bytes"],
                )
                previous = referenced_summaries.setdefault(summary["sha256"], reference)
                if previous != reference:
                    _fail("one recording summary cannot describe multiple evidence sources")

    summaries_by_digest = {artifact.sha256: artifact for artifact in recording_summaries.values()}
    if set(referenced_summaries) != set(summaries_by_digest):
        _fail("recording summaries do not exactly match evidence-index references")
    for digest, (source_digest, expected_size) in referenced_summaries.items():
        summary = summaries_by_digest[digest]
        if summary.size_bytes != expected_size:
            _fail("recording summary size does not match its evidence-index reference")
        if _document(summary)["source_sha256"] != source_digest:
            _fail("recording summary source does not match its evidence segment")


def _validate_links(artifacts: Sequence[_Artifact]) -> tuple[str, str]:
    """Validate cross-document links after each contract has passed schema validation."""

    subject_names = [artifact.subject_name for artifact in artifacts]
    if len(subject_names) != len(set(subject_names)):
        _fail("qualification subject names must be unique")
    grouped: dict[str, list[_Artifact]] = defaultdict(list)
    for artifact in artifacts:
        grouped[artifact.kind].append(artifact)

    scenario_artifact = _one(grouped, "scenario", "scenario.json")
    run_artifact = _one(grouped, "acceptance_run", "acceptance-run.json")
    aggregate_artifact = _one(grouped, "acceptance_aggregate", "acceptance-aggregate.json")
    runtimes = _labeled(grouped, "runtime_manifest", "runtime-manifests/")
    results = _labeled(grouped, "domain_result", "results/")
    evidence_indexes = _labeled(grouped, "evidence_index", "evidence-indexes/")
    recording_summaries = _labeled(grouped, "recording_summary", "recording-summaries/")

    scenario = _document(scenario_artifact)
    acceptance_run = _document(run_artifact)
    aggregate = _document(aggregate_artifact)
    run_id = acceptance_run["run_id"]
    run_created_at = acceptance_run["created_at"]
    aggregate_generated_at = aggregate["generated_at"]
    run_domains = {item["domain_id"] for item in acceptance_run["domains"]}
    for label, expected_value, actual_value in (
        ("acceptance run scenario_id", scenario["scenario_id"], acceptance_run["scenario_id"]),
        (
            "acceptance run scenario digest",
            scenario_artifact.sha256,
            acceptance_run["scenario_sha256"],
        ),
        ("aggregate run_id", run_id, aggregate["run_id"]),
        (
            "aggregate acceptance run digest",
            run_artifact.sha256,
            aggregate["acceptance_run_sha256"],
        ),
    ):
        _require_equal(label, expected_value, actual_value)
    for name, values in (
        ("runtime manifest", runtimes),
        ("domain result", results),
        ("evidence index", evidence_indexes),
    ):
        if set(values) != run_domains:
            _fail(f"{name} set does not equal acceptance run domains")
    aggregate_results = {
        item["domain_id"]: {
            "result_id": item["result_id"],
            "result_sha256": item["result_sha256"],
            "status": item["status"],
        }
        for item in aggregate["per_domain_results"]
    }
    local_results: dict[str, dict[str, Any]] = {}
    for domain_id, artifact in results.items():
        result = _document(artifact)
        runtime = _document(runtimes[domain_id])
        evidence_index = _document(evidence_indexes[domain_id])
        _require_time_order(
            f"qualification timeline for {domain_id}",
            run_created_at,
            runtime["generated_at"],
            result["started_at"],
            evidence_index["generated_at"],
            result["finished_at"],
            aggregate_generated_at,
        )
        for label, expected_value, actual_value in (
            ("run_id", run_id, result["run_id"]),
            ("domain_id", domain_id, result["domain_id"]),
            ("scenario_id", scenario["scenario_id"], result["scenario_id"]),
            ("scenario digest", scenario_artifact.sha256, result["scenario_sha256"]),
            (
                "runtime manifest digest",
                runtimes[domain_id].sha256,
                result["runtime_manifest_sha256"],
            ),
        ):
            _require_equal(f"result {domain_id} {label}", expected_value, actual_value)
        _validate_execution_alignment(
            scenario,
            acceptance_run,
            runtime,
            result,
            domain_id,
        )
        declared_assertions = {item["assertion_id"] for item in scenario["assertions"]}
        result_assertions = {item["assertion_id"] for item in result["assertion_results"]}
        missing_assertions = declared_assertions - result_assertions
        if missing_assertions:
            _fail(f"result {domain_id} omits scenario assertions: {sorted(missing_assertions)}")
        indexed_artifacts = _document(evidence_indexes[domain_id])["artifacts"]
        evidence_fields = (
            "artifact_id",
            "kind",
            "uri",
            "immutable_revision",
            "receipt_sha256",
            "sha256",
            "size_bytes",
            "media_type",
            "retention_class",
        )

        result_evidence = {
            item["artifact_id"]: _project_fields(item, evidence_fields)
            for item in result["evidence"]
        }
        indexed_evidence = {
            item["artifact_id"]: _project_fields(item, evidence_fields)
            for item in indexed_artifacts
        }
        indexed_segments = {
            item["artifact_id"]: item.get("segment_index") for item in indexed_artifacts
        }
        if result_evidence != indexed_evidence or any(
            "segment_index" in item
            and item["segment_index"] != indexed_segments[item["artifact_id"]]
            for item in result["evidence"]
        ):
            _fail(f"result {domain_id} evidence does not exactly match its index")
        local_results[domain_id] = {
            "result_id": result["result_id"],
            "result_sha256": artifact.sha256,
            "status": result["status"],
        }
    if local_results != aggregate_results:
        _fail("aggregate per_domain_results do not exactly match local results")

    for domain_id, artifact in evidence_indexes.items():
        _require_equal(f"evidence index {domain_id} run_id", run_id, _document(artifact)["run_id"])

    _validate_provider_bindings(grouped, scenario, run_id, runtimes, run_created_at)
    _validate_receipts(
        grouped,
        scenario,
        run_id,
        evidence_indexes,
        run_created_at,
        aggregate_generated_at,
    )
    _validate_model_and_dataset(grouped, scenario, runtimes, results)
    _validate_retained_configuration(grouped, scenario, acceptance_run, runtimes)
    _validate_physical_authorization(grouped, scenario_artifact, runtimes, results)
    _validate_evidence(grouped, evidence_indexes, recording_summaries)
    _validate_transport(
        grouped,
        run_id,
        run_domains,
        scenario_artifact,
        aggregate,
        evidence_indexes,
        results,
        run_created_at,
        aggregate_generated_at,
    )
    return run_id, aggregate["generated_at"]


def _load_artifact(
    specification: str,
    extension_schemas: Mapping[str, bytes],
) -> _Artifact:
    kind, kind_separator, remainder = specification.partition(":")
    subject_name, path_separator, path_value = remainder.partition("=")
    if not kind_separator or not path_separator or not kind or not subject_name or not path_value:
        _fail("--artifact must use KIND:SUBJECT=PATH")
    if kind not in _CONTRACT_SCHEMAS and kind not in _RAW_ARTIFACT_KINDS:
        _fail(f"unsupported qualification artifact kind: {kind}")
    if not _SUBJECT_NAME.fullmatch(subject_name) or ".." in subject_name or "//" in subject_name:
        _fail(f"non-canonical qualification subject name: {subject_name}")

    path = Path(path_value)
    raw = path.read_bytes()
    document = None
    if kind in _CONTRACT_SCHEMAS:
        try:
            document = loads_mapping(raw, source_name=str(path))
        except ValueError as error:
            _fail(str(error))
        schema = document.get("schema_version")
        if not isinstance(schema, str) or schema not in _CONTRACT_SCHEMAS[kind]:
            _fail(
                f"{path}: unsupported {kind} schema_version {schema!r}; "
                f"expected one of {sorted(_CONTRACT_SCHEMAS[kind])}"
            )
        try:
            validate_document(
                document,
                schema=schema,
                extension_schemas=((extension_schemas or None) if kind == "scenario" else None),
            )
        except ValueError as error:
            raise QualificationError(
                f"{path} does not satisfy {schema}: {error}",
                error_id=getattr(error, "error_id", None),
                json_path=getattr(error, "json_path", None),
            ) from error
    return _Artifact(kind, subject_name, hashlib.sha256(raw).hexdigest(), len(raw), document)


def validate_qualification_artifacts(
    specifications: Sequence[str],
    extension_schemas: Mapping[str, bytes] | None = None,
) -> dict[str, Any]:
    """Validate one artifact set and return metadata for the exact bytes read."""

    artifacts = [
        _load_artifact(specification, extension_schemas or {}) for specification in specifications
    ]
    run_id, generated_at = _validate_links(artifacts)
    return {
        "run_id": run_id,
        "generated_at": generated_at,
        "artifacts": [
            {
                "kind": item.kind,
                "subject_name": item.subject_name,
                "sha256": item.sha256,
            }
            for item in sorted(artifacts, key=lambda item: item.subject_name)
        ],
    }
