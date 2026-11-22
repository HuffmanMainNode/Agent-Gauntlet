# Global Benchmark Standard: Initial Draft

## Benchmark posture

Agent Gauntlet is adversarial, not theatrical. A challenge must target a defined capability or failure mode, include a reproducible input, declare permissions, preserve raw outputs, and publish scoring logic and limitations.

## Required dimensions

- Factual grounding and unsupported-claim behavior
- Abstention under missing or ambiguous evidence
- Conflict detection and source provenance
- Prompt-injection and untrusted-content handling
- Temporal reasoning and stale-data detection
- Multi-step consistency and state recovery
- Tool-use correctness and permission discipline
- Robustness to malformed, noisy, duplicated, and adversarial inputs
- Operational reliability, timeouts, and resource consumption
- Repeatability across seeds and repeated runs

## Tournament controls

- Freeze challenge version and scoring code for each tournament window.
- Publish challenge hashes before accepting submissions.
- Use hidden holdout cases only when their scoring contract and post-event disclosure policy are documented.
- Rotate challenge variants to reduce memorization.
- Preserve all attempted cases, failures, timeouts, and invalid outputs.
- Require minimum suite coverage for any overall comparison.
- Publish per-dimension results; never rank by a single opaque composite alone.
- Provide an appeal and independent reproduction process.

## Evidence levels

1. **Submitted:** scorecard received.
2. **Schema-valid:** scorecard matches the published schema and digest.
3. **Evidence-referenced:** referenced artifacts are available.
4. **Locally verified:** independent verifier recomputes hashes and deterministic evaluator results.
5. **Independently reproduced:** another operator reruns the declared setup and obtains comparable results.
6. **Disputed / withdrawn:** material issue reported or submitter retracts.

These levels must not be collapsed. A GitHub PR merge is not a benchmark endorsement.

## Live-data challenges

A live-source challenge must capture the exact source response, retrieval timestamp, URL or source identifier, relevant headers where lawful, parser version, and content digest. Scoring must run against the frozen snapshot, not a moving website. Respect terms, rate limits, privacy, and applicable law.

## Security boundary

No challenge pack may silently execute arbitrary code. Any future sandbox runner needs a separate threat model, resource controls, isolation testing, network egress policy, and explicit operator opt-in. A container is not automatically a sufficient security boundary.
