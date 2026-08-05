from __future__ import annotations

import pytest

from robotics_runtime_contracts import (
    channel_observation_status,
    hardware_clock_within_policy,
)


@pytest.mark.parametrize(
    ("violations", "expected"),
    [
        (set(), "passed"),
        ({"loss_ratio_exceeded"}, "failed"),
        ({"insufficient_messages"}, "incomplete"),
        ({"ambiguous_message_id"}, "error"),
        ({"observation_window_exceeded", "loss_ratio_exceeded"}, "error"),
    ],
)
def test_channel_observation_status_is_canonical(
    violations: set[str],
    expected: str,
) -> None:
    assert channel_observation_status(violations) == expected


def test_hardware_clock_policy_requires_samples_monotonicity_and_thresholds() -> None:
    policy = {
        "time_authority_min_samples": 10,
        "max_clock_offset_ms": 2,
        "max_clock_drift_ppm": 5,
        "max_message_age_ms": 20,
    }
    observation = {
        "sample_count": 10,
        "offset_ms": -2,
        "drift_ppm": 5,
        "max_sample_age_ms": 20,
    }

    assert hardware_clock_within_policy(policy, observation, monotonic=True)
    assert not hardware_clock_within_policy(policy, observation, monotonic=False)
    assert not hardware_clock_within_policy(
        policy,
        {**observation, "sample_count": 9},
        monotonic=True,
    )
