# Release checkpoint: 22 November 2026

## Status

**Status: Commits 39-44 merged. The 25-seed baseline is verified.**

The prototype-to-benchmark implementation sequence is merged to `main`. Commit 45 records the successful deterministic reference baseline and freezes the next-step handoff.

## Merged engineering sequence

| Commit | Pull request | Result |
|---|---|---|
| 39 | [#11 POSIX containment](https://github.com/HuffmanMainNode/Agent-Gauntlet/pull/11) | Resource hardening, process-group cleanup, bounded I/O, strict namespace fail-closed behavior |
| 40 | [#12 Challenge Pack Engine](https://github.com/HuffmanMainNode/Agent-Gauntlet/pull/12) | General-purpose declarative pack loader and evaluator |
| 41 | [#13 Interactive tool loop](https://github.com/HuffmanMainNode/Agent-Gauntlet/pull/13) | `tool-loop-v1`, deterministic mock tools, runtime permission interception |
| 42 | [#14 Provenance and signatures](https://github.com/HuffmanMainNode/Agent-Gauntlet/pull/14) | Canonical provenance root and OpenSSH detached signatures |
| 43 | [#15 Reference baselines](https://github.com/HuffmanMainNode/Agent-Gauntlet/pull/15) | Four deterministic reference agents and 25-seed CI matrix |
| 44 | [#16 GRI and federated gate](https://github.com/HuffmanMainNode/Agent-Gauntlet/pull/16) | Coverage-aware GRI, signed pack-result binding, signer/seed/coverage admission gate |
| 45 | [This checkpoint](https://github.com/HuffmanMainNode/Agent-Gauntlet/pull/17) | Verified baseline report and release handoff |

## Verified baseline

- 25 fixed seeds, 1 through 25.
- Four synthetic reference profiles.
- 14 profile/suite runs and 350 cases.
- All 14 evidence bundles verified.
- Python 3.11, 3.12, and 3.13 CI test suites passed.
- Python 3.11 CI generated and verified the 25-seed baseline artifact.
- No third-party Python runtime dependency was introduced.

See [Reference Baseline Report](REFERENCE-BASELINE-REPORT.md) and the machine-readable [baseline record](../benchmarks/reference-baseline-2026-11-22.json).

## Architecture and trust boundaries

- POSIX resource limits, scrubbed environment, temporary working directory, process groups, and output caps are hardening measures. They are not filesystem isolation.
- Strict namespace mode fails closed if the requested Linux namespaces cannot be established.
- Tool permissions are enforced at dispatch time. Denials are recorded as deterministic violations.
- OpenSSH signatures prove custody of the signed provenance digest by a key holder. They do not prove an agent's identity, honesty, or truthfulness.
- GRI completeness and security penalties are explicit. Missing domains reduce coverage; permission violations and injection breaches zero the affected domain.
- The federated gate is local and operator-governed. No central registry or hosted leaderboard is implied.

## Next work when development resumes

1. Recruit independent evaluators to reproduce the same fixed-seed baseline from clean clones.
2. Publish signed submissions covering all six executable suites and all ten challenge domains.
3. Run containment and tool-loop compatibility tests across additional Linux distributions and POSIX environments.
4. Review challenge quality and scoring contracts with external contributors.
5. Only after independent submissions exist, compare cross-agent results and consider a public leaderboard release.

## Release decision

The deterministic prototype milestone is complete and suitable for a tagged prototype release after the owner chooses a version and performs the release action. Do not describe the system as a fully sandboxed execution environment or as an independently validated global AI ranking system.
