# Security Policy

## Current posture
The prototype is fixture-only. It does not execute submitted code, install challenge dependencies, access the network, invoke external agents, or read arbitrary host files.

The bundled Python fixture contains an intentionally unsafe `eval` example. It is data for inspection only and must never be executed.

## Reporting
Do not publish secrets or exploit details in public issues. Use GitHub private vulnerability reporting when enabled.

## Future execution backends
External agent execution is out of scope until a threat model, sandbox design, resource limits, permission model, and adversarial tests are reviewed. Containers alone are not treated as a complete isolation boundary.
