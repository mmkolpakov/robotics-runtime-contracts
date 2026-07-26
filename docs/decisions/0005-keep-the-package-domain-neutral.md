# Keep the Package Domain Neutral

- Status: accepted
- Date: 2026-07-26

## Context and Problem Statement

The same execution and evidence boundary must be reusable across robotics
products without importing scenes, robot descriptions, model taxonomies,
control behavior, or product acceptance thresholds.

## Decision Drivers

- Independent release lifecycle
- Reuse across robot classes
- Stable common vocabulary
- Clear ownership of product rules

## Considered Options

- Put product scenarios in the package
- Maintain separate common packages for each robot class
- Keep common contracts neutral and let consumers own domain documents

## Decision Outcome

The package contains only versioned execution, runtime, evidence,
authorization, and result contracts plus their validation API. Consumer
repositories own worlds, robots, launch files, model artifacts, control logic,
and product acceptance rules.

### Consequences

- Consumer examples remain generic and contain no product decision logic.
- Domain-specific data uses consumer-owned extensions or schemas.
- The package cannot start a runtime or issue a physical command.
