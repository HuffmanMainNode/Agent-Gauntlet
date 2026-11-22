# Challenge Pack Engine

The pack engine loads versioned, data-only challenge directories and evaluates a separately produced JSON response against deterministic, challenge-authored assertions.

Run one pack with: python -m gauntlet pack --name technical-reasoning --response response.json

Run all packs with: python -m gauntlet pack --all --responses-dir responses/

For --all, the response directory must contain one JSON object per pack, named <pack-id>.json. The operator runs their agent separately, supplies the fixture as task input, and saves its JSON response. The engine never executes an agent or submission code.

Each pack contains challenge.json, fixture.json, and expected.json. The manifest declares fixed seed, synthetic provenance, permissions, resource limits, scoring weights, and assertion rules. The loader rejects unknown fields, unsupported permissions, duplicate JSON keys, path traversal, symlink escapes, mismatched fixture IDs/seeds, non-synthetic fixtures, oversized inputs, and unsupported operators.

Supported assertions: exact_match, numeric_tolerance, must_abstain, must_surface_conflict_ids, forbidden_substrings, required_fields. Every pack must cover behavior, traceability, and format dimensions. Dimension scores are normalized to 0-100 and combined using weights totaling 100.

The supported permission allowlist is network disabled, bundled-fixture-only data, and no submission-code execution. The engine passes no filesystem paths or tool handles to an agent and evaluates a response file only. This is a data-contract evaluator, not an OS sandbox. See CONTAINMENT.md.


## Interactive tool-loop-v1

Packs declare a per-pack `permissions.tools` allowlist. Run an interactive local agent against a pack with:

```sh
python -m gauntlet tool-loop --name evidence-integrity --adapter-json '["python","agent.py"]'
```

The runner sends `TASK_INIT`, then accepts sequential `TOOL_CALL` events and returns `TOOL_RESULT` frames until `FINAL_COMMIT`. Tool calls are intercepted before dispatch. Denials return deterministic HTTP-style 403 results and increment permission-violation counters. The deterministic mock tools are `lookup_evidence`, `calculate_sum`, and `transient_lookup`; they do not access external services. Transient failures use a bounded three-attempt schedule with recorded exponential delays. Repeated denied calls are counted as retry loops.

The interactive adapter runs trusted operator-supplied code in a separate process group with POSIX resource limits, bounded output, a wall-clock deadline, and process-group cleanup. It is not a filesystem sandbox. The protocol transcript and counters are evidence of what this local runner observed, not proof of agent identity or honesty.


## Seeded local execution and evidence bundles

Use `python -m gauntlet pack-run` to execute a trusted local `tool-loop-v1` adapter for one pack across an explicit, unique seed list. Each run emits a result row with the final response, deterministic assertion evaluation, transcript digest, containment report, execution status, and a fixture hash. The bundle inventory covers the challenge manifest, per-seed fixtures, result and summary records, environment record, and run-scoped containment/execution artifacts.

Failed attempts are retained with a bounded error description and any containment/execution artifacts written before failure. Verify a bundle with `python -m gauntlet verify-pack-run --bundle PATH`; verification checks the inventory, fixture identities and hashes, transcript digests, and recomputes completed evaluations from the recorded response.

The adapter command is not copied into the public evidence manifest because command-line arguments may contain credentials. The manifest records its SHA-256 together with the operator-declared adapter name and version. Keep the exact command and source revision separately for reproduction.

Each run seed deterministically permutes the existing synthetic evidence records using a seed-scoped SHA-256 sort key. Evidence contents and identifiers remain unchanged; presentation order varies, and finite evidence sets mean different seeds can share a permutation. This is a presentation-order variant, not newly synthesized evidence. Local adapter code is operator-trusted and is not filesystem-sandboxed.


## Semantic assertion coverage (challenge contract v1.1.0)

The ten challenge manifests now carry stronger, versioned assertions. The scoring contract checks decision labels and provenance as before, and also checks domain-critical answer content: numeric results and units, temporal current state, authorization decisions, scientific limitations, recovery actions, resource totals, and canonical reproducibility outputs.

The reproducibility pack's prior wildcard assertion compared an evidence-ID array to an object and could never express the intended contract. It now checks the normalized claim and evidence-ID array separately. The technical-reasoning pack now checks the actual byte total, unit, and calculation rather than accepting a correct behavior label with an incorrect number.

The checked-in expected files act as reference oracles. CI removes oracle-only annotations such as `prohibited` and `forbidden_substrings` before evaluating the expected agent response, then requires every manifest assertion to pass for every pack. Negative tests mutate numeric and scientific fields to confirm that semantic errors reduce the score.

A pack assertion change is a scoring-contract change. All ten manifests were advanced to version `1.1.0`; old and new scorecards should not be treated as directly comparable without recording the pack version.
