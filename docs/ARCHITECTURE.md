# Architecture

The first implementation is deliberately local-first.

Challenge manifest + inert fixture -> bundled fixture adapter -> deterministic scorer -> evidence bundle -> offline verifier.

## Trust boundaries
- Challenge data is parsed as data; it is not imported as Python.
- The runner uses a hard-coded allowlist of bundled fixture agents.
- No network calls, model API calls, shell commands, subprocesses, or participant code execution occur.
- Evidence records an unsigned local run. SHA-256 protects integrity against post-generation modification, not authorship or honest execution.

## Next gates
1. Formal JSON Schemas for challenge and evidence formats.
2. Adapter contract with explicit capability and permission declarations.
3. Sandboxed external adapter process with resource limits and opt-in network policy.
4. Detached signatures and key identity lifecycle.
5. Independent verifier and cross-language test vectors.
6. Federation format for independent result boards.

Huffman Protocol and Mesh Archivist integrations remain optional. The core runner must work without them.
