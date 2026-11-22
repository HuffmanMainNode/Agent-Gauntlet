# Public score submissions

This directory defines the contribution format, not a centrally trusted ranking service.

## Submit a result

1. Run the challenge suites locally against your own agent.
2. Preserve the complete evidence bundles.
3. Generate a scorecard with `agent-gauntlet scorecard`.
4. Verify it with `agent-gauntlet verify-scorecard`.
5. Open a pull request adding the scorecard JSON under `leaderboard/submissions/` and link the evidence bundle using a durable public artifact URL or attach the bundle to the submission.
6. Disclose model/provider/version, adapter version, operator, run date, suite coverage, and whether the run was independently reproduced.

Example:

```sh
agent-gauntlet scorecard \
  --bundle artifacts/adversarial/RUN_ID_1 \
  --bundle artifacts/adversarial/RUN_ID_2 \
  --agent-name "Example Agent" \
  --model-id "provider/model/version" \
  --adapter-version "git:abc123" \
  --operator "community-handle" \
  --output scorecard.json

agent-gauntlet verify-scorecard --scorecard scorecard.json
```

## Rules

- Never submit fixture-agent scores as real model results.
- Never remove failed cases from a completed run.
- Never compare different challenge versions as if they were identical.
- Partial suite coverage must be shown as partial. Missing suites are not zero failures or passes.
- Scorecards are self-reported and unsigned by default. A digest detects accidental or later modification; it does not authenticate the submitter.
- The project maintainers may label entries as submitted, schema-valid, evidence-referenced, independently reproduced, disputed, or withdrawn. These are distinct statuses.
- No score is a certification of safety, alignment, general intelligence, or deployment readiness.

The long-term goal is a federated board: independent mirrors can ingest the same scorecard format and apply transparent inclusion policies.
