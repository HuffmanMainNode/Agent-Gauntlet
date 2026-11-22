# Deterministic reference baselines

Agent Gauntlet includes four local, synthetic reference programs to calibrate the evaluator. They are not hosted models and make no claims about any external model provider.

## Generate the standard baseline

From a clean repository checkout:

```sh
python -m gauntlet reference --output artifacts/reference
python -m gauntlet verify-reference --baseline artifacts/reference/reference-baseline.json
```

The default matrix uses seeds 1 through 25 and creates 14 evidence bundles:

| Reference profile | Suites |
|---|---|
| `demo-good` | All six executable adversarial suites |
| `demo-bad` | All six executable adversarial suites |
| `demo-vulnerable-injection` | Injection |
| `demo-stale-state` | Stateful JSONL session |

That is 350 deterministic cases across the matrix. Each case is stored in its own verified adversarial evidence bundle. The baseline index records each bundle path, run ID, evidence digest, behavior pass rate, mean score, execution failures, and unsupported claims.

## Reproduce with a smaller seed set

```sh
python -m gauntlet reference --seed-start 1 --seed-count 3 --output artifacts/reference-smoke
python -m gauntlet verify-reference --baseline artifacts/reference-smoke/reference-baseline.json
```

The seed count option is intended for local smoke tests. The standard published reference baseline uses 25 seeds.

## Interpretation

- `demo-good` is a deterministic positive control for the declared suite contracts.
- `demo-bad` is a deliberately unreliable negative control.
- `demo-vulnerable-injection` intentionally emits the untrusted canary.
- `demo-stale-state` intentionally reports the superseded initial value.

These controls check evaluator sensitivity and evidence reproducibility. They are not representative samples of commercial agents. A successful reference baseline verifies deterministic runner behavior, not general agent reliability.
