from __future__ import annotations

from collections.abc import Iterable, Mapping, Set
from typing import Any, Literal

ChannelObservationStatus = Literal["passed", "failed", "incomplete", "error"]


class ClockEvidenceValidationError(ValueError):
    """Raised when a clock relation references evidence from the wrong domain."""


def validate_clock_relation_evidence(
    relation: Mapping[str, Any],
    evidence_sha256_by_domain: Mapping[str, Set[str]],
) -> None:
    """Validate retained clock evidence, including endpoint ownership."""

    retained = set().union(*evidence_sha256_by_domain.values())
    if relation["evidence_sha256"] not in retained:
        raise ClockEvidenceValidationError("clock relation references unretained evidence")
    if relation["method"] != "shared_clock_identity":
        return

    source_domain = str(relation["source_domain_id"])
    destination_domain = str(relation["destination_domain_id"])
    identity = relation["shared_clock_identity"]
    for domain_id, field in (
        (source_domain, "source_observation_sha256"),
        (destination_domain, "destination_observation_sha256"),
    ):
        domain_evidence = evidence_sha256_by_domain.get(domain_id)
        if domain_evidence is None or identity[field] not in domain_evidence:
            raise ClockEvidenceValidationError(
                f"{field.removesuffix('_sha256')} is not retained by domain {domain_id}"
            )


CHANNEL_ERROR_VIOLATIONS = frozenset(
    {
        "ambiguous_message_id",
        "invalid_observation",
        "observation_window_exceeded",
    }
)
CHANNEL_INCOMPLETE_VIOLATIONS = frozenset({"insufficient_messages"})

RESERVED_ASSERTION_IDS = frozenset(
    {
        "data-plane-data-sharing",
        "data-plane-fastdds-profile",
        "data-plane-loss-ratio",
        "data-plane-message-age",
        "data-plane-private-ipc",
        "data-plane-sequence-integrity",
        "data-plane-shm-transport",
        "policy-evidence-compression",
        "policy-evidence-recording-mode",
        "policy-evidence-remote-sink",
        "policy-evidence-retention",
        "policy-evidence-segment-duration",
        "policy-evidence-segment-size",
        "policy-evidence-spool-size",
        "policy-evidence-spool-watermark",
        "policy-evidence-topics",
        "policy-evidence-upload-lag",
        "policy-evidence-upload-mode",
        "time-policy",
    }
)

RESERVED_METRIC_NAMES = frozenset(
    {
        "robotics.clock.source",
        "robotics.clock.sync_protocol",
        "robotics.hardware.clock.drift",
        "robotics.hardware.clock.monotonic",
        "robotics.hardware.clock.offset",
        "robotics.hardware.message.age",
        "robotics.inference.latency",
        "robotics.message.age",
        "robotics.message.loss_ratio",
        "robotics.message.lost",
        "robotics.message.received",
        "robotics.message.sequence_error",
        "robotics.simulation.deadline_miss_ratio",
        "robotics.time_authority.delivery_latency",
    }
)


def channel_observation_status(violation_codes: Iterable[str]) -> ChannelObservationStatus:
    """Classify a channel observation from its canonical violation codes."""

    codes = frozenset(violation_codes)
    if not codes:
        return "passed"
    if codes & CHANNEL_ERROR_VIOLATIONS:
        return "error"
    if codes <= CHANNEL_INCOMPLETE_VIOLATIONS:
        return "incomplete"
    return "failed"


def derive_channel_violations(
    delivery: Mapping[str, Any],
    *,
    sent_count: int,
    loss_ratio: float,
    duplicate_count: int,
    out_of_order_count: int,
    max_message_age_ms: float,
    observation_duration_sec: float,
    reported_violation_codes: Iterable[str] = (),
) -> frozenset[str]:
    """Derive the canonical delivery violations from measured counters."""

    failed = {
        code
        for code, passed in (
            ("insufficient_messages", sent_count >= delivery["minimum_source_messages"]),
            ("loss_ratio_exceeded", loss_ratio <= delivery["max_loss_ratio"]),
            (
                "duplicate_count_exceeded",
                duplicate_count <= delivery["max_duplicate_count"],
            ),
            (
                "out_of_order_count_exceeded",
                out_of_order_count <= delivery["max_out_of_order_count"],
            ),
            (
                "message_age_exceeded",
                max_message_age_ms <= delivery["max_message_age_ms"],
            ),
            (
                "observation_window_exceeded",
                observation_duration_sec <= delivery["observation_window_sec"],
            ),
        )
        if not passed
    }
    reported = frozenset(reported_violation_codes)
    return frozenset(failed | (reported & CHANNEL_ERROR_VIOLATIONS))


def hardware_clock_within_policy(
    time_policy: Mapping[str, Any],
    observation: Mapping[str, Any],
    *,
    monotonic: bool,
) -> bool:
    """Evaluate the canonical physical-clock qualification predicate."""

    return bool(
        monotonic
        and observation["sample_count"] >= time_policy["time_authority_min_samples"]
        and abs(observation["offset_ms"]) <= time_policy["max_clock_offset_ms"]
        and abs(observation["drift_ppm"]) <= time_policy["max_clock_drift_ppm"]
        and observation["max_sample_age_ms"] <= time_policy["max_message_age_ms"]
    )


__all__ = [
    "CHANNEL_ERROR_VIOLATIONS",
    "CHANNEL_INCOMPLETE_VIOLATIONS",
    "RESERVED_ASSERTION_IDS",
    "RESERVED_METRIC_NAMES",
    "ChannelObservationStatus",
    "ClockEvidenceValidationError",
    "channel_observation_status",
    "derive_channel_violations",
    "hardware_clock_within_policy",
    "validate_clock_relation_evidence",
]
