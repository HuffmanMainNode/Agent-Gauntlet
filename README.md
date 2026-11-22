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

**Status boundary:** these ten packs are currently declarative assets. The general-purpose pack loader/evaluator and CLI execution path are not yet implemented. The executable adversarial suites below remain the current CLI evaluation path.

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

Scorecards are unsigned operator submissions, not authenticated rankings or certifications. See [Global Benchmark Standard](docs/GLOBAL-BENCHMARK-STANDARD.md) and [score submission rules](leaderboard/README.md).

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

**Prototype / experimental.** The local fixture runner, evidence verifier, local stdin/stdout subprocess adapters, deterministic assertion operators, and experimental persistent-process JSONL session protocol are implemented. Ten declarative Challenge Laboratory packs are populated and structurally tested. A general-purpose pack loader/evaluator, remote adapters, interactive tool-round-trip sessions, hardened sandboxed execution, cryptographic signatures, independent result federation, and production-grade security review remain pending.

See [Architecture](docs/ARCHITECTURE.md), [Scoring](docs/SCORING.md), [Security](SECURITY.md), [Contributing](CONTRIBUTING.md), and the [Failure Ledger](docs/FAILURE-LEDGER.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
