from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal

ChannelObservationStatus = Literal["passed", "failed", "incomplete", "error"]

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
    "ChannelObservationStatus",
    "channel_observation_status",
    "hardware_clock_within_policy",
]
