# Security Policy

## Supported Versions

Security fixes are applied to the latest released package and schema set.
Published schema bytes remain immutable; a security-related contract change is
released under a new schema version.

## Security Boundary

This package validates caller-provided documents. It does not fetch schemas,
start ROS nodes, issue commands, verify live device state, or authorize an
execution by itself. A structurally valid permit or verification document is
data for a policy-enforcement component, not proof that enforcement occurred.

Physical-target fingerprints and software signer identities are separate trust
subjects. The governing decision is
[ADR 0004](docs/decisions/0004-separate-device-and-workload-identities.md).

## Reporting a Vulnerability

Report vulnerabilities through
[GitHub private vulnerability reporting](https://github.com/mmkolpakov/robotics-runtime-contracts/security/advisories/new).
Do not disclose a vulnerability in a public issue.

Include the affected version, a minimal reproduction, and the expected security
boundary. Remove credentials, signing keys, private datasets, device serials,
and production endpoint details. An initial response is expected within seven
days; disclosure timing is coordinated after impact and remediation are known.
