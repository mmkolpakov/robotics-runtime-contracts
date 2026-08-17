from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum


class OutcomeStatus(StrEnum):
    PASSED = "passed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    INCOMPLETE = "incomplete"
    FAILED = "failed"
    ERROR = "error"


_PRIORITY = {status: priority for priority, status in enumerate(OutcomeStatus)}


def worst_status(
    statuses: Iterable[str | OutcomeStatus],
    *,
    collapse_cancelled: bool = False,
) -> str:
    """Return the deterministic worst outcome from a non-empty collection."""

    values = tuple(OutcomeStatus(status) for status in statuses)
    if not values:
        raise ValueError("at least one status is required")
    status = max(values, key=_PRIORITY.__getitem__)
    if collapse_cancelled and status is OutcomeStatus.CANCELLED:
        return OutcomeStatus.INCOMPLETE.value
    return status.value
