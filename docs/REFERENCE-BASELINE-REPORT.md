# Agent Gauntlet reference baseline: 22 November 2026

**Verified CI baseline**

The standard deterministic reference matrix completed successfully on 22 November 2026. The tested revision was `d846955507118b9628cd7ad8b593ffd9e97db22f`, subsequently merged to `main` as `a559af73b11bd4d5419d5eb1495c532761df7b04` through PR #16.

## Baseline facts

| Measure | Result |
|---|---:|
| Fixed seeds | 25 (1 through 25) |
| Synthetic reference profiles | 4 |
| Profile/suite runs | 14 |
| Evaluated cases | 350 |
| Evidence bundles verified | 14 of 14 |
| Execution failures | 0 |
| CI Python versions | 3.11, 3.12, 3.13 |

The machine-readable release summary is [reference-baseline-2026-11-22.json](../benchmarks/reference-baseline-2026-11-22.json), validated by [release-baseline-report.schema.json](../schemas/release-baseline-report.schema.json). The original CI-generated baseline index and all evidence bundles are preserved in the linked workflow artifact.

## Calibration outcomes

- **demo-good:** 100% behavioral pass rate across all six executable suites.
- **demo-bad:** 0% behavioral pass rate across all six suites. Its stateful mean score remains 50 because the composite case score contains multiple dimensions. Behavioral pass rate and mean score must not be conflated.
- **demo-vulnerable-injection:** 0% behavioral pass rate on injection.
- **demo-stale-state:** 0% behavioral pass rate on the stateful suite.

These are intentionally synthetic calibration agents. The results establish that the evaluator distinguishes the bundled positive and negative controls; they are not claims about any commercial or external AI model.

## Reproduction and evidence

The successful CI run is [Agent Gauntlet CI, run 45053558139](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45053558139). Its `agent-gauntlet-reference-baseline` artifact contains the baseline index and all 14 evidence bundles.

- Artifact ID: `14766482506`
- Artifact SHA-256: `bd78f1c8099b52749e5aaaed5087b0bcf271f1ed140ed849b9e3ec7aa82b0bf9`
- Baseline index SHA-256: `a3ede77ae332e90b30c6245f05bf3856bf4a7e62825726214086b0104876edb6`
- Artifact retention expiry: 20 February 2027

The CI workflow ran the full test suite on Python 3.11, 3.12, and 3.13. The Python 3.11 leg also generated the 25-seed matrix and independently verified every evidence bundle and the baseline index before upload. During this audit, the downloaded archive SHA-256 was recomputed against GitHub's artifact digest, the embedded baseline index SHA-256 was independently recomputed, and all 14 bundle directories were confirmed present.

## Release checkpoint

The engineering sequence from Commit 39 through Commit 44 is merged:

1. POSIX resource hardening and honest containment capability reporting.
2. General-purpose declarative challenge-pack loading and evaluation.
3. Interactive `tool-loop-v1` with deterministic mock tools and runtime permission enforcement.
4. Canonical provenance roots and OpenSSH custody signatures.
5. Deterministic 25-seed synthetic reference matrix.
6. Coverage-aware GRI and federated admission checks.

The repository remains zero third-party Python runtime dependency. Development tests use pytest. Strict namespace isolation is platform-dependent and must fail closed when requested but unavailable. Resource limits and temporary working directories are hardening controls, not a filesystem sandbox.

### Remaining validation work

- Obtain independent reproductions from external evaluators and agents.
- Add signed, complete ten-domain submissions from separately registered evaluators.
- Validate the full tool-loop and containment behavior across additional Linux distributions and supported POSIX environments.
- Treat leaderboard scores as reproducible evidence summaries, not proof of truth, identity, or general intelligence.

This is a release checkpoint for the prototype-to-benchmark transition, not a claim that the federated ecosystem is already populated or independently validated.
