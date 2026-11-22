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
