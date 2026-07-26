# Consumer Examples

These documents form a neutral, single-domain simulation exchange. They show
how a consumer can declare a scenario, describe the observed runtime, establish
one run context, report one domain result, index evidence, and aggregate the
result.

Every YAML document declares its own `schema_version`. CI validates all files
in this directory with the released Python API:

```bash
uv run pytest tests/test_consumer_examples.py
```

Consumers should copy only the document types they produce or consume.
Identifiers, image references, timestamps, and ROS graph observations are
examples and must be replaced with observed data. The SHA-256 fields that link
files in `minimal-simulation/` are the actual digests of those files, and CI
recomputes the complete acyclic chain. A successful result contains evaluated
assertions and evidence; observation digests identify the corresponding item in
both the result and the evidence index.
