# Agent Gauntlet

**Your AI says it can do the job. Prove it.**

Agent Gauntlet is a decentralized, open-source proving ground for AI agents, challenges, frameworks, and reproducible evidence. It is a toolkit and open formats, not a hosted service. Anyone can fork it, run it locally, create challenges, build adapters, and publish independently verifiable results.

## First prototype: local, deterministic, evidence-first

The fixture runner uses bundled demonstration agents and does not invoke a model API or access the network. The adversarial runner also supports an explicitly supplied local command adapter. That adapter executes participant-selected code on the operator's machine and is **not sandboxed**. Use only trusted adapters inside a disposable, externally isolated environment.

### Requirements
- Python 3.11+
- No third-party runtime dependencies

### Run the demo
```sh
git clone https://github.com/HuffmanMainNode/Agent-Gauntlet.git
cd Agent-Gauntlet
python -m pip install -e .
python -m gauntlet run --challenge repository-reality-check --agent demo-good
python -m gauntlet verify --bundle artifacts/LATEST
```

## Challenge Laboratory

Ten populated, versioned challenge packs cover evidence integrity, temporal reasoning, instruction resistance, multi-agent coordination, technical reasoning, privacy and authorization, scientific reasoning, failure recovery, resource optimization, and reproducibility.

Start with [the Challenge Laboratory catalog](docs/CHALLENGE-LABORATORY.md). Each pack includes a manifest, synthetic fixture, expected behavior, fixed seed, permissions, resource limits, and scoring contract. Packs are data-only and safe to inspect.

**Pack engine available:** all ten packs now include executable assertion contracts. The local engine loads and validates pack data, then scores a separately generated JSON response. It never executes agent-submitted code. See [Challenge Pack Engine](docs/CHALLENGE-PACK-ENGINE.md).

### Evaluate a challenge pack

Run one pack after saving your agent's JSON response:

```sh
python -m gauntlet pack --name technical-reasoning --response response.json
```

Run all ten using `responses/<pack-id>.json` files:

```sh
python -m gauntlet pack --all --responses-dir responses/
```

The engine reports behavior, traceability, and format scores. Missing responses or failed assertions produce a non-zero exit. The pack evaluator is data-only and does not execute the agent.

Run an interactive local agent using only the tools allowed by its pack:

```sh
python -m gauntlet tool-loop --name evidence-integrity --adapter-json '["python","agent.py"]'
```

The tool-loop runner sends TASK_INIT, intercepts TOOL_CALL, returns TOOL_RESULT, and requires FINAL_COMMIT. Permission denials return 403 and are counted. Transient fault schedules are fixture-controlled; recovery credit requires observed retry calls against the same operation ID. Built-in mock tools are deterministic and offline.

## Post-release engineering roadmap

The [post-release engineering roadmap](docs/POST-RELEASE-ENGINEERING-ROADMAP.md) records the verified state, remaining engineering gaps, and the proposed next implementation sequence.

## Release checkpoint

The Commit 39-45 engineering sequence is recorded in the [22 November 2026 release checkpoint](docs/RELEASE-CHECKPOINT-2026-11-22.md), with the verified 25-seed [baseline report](docs/REFERENCE-BASELINE-REPORT.md).

## Reliability index and federated leaderboard

The cross-domain GRI reports coverage, missing domains, and security-penalized domains. Permission violations or injection breaches zero the affected domain. The federated admission gate requires a valid OpenSSH signature from a registered signer, a signature-bound digest of all public scorecard claims, all six executable suites with at least 25 distinct seeds each, exact case/seed inventory agreement, and full ten-domain coverage. The gate checks signed declarations and internal consistency; independent reproduction is still required to establish external validity. See [GRI and Leaderboard](docs/GRI-AND-LEADERBOARD.md).

## Deterministic reference baseline

Generate and verify the standard 25-seed calibration matrix:

```sh
python -m gauntlet reference --output artifacts/reference
python -m gauntlet verify-reference --baseline artifacts/reference/reference-baseline.json
python -m gauntlet verify-leaderboard
```

The matrix contains 14 bundles and 350 cases across `demo-good`, `demo-bad`, `demo-vulnerable-injection`, and `demo-stale-state`. These are synthetic local controls, not external model results. See [Reference Baselines](docs/REFERENCE-BASELINES.md).

## Gauntlet Reliability Index

Generate a coverage-aware score from pack result files:

```sh
python -m gauntlet gri --result artifacts/packs/evidence-integrity.result.json
```

The report always discloses missing domains and security-penalized domains. Any permission violation or injection breach zeros the affected domain. Partial coverage is never presented as a complete benchmark.

## Evidence bundles

Bundles include challenge identity/version, agent identity/type, timestamps, task input/output, deterministic score breakdown, SHA-256 inventory, and verification report. A valid hash proves that files match recorded digests. It does not prove honest execution, agent identity, safety, or independent observation.

## Executable adversarial evaluation

The existing runner includes seeded suites for hallucination pressure, contradictory records, prompt injection, variable numeric inputs, ambiguity, and stateful JSONL sessions.

Run a suite using an adapter command you explicitly trust:

```sh
python -m gauntlet adversarial --suite hallucination --adapter-json '["python","my_adapter.py"]' --seeds 1,2,3,4,5 \
  --agent-name "Example Agent" --model-id "provider/model/version" \
  --adapter-version "git:abc123" --operator "community-handle"
```

The optional `jsonl-session` protocol starts one persistent process per seed and requires one response frame per input frame with matching `turn_index`. Neither adapter mode is a sandbox. Timeouts, non-zero exits, malformed output, and missing session frames are retained as failed cases.

Evidence references establish traceability, not semantic entailment. The evaluator is a narrow contract checker, not a general hallucination detector or complete prompt-injection defense.

## Public scorecards

Build a scorecard from verified adversarial suite bundles:

```sh
python -m gauntlet scorecard --bundle artifacts/adversarial/RUN_ID \
  --agent-name "Example Agent" --model-id "provider/model/version" \
  --adapter-version "git:abc123" --operator "community-handle" \
  --output scorecard.json
python -m gauntlet verify-scorecard --scorecard scorecard.json
```

Scorecards include a coverage-aware ten-domain Gauntlet Reliability Index (GRI), canonical SHA-256 provenance roots, and optional detached OpenSSH custody signatures. The leaderboard gate requires registered signers, full GRI coverage, and at least 25 cases per adversarial suite. Signatures prove key-holder custody over the root digest, not agent identity or behavioral honesty. See [score submission rules](leaderboard/README.md).

## Community model

1. Fork or clone the repository.
2. Add a challenge pack or adapter proposal.
3. Include fixtures, expected behavior, scoring rules, permissions, and reproducibility instructions.
4. Submit a pull request with tests.
5. Publish evidence bundles for independent verification.

Independent forks may maintain their own challenge collections and result boards. No central account, hosted API, telemetry, token, or leaderboard is required.

For development and tests, install `python -m pip install -e ".[dev]"` and run `python -m pytest`.

## Security boundary

The adversarial runner executes an explicitly configured command supplied by the operator. It does not sandbox that command or prevent network/filesystem access. Isolation and egress policy remain the operator's responsibility until a hardened sandbox runner is separately implemented and reviewed. Challenge pack loading is data-only.

## Project status

**Prototype / experimental.** The local fixture runner, evidence verifier, POSIX resource-hardening runner, local stdin/stdout adapters, deterministic assertion operators, persistent JSONL sessions, declarative pack loader/evaluator, interactive tool-loop, signed scorecards, and local federated admission gate are implemented. Ten synthetic Challenge Laboratory packs are populated. The leaderboard currently has no registered external signers or submissions. Independent evidence replay, a hostile-code filesystem sandbox, external evaluator participation, cross-platform containment validation, and production-grade security review remain pending.

See [Architecture](docs/ARCHITECTURE.md), [Scoring](docs/SCORING.md), [Security](SECURITY.md), [Contributing](CONTRIBUTING.md), and the [Failure Ledger](docs/FAILURE-LEDGER.md).

## License

Apache-2.0. See [LICENSE](LICENSE).


## Run a local pack across declared seeds

The `pack-run` command executes an explicitly supplied, trusted local adapter through the interactive `tool-loop-v1` protocol, evaluates each final commit, and writes a verifiable evidence bundle:

```sh
python -m gauntlet pack-run --name technical-reasoning \
  --adapter-json '["python","agent.py"]' \
  --seeds 1,2,3,4,5 \
  --adapter-name "Example Agent" \
  --adapter-version "git:abc123" \
  --operator "community-handle"
```

Verify the resulting bundle:

```sh
python -m gauntlet verify-pack-run --bundle artifacts/pack-runs/RUN_ID
```

Each seed gets a separate fixture copy, transcript digest, final response, assertion report, containment report, and execution record. Failed attempts are retained rather than silently dropped. The adapter command itself is represented by a SHA-256 digest in the evidence manifest; retain the exact command and adapter source separately if independent reproduction is intended.

**Seed semantics:** each seed deterministically permutes the existing synthetic evidence records using a seed-scoped SHA-256 sort key. Evidence content is preserved, but presentation order varies. Finite evidence sets have finite permutations, so different seeds can produce the same ordering. This is a presentation-order variant, not newly synthesized evidence. The runner remains a trusted-code execution path, not a filesystem sandbox.
