# Migrating Acceptance Scenarios from v1 to v2

`acceptance-scenario.v1` remains supported and byte-for-byte unchanged. Version
2 makes execution mode, physical scope, time, data transport, security, and
evidence retention explicit. Migration is intentional; no implicit conversion
is performed at runtime.

## Field Mapping

| Version 1 | Version 2 | Required action |
| --- | --- | --- |
| `schema_version` | `schema_version` | Set `acceptance-scenario.v2` |
| `scenario_id` | `scenario_id` | Keep the stable identifier |
| `target_environment` | `execution.target_environment` | Move under `execution` |
| Not represented | `execution.hardware_scope` | Declare physical compute, sensor, controller, or actuator access |
| Not represented | `execution.physical_effect` | Declare `none`, `observation`, or `actuation` |
| Not represented | `execution.test_intent` | Declare interface, functional, performance, or safety intent |
| Not represented | `execution.data_source` | Select Gazebo, MCAP playback, or a live target |
| Not represented | `execution.plant_backend` | Select mock, Gazebo physics, recorded data, or real hardware |
| Not represented | `execution.time_mode` | Select real-time simulation, stepped simulation, playback, or hardware time |
| Not represented | `execution.data_plane_profile` | Select isolated, local high-throughput, or secure shared-memory transport |
| Not represented | `execution.security_profile` | Select no ROS security or SROS2 Enforce |
| `seed` | `seed` | Keep the deterministic seed |
| `timeouts.*` | `timeouts.*` | Add `stable_for_sec` |
| `expected_ros_graph.stable_for_sec` | `timeouts.stable_for_sec` | Move the graph stability window |
| `expected_ros_graph.topics` | `expected_ros_graph.topics` | Add first-message timeout and optional QoS profile |
| `expected_ros_graph.services` | `expected_ros_graph.services` | Add `server_required: true` |
| `expected_ros_graph.actions` | `expected_ros_graph.actions` | Add `server_required: true` |
| Not represented | `expected_ros_graph.lifecycle_nodes` | Declare managed nodes that must be active |
| Not represented | `assertions` | Add machine-evaluated metric assertions |
| Not represented | `time_policy` | Add limits for the selected time mode |
| Not represented | `data_plane_policy` | Add latency, loss, SHM, and IPC requirements |
| Not represented | `evidence_policy` | Add bounded MCAP recording, spool, upload, and retention rules |
| `extensions` | `extension_schemas` and `extensions` | Pin every extension schema by URI and SHA-256 |

## Fixed Execution Combinations

| Data source | Target | Plant | Time mode |
| --- | --- | --- | --- |
| `gazebo` | `simulation` | `gazebo_physics` | `simulation_realtime` or `simulation_stepped` |
| `mcap_playback` | `simulation` | `recorded_data` | `playback_clocked` |
| `live_target` | `hil` or `real_robot` | `real_hardware` | `hardware_realtime` |

`interface_mock` is restricted to `interface_smoke` and cannot support a
physical business verdict. HIL forbids actuator scope and physical effect. HIL
and real-robot runs require SROS2 Enforce. Local high-throughput transport is an
unsecured same-host profile; secure shared memory uses SROS2 with Fast DDS Data
Sharing disabled.

## Validator Migration

Version 1 callers may remain unchanged:

```python
from robotics_runtime_contracts import validate_scenario

validate_scenario(v1_scenario)
```

Version 2 and manifest callers use schema dispatch:

```python
from robotics_runtime_contracts import validate_document

validate_document(v2_scenario)
```

When a scenario declares `extension_schemas`, provide the exact schema bytes in
the `extension_schemas` argument. The validator compares SHA-256, requires the
declared URI to equal `$id`, and rejects network references.

## Migration Gate

A migrated scenario is ready when:

1. `validate_document()` succeeds without suppressions.
2. The selected runtime publishes a matching `runtime-manifest.v1`.
3. Playback scenarios reference a valid `dataset-manifest.v1` digest.
4. Model-backed scenarios reference a valid `model-artifact-manifest.v1` digest.
5. HIL and real-robot runs carry a separately verified `execution-permit.v1`.
6. The resulting `acceptance-result.v1` repeats the same execution facts and
   content digests.
