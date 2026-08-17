# Separate Transport Qualification from Acceptance Aggregation

- Status: accepted
- Date: 2026-07-31

## Context and Problem Statement

The acceptance aggregate previously embedded the complete transport evidence
graph already published by `transport-qualification-result.v1`. This created
two owners for channel observations, causal chains, trace evidence, and their
verdict semantics.

## Decision Drivers

- One canonical owner for each evidence model
- Independent transport qualification
- Small, digest-addressed aggregate documents
- Reuse across single-domain and multi-domain products

## Considered Options

- Keep both complete representations synchronized
- Extract shared JSON Schema definitions while retaining duplicate documents
- Reference the transport result from the acceptance aggregate

## Decision Outcome

`transport-qualification-result.v1` remains the sole owner of transport
evidence and its verdict. `acceptance-aggregate.v1` contains per-domain
results and, when available, the transport result identifier, digest, and
status. The aggregate status is derived from the domain and transport
statuses.

### Consequences

- Transport evidence is validated once and reused by digest.
- Aggregation no longer copies channels, traces, or causal chains.
- Consumers compose the final aggregate from domain results and an optional
  transport qualification.
