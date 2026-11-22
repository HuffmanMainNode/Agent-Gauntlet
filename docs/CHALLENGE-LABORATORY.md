# Challenge Laboratory

The Challenge Laboratory is the public catalog of deterministic, synthetic proving tasks for Agent Gauntlet.

## Initial catalog

| Pack | Category | Level | Capability |
|---|---|---|---|
| `evidence-integrity` | Evidence integrity | Advanced | Preserve conflicting primary records |
| `temporal-reasoning` | Temporal reasoning | Advanced | Apply authoritative updates without erasing history |
| `instruction-resistance` | Instruction resistance | Expert | Treat hostile evidence as untrusted data |
| `multi-agent-coordination` | Multi-agent coordination | Expert | Reconcile disagreement without vote laundering |
| `technical-reasoning` | Technical reasoning | Foundation | Exact traceable calculation |
| `privacy-authorization` | Privacy and authorization | Expert | Enforce disclosure boundaries |
| `scientific-reasoning` | Scientific reasoning | Advanced | Separate observation from causation |
| `failure-recovery` | Failure recovery | Expert | Recover from ambiguous commit outcome |
| `resource-optimization` | Resource optimization | Advanced | Optimize indivisible tasks under a budget |
| `reproducibility` | Reproducibility | Frontier | Canonical independent reproduction |

All initial fixtures are synthetic and fixed-seed. No real personal data, live credentials, or external evidence is included.

## Execution status

These packs are declarative challenge assets, not yet connected to a general-purpose CLI pack runner. The existing executable adversarial suites remain separate. The manifest schema and structural tests validate pack structure; they do not imply a general pack evaluator exists.

## Next engineering gates

1. Strict manifest/fixture loader with path containment and schema validation.
2. Pack-specific assertion evaluation and negative tests.
3. CLI discovery and execution after loader/evaluator tests pass.
4. Independent reproduction and optional signed scorecards.
5. Never execute challenge-supplied code during loading or scoring.
