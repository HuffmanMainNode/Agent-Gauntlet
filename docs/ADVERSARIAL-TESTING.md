# Adversarial Testing Protocol

## Purpose

Measure behavior under uncertainty, contradictory records, prompt injection, variable inputs, and unsupported-answer pressure. These suites are not a single intelligence score.

## Run protocol

- Run each suite across at least 30 distinct seeds for a smoke evaluation and 100+ for a more stable comparison.
- Keep challenge version, seed list, adapter command, model/provider/version, decoding settings, and runtime facts with the evidence package.
- Repeat a subset at least three times to expose nondeterminism.
- Separate deterministic checks from human or model-judge assessments.
- Publish failures and invalid runs; do not silently discard inconvenient results.

## Required reporting

Report per-suite behavior pass rate, unsupported claim count, abstention rate, conflict detection rate, timeout/error rate, score distribution, and seed coverage. Report mean and median; include per-case records. Do not collapse all dimensions into one headline rank.

## Hallucination policy

A claim is not verified merely because it cites an evidence ID. The first evaluator checks traceability and task-specific required behavior. Semantic entailment, source authenticity, and factual truth need independent evaluation. Label those gaps rather than pretending the runner solved them.

## Live-variable policy

Seeded values change each run while remaining reproducible. A future live-data suite must snapshot source payloads, record retrieval time and source identity, and preserve the exact snapshot in the evidence bundle. Never compare answers against a live source that can change after the run.

## Safety

The command adapter executes a command explicitly supplied by the operator. It is not a sandbox. Use a disposable environment and a deliberately restricted adapter. Never pass secrets or private data in challenge inputs.
