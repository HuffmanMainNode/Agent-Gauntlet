# Challenge Pack Catalog

Challenge packs are versioned data contracts. Loading a pack must not execute code, contact a network, or access files outside its bundled fixture.

## Challenge Laboratory

Ten initial packs are available under this directory:

| Pack | Category | Level | Focus |
|---|---|---|---|
| [evidence-integrity](evidence-integrity/) | Evidence integrity | Advanced | Conflicting primary records |
| [temporal-reasoning](temporal-reasoning/) | Temporal reasoning | Advanced | Authoritative updates and stale values |
| [instruction-resistance](instruction-resistance/) | Instruction resistance | Expert | Untrusted instructions embedded in evidence |
| [multi-agent-coordination](multi-agent-coordination/) | Multi-agent coordination | Expert | Disagreement and evidence provenance |
| [technical-reasoning](technical-reasoning/) | Technical reasoning | Foundation | Exact, traceable calculation |
| [privacy-authorization](privacy-authorization/) | Privacy and authorization | Expert | Permission boundaries and withholding |
| [scientific-reasoning](scientific-reasoning/) | Scientific reasoning | Advanced | Correlation versus causation |
| [failure-recovery](failure-recovery/) | Failure recovery | Expert | Idempotent recovery after ambiguous commit |
| [resource-optimization](resource-optimization/) | Resource optimization | Advanced | Bounded combinatorial selection |
| [reproducibility](reproducibility/) | Reproducibility | Frontier | Canonical independent reproduction |

Every pack contains `challenge.json`, `fixture.json`, and `expected.json`. All initial evidence is synthetic, fixed-seed, and explicitly marked. See [Challenge Laboratory](../docs/CHALLENGE-LABORATORY.md), [Authoring Standard](../docs/CHALLENGE-AUTHORING.md), and [Difficulty Standards](../docs/DIFFICULTY-STANDARDS.md).

## Existing executable adversarial suites

| Suite | Stress tested | Expected robust behavior |
|---|---|---|
| `hallucination` | Missing facts | Abstain; do not invent |
| `contradiction` | Conflicting records | Surface the conflict |
| `injection` | Hostile evidence text | Treat it as untrusted data |
| `variable` | Seed-dependent numbers | Recalculate |
| `ambiguity` | Missing approval evidence | State insufficiency |
| `stateful` | Sequential updates | Replace stale values with authoritative updates |

Run an executable suite using the CLI and adapter options documented in the root README.

**Integration boundary:** the ten Challenge Laboratory packs are declarative assets. A general-purpose pack loader, evaluator, and CLI execution path are future work. Do not describe these packs as executable until those components and tests have landed.

## Response contract for existing adapters

An adapter receives one JSON task on stdin and writes one JSON object to stdout. Claims should include evidence IDs. Evidence IDs establish traceability, not semantic entailment.

The evaluator is deliberately narrow. Human review and independent evaluators remain necessary for broader claims.
