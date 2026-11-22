# Agent Gauntlet

**Your AI says it can do the job. Prove it.**

Agent Gauntlet is a decentralized, open-source proving ground for AI agents, challenges, frameworks, and reproducible evidence. It is a toolkit and a set of open formats, not a hosted service. Anyone can fork it, run it locally, create challenges, build adapters, and publish independently verifiable results.

## First prototype: local, deterministic, evidence-first

The initial runner deliberately uses only two bundled fixture agents. It does **not** execute participant code, invoke a model API, access the network, or inspect your machine. This makes the first demonstration safe and repeatable while adapter and sandbox contracts are developed.

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

## Community model
1. Fork or clone the repository.
2. Add a challenge pack or adapter proposal.
3. Include fixtures, scoring rules, permissions, and reproducibility instructions.
4. Submit a pull request with tests.
5. Publish evidence bundles for independent verification.

Independent forks may maintain their own challenge collections and result boards. No central account, hosted API, telemetry, token, or leaderboard is required.

For development and tests, install `python -m pip install -e ".[dev]"` and run `python -m pytest`.

## Security boundary
The first prototype runs only trusted, bundled fixture logic. It never loads or executes adapter code supplied by a challenge bundle or participant. Future external adapters must be explicitly configured and isolated; network and host filesystem access remain opt-in.

## Project status
**Prototype / experimental.** The local fixture runner and evidence verifier are implemented. External agent adapters, sandboxed execution, cryptographic signatures, independent result federation, and production-grade security review are not yet implemented.

See [ARCHITECTURE.md](docs/ARCHITECTURE.md), [SCORING.md](docs/SCORING.md), [SECURITY.md](SECURITY.md), and [CONTRIBUTING.md](CONTRIBUTING.md).

## License
Apache-2.0. See [LICENSE](LICENSE).
