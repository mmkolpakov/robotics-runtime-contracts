from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

type JsonScalar = str | int | float | bool


def migrate_scenario_v1_to_v2(
    scenario: Mapping[str, Any],
    *,
    metric_attributes: Mapping[str, Mapping[str, JsonScalar]],
    time_authority_min_samples: int,
    max_clock_offset_p50_ms: float,
    max_clock_offset_p95_ms: float,
    max_clock_offset_ms: float,
) -> dict[str, Any]:
    """Migrate a v1 scenario without inventing metric selectors or timing policy."""

    if scenario.get("schema_version") != "acceptance-scenario.v1":
        raise ValueError("scenario must declare acceptance-scenario.v1")

    migrated = deepcopy(dict(scenario))
    migrated["schema_version"] = "acceptance-scenario.v2"
    for assertion in migrated["assertions"]:
        if assertion["kind"] != "metric":
            continue
        assertion_id = assertion["assertion_id"]
        try:
            attributes = metric_attributes[assertion_id]
        except KeyError as error:
            raise ValueError(f"metric_attributes is missing assertion {assertion_id!r}") from error
        if not attributes:
            raise ValueError(f"metric_attributes[{assertion_id!r}] must not be empty")
        assertion["attribute_match"] = dict(attributes)

    time_policy = migrated["time_policy"]
    time_policy.update(
        {
            "time_authority_min_samples": time_authority_min_samples,
            "max_clock_offset_p50_ms": max_clock_offset_p50_ms,
            "max_clock_offset_p95_ms": max_clock_offset_p95_ms,
            "max_clock_offset_ms": max_clock_offset_ms,
        }
    )
    return migrated


__all__ = ["JsonScalar", "migrate_scenario_v1_to_v2"]
