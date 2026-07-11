# Runtime and Result Workloads

`runtime-manifest.v1` and `acceptance-result.v1` describe model-backed runs and
remain immutable. Version 2 removes the need for a fictitious model in physics,
sensor, controller, and data-plane acceptance runs.

## No Inference

Use an explicit empty workload:

```yaml
schema_version: runtime-manifest.v2
workload:
  kind: none
```

The corresponding result uses the same shape:

```yaml
schema_version: acceptance-result.v2
workload:
  kind: none
```

No model manifest digest, provider, accelerator, or fallback count is emitted.

## Inference

Model-backed runtime facts move under `workload` without changing their v1
meaning:

```yaml
schema_version: runtime-manifest.v2
workload:
  kind: inference
  model:
    manifest_sha256: <sha256>
    artifact_sha256: <sha256>
    format: onnx
  inference:
    runtime_family: onnxruntime_cpu
    runtime_version: 1.27.0
    requested_provider: CPUExecutionProvider
    actual_provider: CPUExecutionProvider
    fallback_count: 0
  accelerator:
    vendor: none
    device_class: cpu
    device_id: host-cpu
```

`acceptance-result.v2` places the observed runtime family, provider, model
format, and fallback count under its own `workload`. An inference result must
carry `model_manifest_sha256`.

## Compatibility Rule

New producers use v2. Existing v1 documents continue to validate unchanged.
Consumers must dispatch on `schema_version`; they must not infer the absence of
inference from missing v1 fields or synthesize placeholder model identities.
