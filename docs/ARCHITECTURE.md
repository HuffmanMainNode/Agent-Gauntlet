# Architecture

Agent Gauntlet is local-first and offline-capable. The package runtime uses the Python 3.11+ standard library. The optional development test dependency is pytest.

## Implemented execution paths

### Bundled fixture runner
Challenge manifest and inert fixture data flow through a bundled fixture agent, deterministic scorer, evidence bundle writer, and offline verifier. The fixture runner does not execute participant code or call external model APIs.

### Local command adapter
The adversarial runner invokes an operator-configured argument vector using Python subprocess with `shell=False`, a timeout, and a deliberately minimal environment. It sends one JSON task on stdin and expects one JSON object on stdout. Each seed is a separate process invocation. This is a **single-turn local subprocess contract**, not a remote adapter, persistent session, or sandbox.

The local command adapter is implemented. It must not be described as secure isolation: the process retains the OS permissions and network access of its execution identity.

## Evidence and trust boundaries
- Challenge payloads are parsed as data, not imported as Python.
- SHA-256 inventories detect payload changes relative to the manifest.
- The evidence and scorecard formats are unsigned. A submitter can generate a fresh internally consistent bundle.
- Deterministic case reconstruction and score recomputation validate evaluator consistency, not semantic truth or honest model execution.
- Agent/model/version fields are operator declarations, not authenticated identities.
- The evaluator is a narrow challenge contract, not a general-purpose hallucination detector.

## Planned, separate milestones
1. Multi-turn stateful adapter protocol with explicit frame sequencing, state-change events, turn limits, and recovery semantics.
2. Defense-in-depth POSIX process controls, clearly labeled as best-effort containment and never as a hostile-code sandbox.
3. Optional detached cryptographic signatures and documented key lifecycle.
4. Deterministic semantic assertion primitives for exact values, numeric tolerances, allowed derivations, and source-to-claim constraints.
5. Independent verifier test vectors and cross-language implementations.
6. Federated publication and independent reproduction formats.

## Integration policy
Huffman Protocol, Mesh Archivist, and other projects may provide optional adapters or packaging integrations. The core runner must remain independently useful and have no mandatory runtime dependencies.
