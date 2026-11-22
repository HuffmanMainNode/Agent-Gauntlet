# Architecture

Agent Gauntlet is local-first and offline-capable. The package runtime uses the Python 3.11+ standard library. The optional development test dependency is pytest.

## Implemented execution paths

### Bundled fixture runner
Challenge manifest and inert fixture data flow through a bundled fixture agent, deterministic scorer, evidence bundle writer, and offline verifier. The fixture runner does not execute participant code or call external model APIs.

### Interactive tool-loop-v1

The interactive JSONL adapter sends TASK_INIT, intercepts TOOL_CALL frames through a per-pack capability allowlist, returns TOOL_RESULT frames, and terminates only on FINAL_COMMIT. The built-in mock tools are deterministic and offline. Permission denials produce 403 results and counters; repeated denied calls are identified as retry loops. Transient mock failures use bounded retry accounting with exponential delay metadata. The runner uses a process group, POSIX resource limits, bounded output, and a wall-clock deadline. It remains a trusted-code runner, not a filesystem sandbox.

### Local command adapter
The adversarial runner invokes an operator-configured argument vector using Python subprocess with `shell=False`, a timeout, and a deliberately minimal environment. It sends one JSON task on stdin and expects one JSON object on stdout. Each seed is a separate process invocation. This is a **single-turn local subprocess contract**, not a remote adapter, persistent session, or sandbox.

The local command adapter is implemented. The experimental persistent-process JSONL session adapter is also implemented for sequential, non-interactive multi-turn tests. Neither path is secure isolation: the process retains the OS permissions and network access of its execution identity.

### Deterministic reference matrix

Four bundled synthetic reference programs run across 14 profile/suite combinations using a fixed seed inventory. The standard CI baseline uses 25 seeds per run (350 cases), verifies each evidence bundle, and uploads the baseline index plus bundles as a workflow artifact. These controls calibrate evaluator sensitivity; they are not external model results.

## Evidence and trust boundaries
- Challenge payloads are parsed as data, not imported as Python.
- SHA-256 inventories detect payload changes relative to the manifest.
- Evidence bundles remain unsigned by default. Scorecards include canonical provenance roots and optionally carry detached OpenSSH signatures. A submitter can still generate a fresh internally consistent bundle.
- Deterministic case reconstruction and score recomputation validate evaluator consistency, not semantic truth or honest model execution.
- Agent/model/version fields are operator declarations, not authenticated identities.
- The evaluator is a narrow challenge contract, not a general-purpose hallucination detector.

## Planned, separate milestones
1. Federated leaderboard inclusion gates with registered signer identities and minimum seed coverage.
2. Cross-domain Gauntlet Reliability Index with explicit coverage and penalty disclosures.
3. Deterministic reference runs and independent reproduction reports.
4. Independent verifier test vectors and cross-language implementations.

## Integration policy
Huffman Protocol, Mesh Archivist, and other projects may provide optional adapters or packaging integrations. The core runner must remain independently useful and have no mandatory runtime dependencies.
