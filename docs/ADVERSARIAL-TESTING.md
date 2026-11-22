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


## Command adapter contract

Use `agent-gauntlet adversarial --suite SUITE --adapter-json '["executable","arg"]' --seeds 1,2,3`. The adapter receives a JSON task on stdin and returns one JSON object on stdout. The adapter is explicitly trusted local code. The runner uses argument-list execution (no shell), a timeout, and a reduced environment, but does not sandbox the process or restrict filesystem/network access. Use a disposable VM/container configured by the operator.

## Current evaluator limitations

The current checks validate task-specific required behavior and evidence-ID traceability. They do not independently prove semantic entailment, source authenticity, factual truth, model identity, or resistance to all prompt-injection techniques. Confidence values are retained in raw responses but are not scored as calibrated probabilities. Those features require labeled corpora, independent evaluation, and statistical validation.


## Multi-turn JSONL session protocol (experimental)

The `stateful` suite uses `--protocol jsonl-session`. The harness starts one adapter process per seed and exchanges newline-delimited JSON frames over that process's stdin/stdout. Each input frame has a monotonically increasing `turn_index`. The adapter must emit exactly one JSON object per input frame, in order, with the matching `turn_index`. The process remains alive across the bounded sequence for that seed; a fresh process starts for the next seed.

The reference state-drift challenge sends an initial value, then a correction frame that explicitly supersedes the earlier evidence, then asks for the current value. The final answer must cite the latest evidence. Stale-state answers, missing frames, malformed JSONL, incorrect turn indexes, non-zero exits, and timeouts fail the case and remain in the evidence bundle.

This first protocol is sequential but non-interactive: the harness supplies the full frame sequence to stdin and evaluates the ordered response sequence after process completion. It tests process-persistent state across turns, not adaptive tool round-trips where later inputs depend on earlier outputs. A future interactive protocol would require a separately designed streaming transport and per-turn deadlines.

Example:

```sh
python -m gauntlet adversarial --suite stateful --protocol jsonl-session \
  --adapter-json '["python","my_session_adapter.py"]' --seeds 1,2,3 \
  --agent-name "Example Session Agent" --model-id "provider/model" \
  --adapter-version "git:abc123" --operator "community-handle"
```

The session process is trusted local code and remains unsandboxed. Do not run untrusted adapters on a host with secrets or sensitive data.
