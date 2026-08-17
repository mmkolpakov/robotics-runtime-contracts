from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class ProviderRequirementError(ValueError):
    """Raised when runtime provider bindings do not satisfy a scenario."""


def _json_scalar_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    return bool(left == right)


def scene_satisfies(requirement: Mapping[str, Any], scene: Mapping[str, Any]) -> bool:
    """Return whether one observed scene satisfies one complete requirement."""

    return (
        scene["semantic_scene_id"] == requirement["semantic_scene_id"]
        and set(requirement["required_entities"]) <= set(scene["entities"])
        and set(requirement["required_interfaces"]) <= set(scene["interfaces"])
        and all(
            _json_scalar_equal(scene["physical_parameters"].get(key), value)
            for key, value in requirement.get("physical_parameters", {}).items()
        )
    )


def validate_provider_requirements(
    requirements: Mapping[str, Any],
    bindings: Sequence[Mapping[str, Any]],
) -> None:
    """Validate provider capabilities and one complete semantic scene."""

    capabilities = {
        str(capability) for binding in bindings for capability in binding["capabilities"]
    }
    missing = set(requirements["capabilities"]) - capabilities
    if missing:
        raise ProviderRequirementError(
            f"provider bindings do not satisfy capabilities; missing {sorted(missing)}"
        )

    scene_requirement = requirements.get("scene")
    if scene_requirement is not None and not any(
        scene_satisfies(scene_requirement, scene)
        for binding in bindings
        if (scene := binding.get("scene")) is not None
    ):
        raise ProviderRequirementError(
            "provider bindings do not satisfy the scene; no single provider scene "
            "satisfies the requirement"
        )


__all__ = [
    "ProviderRequirementError",
    "scene_satisfies",
    "validate_provider_requirements",
]
