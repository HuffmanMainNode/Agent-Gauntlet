# Agent Gauntlet

**Your AI says it can do the job. Prove it.**

Agent Gauntlet is a decentralized, open-source proving ground for AI agents, challenges, frameworks, and reproducible evidence. It is a toolkit and a set of open formats, not a hosted service. Anyone can fork it, run it locally, create challenges, build adapters, and publish independently verifiable results.

## First prototype: local, deterministic, evidence-first

The original fixture runner uses two bundled demonstration agents and does not invoke a model API or access the network. The adversarial runner additionally supports an explicitly supplied local command adapter. That adapter executes participant-selected code on the operator's machine and is **not sandboxed**. Use only trusted adapters inside a disposable, externally isolated environment.

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

The runner writes a portable evidence bundle under `artifacts/`. `LATEST` contains the most recent bundle directory name.

Try the deliberately incomplete fixture agent:
```sh
python -m gauntlet run --challenge repository-reality-check --agent demo-bad
```

The demo agents are deterministic test fixtures, not real AI systems. Their scores are demonstration outputs, not claims about model performance.

## Evidence bundle
- Exact challenge identifier and version
- Agent identifier and declared type
- UTC start/end timestamps
- Task input and agent output
- Deterministic score breakdown
- SHA-256 inventory for every payload file
- Verification report

A valid hash proves that files match recorded digests. It does not prove honest execution, agent identity, safety, or independent observation.

## Adversarial evaluation

The expanded prototype includes seeded suites for:
- Hallucination pressure: missing facts where abstention is the correct behavior.
- Contradictory records: agents must surface incompatible sources.
- Prompt injection: hostile instructions embedded inside evidence must remain untrusted data.
- Live-variable simulation: values change by seed and must be recalculated from current inputs.
- Ambiguity: agents must not turn missing approval evidence into an approval claim.

Run a suite using an adapter command you explicitly trust:

```sh
python -m gauntlet adversarial --suite hallucination --adapter-json '["python","my_adapter.py"]' --seeds 1,2,3,4,5 \
  --agent-name "Example Agent" \
  --model-id "provider/model/version" \
  --adapter-version "git:abc123" \
  --operator "community-handle"
```

The adapter receives one JSON task on stdin and returns one JSON response on stdout. The command is executed directly without a shell and has a timeout, but **this is not a sandbox**. Run adapters only in a disposable environment. The report records per-case results, suite summaries, seeds, and hashes. Adapter timeouts, non-zero exits, malformed output, and other handled execution errors are retained as failed cases with zero points rather than silently dropping the run.

Evidence references establish traceability, not semantic entailment. The first evaluator is a narrow contract checker, not a general hallucination detector or complete prompt-injection defense. See [Adversarial Testing](docs/ADVERSARIAL-TESTING.md).

## Public scorecards

Build a scorecard from one or more verified adversarial suite bundles:

```sh
python -m gauntlet scorecard \
  --bundle artifacts/adversarial/RUN_ID \
  --agent-name "Example Agent" \
  --model-id "provider/model/version" \
  --adapter-version "git:abc123" \
  --operator "community-handle" \
  --output scorecard.json

python -m gauntlet verify-scorecard --scorecard scorecard.json
```

Scorecards include per-suite coverage, behavior pass rates, unsupported and malformed claims, abstention rates, evidence hashes, and an explicitly limited geometric-mean behavior index. They are unsigned operator submissions, not authenticated rankings or certifications. See [Global Benchmark Standard](docs/GLOBAL-BENCHMARK-STANDARD.md) and [score submission rules](leaderboard/README.md).

## Community model
1. Fork or clone the repository.
2. Add a challenge pack or adapter proposal.
3. Include fixtures, scoring rules, permissions, and reproducibility instructions.
4. Submit a pull request with tests.
5. Publish evidence bundles for independent verification.

Independent forks may maintain their own challenge collections and result boards. No central account, hosted API, telemetry, token, or leaderboard is required.

For development and tests, install `python -m pip install -e ".[dev]"` and run `python -m pytest`.

## Security boundary
The fixture runner executes bundled logic. The adversarial runner executes an explicitly configured command supplied by the operator. It does not sandbox that command or prevent network/filesystem access. Isolation, resource controls, and network egress policy are the operator's responsibility until a hardened sandbox runner is separately implemented and reviewed.

## Project status
**Prototype / experimental.** The local fixture runner, evidence verifier, and local stdin/stdout subprocess adapters are implemented. The command adapter accepts an explicitly configured argument vector, sends one JSON task on stdin, reads one JSON response from stdout, and enforces a timeout. It executes locally without a shell, but is not sandboxed. Remote/networked adapters, multi-turn stateful adapters, hardened sandboxed execution, cryptographic signatures, independent result federation, and production-grade security review remain pending.

See [ARCHITECTURE.md](docs/ARCHITECTURE.md), [SCORING.md](docs/SCORING.md), [SECURITY.md](SECURITY.md), [CONTRIBUTING.md](CONTRIBUTING.md), and the [Failure Ledger](docs/FAILURE-LEDGER.md).

## License
Apache-2.0. See [LICENSE](LICENSE).
