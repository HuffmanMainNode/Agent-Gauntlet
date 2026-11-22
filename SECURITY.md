# Security Policy

## Current execution boundary

Agent Gauntlet has two distinct execution paths:

- The fixture runner uses bundled demonstration agents and does not invoke an external model or participant command.
- The adversarial runner executes an operator-configured command adapter on the operator's machine using `subprocess.run`, without a shell, with a timeout, and with a minimal environment. It starts a separate process for each seed. This is **not a sandbox**. The adapter can access resources available to its operating-system identity, including files and network access, subject to the host environment.

Do not run untrusted adapters on a workstation, CI runner, or host containing credentials, private repositories, personal data, or production access. Use a disposable environment with no secrets, restricted filesystem mounts, restricted network egress, and strict resource limits. These controls must be configured outside Agent Gauntlet today. Process groups, resource limits, and namespace isolation may be added as defense-in-depth controls, but must not be represented as a secure boundary against hostile code without a separately reviewed isolation design.

The bundled Python fixture contains an intentionally unsafe `eval` example. It is data for inspection only and must never be executed.

## Evidence limitations

SHA-256 artifact digests detect accidental or later content changes relative to the manifest. The manifests are unsigned. A submitter can create a new internally consistent bundle; hashes do not authenticate the model, operator, runtime, or honesty of execution. The verifier recomputes deterministic cases and scoring, but it cannot establish semantic truth or independently observe an external model.

## Reporting

Do not publish secrets or exploit details in public issues. Use GitHub private vulnerability reporting when enabled.

## Future execution backend

A hardened sandbox is a separate security project requiring a threat model, isolation architecture, resource limits, network egress policy, permission model, escape testing, and independent review. Containers alone are not treated as a complete isolation boundary.
