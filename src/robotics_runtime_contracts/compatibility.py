from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

_REQUIREMENTS: Mapping[str, Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        "acceptance-scenario.v4": MappingProxyType(
            {
                "runtime_manifest": frozenset({"runtime-manifest.v1", "runtime-manifest.v2"}),
                "domain_result": frozenset({"acceptance-result.v4", "acceptance-result.v5"}),
                "evidence_index": frozenset({"evidence-index.v2", "evidence-index.v3"}),
                "transport_qualification": frozenset({"transport-qualification-result.v1"}),
            }
        ),
        "acceptance-scenario.v5": MappingProxyType(
            {
                "runtime_manifest": frozenset({"runtime-manifest.v3"}),
                "domain_result": frozenset({"acceptance-result.v5"}),
                "evidence_index": frozenset({"evidence-index.v3"}),
                "transport_qualification": frozenset({"transport-qualification-result.v2"}),
            }
        ),
    }
)


class SchemaCompatibilityError(ValueError):
    """Raised when individually valid contract versions cannot form one bundle."""

    error_id = "schema.incompatible"

    def __init__(
        self,
        scenario_schema: str,
        artifact_kind: str,
        expected_schemas: frozenset[str],
        observed_schema: str,
    ) -> None:
        self.scenario_schema = scenario_schema
        self.artifact_kind = artifact_kind
        self.expected_schemas = expected_schemas
        self.observed_schema = observed_schema
        expected = sorted(expected_schemas)
        requirement = expected[0] if len(expected) == 1 else f"one of {expected}"
        super().__init__(
            f"{scenario_schema} requires {requirement} for {artifact_kind}; "
            f"received {observed_schema}"
        )


class UnknownCompatibilityRuleError(ValueError):
    """Raised when no compatibility rule exists for a public API request."""

    error_id = "schema.compatibility_rule_unknown"


def allowed_companion_schemas(scenario_schema: str, artifact_kind: str) -> frozenset[str]:
    """Return the companion schemas accepted by a scenario version."""

    try:
        return _REQUIREMENTS[scenario_schema][artifact_kind]
    except KeyError as error:
        raise UnknownCompatibilityRuleError(
            f"no compatibility rule for {scenario_schema} and {artifact_kind}"
        ) from error


def validate_companion_schema(
    scenario_schema: str,
    artifact_kind: str,
    observed_schema: str,
) -> None:
    """Reject a companion document that violates the published version matrix."""

    expected = allowed_companion_schemas(scenario_schema, artifact_kind)
    if observed_schema not in expected:
        raise SchemaCompatibilityError(
            scenario_schema,
            artifact_kind,
            expected,
            observed_schema,
        )
