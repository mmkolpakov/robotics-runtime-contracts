# Keep Device and Workload Identities Distinct

- Status: accepted
- Date: 2026-07-26

## Context and Problem Statement

Physical-target authorization and software-workload authentication identify
different subjects. A workload identity such as a
[SPIFFE ID](https://spiffe.io/docs/latest/spiffe-about/spiffe-concepts/)
does not prove the identity of a controller, sensor, or compute device.

## Decision Drivers

- Fail-closed physical-target binding
- Clear verification provenance
- Compatibility with workload identity systems
- No overloaded identity field

## Considered Options

- Use one free-form identity for every subject
- Treat workload identity as physical-device identity
- Record target fingerprints and signer identities separately

## Decision Outcome

Physical targets use their declared identity kind and SHA-256 fingerprint.
Permit verification records signer identities separately. A SPIFFE ID may
identify a verifier or other software workload, but it does not replace the
physical target fingerprint.

### Consequences

- Authorization must bind both trusted signers and the intended target.
- Workload-identity adoption does not change device identity semantics.
- New identity kinds require a new schema version.
