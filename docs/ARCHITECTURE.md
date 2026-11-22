# Architecture

Agent Gauntlet is local-first and offline-capable. The package runtime uses the Python 3.11+ standard library. The optional development test dependency is pytest.

## Implemented execution paths

### Bundled fixture runner
Challenge manifest and inert fixture data flow through a bundled fixture agent, deterministic scorer, evidence bundle writer, and offline verifier. The fixture runner does not execute participant code or call external model APIs.

### Interactive tool-loop-v1

The interactive JSONL adapter sends TASK_INIT, intercepts TOOL_CALL frames through a per-pack capability allowlist, returns TOOL_RESULT frames, and terminates on FINAL_COMMIT. The built-in mock tools are deterministic and offline. Permission denials produce 403 results and counters; repeated denied calls are identified as retry loops. Transient mock failures are fixture-controlled and stateful: each 503 is emitted on an actual tool call, retries must reuse the same operation ID, and recovery credit is awarded only after a successful subsequent call. The retry budget is capped and unresolved operations are penalized. The runner and the single-turn adapter now use the same internal execution supervisor for minimal environment construction, temporary working directories, namespace preflight, confirmed POSIX resource limits, process-group lifecycle, and cleanup. Tool-loop runs persist `containment.json` and `execution.json` under a run-specific artifact directory, bound stdout/stderr, and include a canonical transcript digest in successful result records. Strict mode requires Linux user/network/PID namespaces. It remains a trusted-code runner, not a filesystem sandbox.

### Local command adapter
The adversarial runner invokes an operator-configured argument vector through `gauntlet.containment.run_contained`. It sends one JSON task on stdin and expects one JSON object on stdout. Each seed is a separate process invocation. POSIX resource limits, a scrubbed environment, a temporary working directory, process-group cleanup, and bounded stdout/stderr capture are applied. Best-effort mode attempts Linux user/network/PID namespaces when available. This is a **single-turn local subprocess contract**, not a remote adapter or filesystem sandbox.

The local command adapter and experimental persistent-process JSONL session adapter are implemented for sequential, non-interactive multi-turn tests. Neither path is secure filesystem isolation: the process retains the OS permissions of its execution identity, and namespace network isolation is capability- and mode-dependent.

### Deterministic reference matrix

Four bundled synthetic reference programs run across 14 profile/suite combinations using a fixed seed inventory. The standard CI baseline uses 25 seeds per run (350 cases), verifies each evidence bundle, and uploads the baseline index plus bundles as a workflow artifact. These controls calibrate evaluator sensitivity; they are not external model results.

### GRI and federated admission

The GRI combines the ten declarative challenge domains with explicit coverage and hard security penalties. Permission violations and injection breaches force the affected domain to zero. Scorecards embed their evaluated pack results, commit canonical result hashes and a digest of all public scorecard claims into the OpenSSH-signed attestation payload, and recompute the GRI during verification. The optional local leaderboard gate requires a registered signer, valid signature, six executable suites with at least 25 unique seeds per suite, and complete ten-domain coverage. This is a custody and completeness gate, not a truth oracle. See [GRI and Leaderboard](GRI-AND-LEADERBOARD.md).

## Evidence and trust boundaries
- Challenge payloads are parsed as data, not imported as Python.
- SHA-256 inventories detect payload changes relative to the manifest.
- Evidence bundles remain unsigned by default. Scorecards include canonical provenance roots and optionally carry detached OpenSSH signatures. A submitter can still generate a fresh internally consistent bundle.
- Deterministic case reconstruction and score recomputation validate evaluator consistency, not semantic truth or honest model execution.
- Agent/model/version fields are operator declarations, not authenticated identities.
- The evaluator is a narrow challenge contract, not a general-purpose hallucination detector.

## Remaining milestones
1. **Implemented in the unified execution supervisor branch:** share containment setup, confirmed limits, namespace handling, process-group lifecycle, and run-scoped containment/execution reports across single-turn and interactive tool-loop execution. Remaining follow-up: cross-platform capability tests and durable failure-transcript artifacts.
2. Make live tool-loop sessions and offline trace replay share one protocol validator and conformance suite.
3. Add an end-to-end per-pack/per-seed execution pipeline that emits canonical evidence bundles, rather than relying only on separately supplied response JSON.
4. Add portable evidence archive intake and independent replay; keep `attested` and `reproduced` as distinct result states.
5. Enforce every checked-in JSON schema in CI and expand cross-platform containment testing.
6. Build community participation only after external signers and reproducible submissions exist.

## Integration policy
Huffman Protocol, Mesh Archivist, and other projects may provide optional adapters or packaging integrations. The core runner must remain independently useful and have no mandatory runtime dependencies.
