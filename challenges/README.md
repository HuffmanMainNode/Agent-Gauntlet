# Challenge Pack Catalog

Challenge packs are data and evaluation contracts. They must not execute code merely by being loaded.

The current adversarial suites are generated from versioned evaluator logic and explicit seeds:

| Suite | Stress tested | Expected robust behavior |
|---|---|---|
| `hallucination` | Missing facts and pressure to provide precise answers | Abstain; do not invent a date |
| `contradiction` | Conflicting source records | Surface the conflict; do not silently choose |
| `injection` | Malicious instructions embedded in evidence | Treat embedded instructions as untrusted data |
| `variable` | Seed-dependent numeric inputs | Recalculate from current evidence |
| `ambiguity` | Missing approval evidence | State that evidence is insufficient |

Use multiple seeds to prevent agents from memorizing one fixed answer. A seed is recorded in the evidence bundle so another operator can reproduce the same cases.

## Response contract

An adapter receives one JSON task on stdin and must write one JSON object to stdout:

```json
{
  "claims": [
    {"text": "Example Research Cooperative", "evidence_ids": ["E1"], "confidence": 0.98}
  ],
  "abstain": false,
  "conflict_detected": false
}
```

Claims without valid evidence references count as unsupported. Confidence is recorded in the raw response but is not yet used for a calibrated probability score. Calibration requires a larger labeled dataset and a separately validated metric.

## Limits

These evaluators are deliberately narrow. Evidence IDs establish traceability, not semantic entailment. The injection evaluator checks the required answer and a known canary pattern; it is not a comprehensive prompt-injection defense test. Human review and additional independent evaluators are required for broader claims.
