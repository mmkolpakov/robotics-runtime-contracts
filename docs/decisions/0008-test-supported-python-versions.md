# Test the Declared Python Support Range

- Status: accepted
- Date: 2026-09-07
- Decision: Python support portion of D4 in the approved implementation specification

## Context and Problem Statement

The package declared Python 3.12 or newer while its CI and classifiers covered
only 3.12. An unrestricted requirement did not describe the tested range.

## Decision Outcome

Declare `>=3.12,<3.15` and test 3.12, 3.13 and 3.14 explicitly. Each CI matrix
entry selects its interpreter despite the local `.python-version` pin, runs
the suite, and checks installation of the built wheel and source distribution.
Keep `.python-version` and the release build on the minimum, 3.12.

## Consequences

Adding another Python minor requires updating the matrix, package metadata and
documentation together. Linux hosted results qualify that platform only; local
Windows runs do not substitute for the GitHub Actions gate. This decision does
not change or qualify any ROS/Gazebo combination in a consumer repository.
