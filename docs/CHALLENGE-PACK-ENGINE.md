# Challenge Pack Engine

The pack engine loads versioned, data-only challenge directories and evaluates a separately produced JSON response against deterministic, challenge-authored assertions.

Run one pack with: python -m gauntlet pack --name technical-reasoning --response response.json

Run all packs with: python -m gauntlet pack --all --responses-dir responses/

For --all, the response directory must contain one JSON object per pack, named <pack-id>.json. The operator runs their agent separately, supplies the fixture as task input, and saves its JSON response. The engine never executes an agent or submission code.

Each pack contains challenge.json, fixture.json, and expected.json. The manifest declares fixed seed, synthetic provenance, permissions, resource limits, scoring weights, and assertion rules. The loader rejects unknown fields, unsupported permissions, duplicate JSON keys, path traversal, symlink escapes, mismatched fixture IDs/seeds, non-synthetic fixtures, oversized inputs, and unsupported operators.

Supported assertions: exact_match, numeric_tolerance, must_abstain, must_surface_conflict_ids, forbidden_substrings, required_fields. Every pack must cover behavior, traceability, and format dimensions. Dimension scores are normalized to 0-100 and combined using weights totaling 100.

The supported permission allowlist is network disabled, bundled-fixture-only data, and no submission-code execution. The engine passes no filesystem paths or tool handles to an agent and evaluates a response file only. This is a data-contract evaluator, not an OS sandbox. See CONTAINMENT.md.
