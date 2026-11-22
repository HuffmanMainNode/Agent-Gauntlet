# Security Policy

## Current execution boundary

Agent Gauntlet has two distinct execution paths:

- The fixture runner uses bundled demonstration agents and does not invoke an external model or participant command.
- The adversarial runner executes an operator-configured command adapter through the POSIX containment helper. It starts a separate process for each seed, uses `shell=False`, a scrubbed environment, a temporary working directory, process-group cleanup, bounded stdout/stderr capture, wall-clock timeouts, and configured POSIX resource limits. Best-effort mode attempts Linux user/network/PID namespaces when the host capability probe succeeds; strict mode fails closed if that probe fails. The interactive tool-loop has resource limits and strict namespace enforcement, but its best-effort namespace behavior is not yet unified with the single-turn supervisor. These controls are defense-in-depth, **not a filesystem sandbox**. The adapter can still access host files available to its operating-system identity; network isolation depends on whether namespaces are active.

Do not run untrusted adapters on a workstation, CI runner, or host containing credentials, private repositories, personal data, or production access. Use a disposable VM or independently configured OS sandbox with no secrets, restricted filesystem mounts, restricted network egress, and strict resource limits. Agent Gauntlet's temporary directory is only a working directory; it does not restrict filesystem visibility. Process groups, resource limits, and namespaces are defense-in-depth controls, not a secure boundary against hostile code without a separately reviewed isolation design.

The bundled Python fixture contains an intentionally unsafe `eval` example. It is data for inspection only and must never be executed.

## Evidence limitations

SHA-256 artifact digests detect content changes relative to the manifest. Evidence bundles are unsigned by default. Public scorecards can carry detached OpenSSH signatures that bind the provenance root, pack-result hashes, and a canonical digest of all public scorecard claims. A signature authenticates the key holder's signed declaration only; it does not authenticate the agent, model provider, runtime, operator's honesty, or semantic truth. The local leaderboard gate verifies the signature and internal consistency but does not fetch external evidence archives or independently replay remote adapter runs.

## Reporting

Do not publish secrets or exploit details in public issues. Use GitHub private vulnerability reporting when enabled.

## Future execution backend

A hardened filesystem/process sandbox remains a separate security project requiring a threat model, isolation architecture, mount or pivot-root controls, network egress policy, permission model, escape testing, and independent review. Containers alone are not treated as a complete isolation boundary.
