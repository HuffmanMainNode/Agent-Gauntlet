# Challenge Authoring Standard

A challenge is a versioned, reviewable test contract. Loading a pack must never execute participant code, evaluate expressions, contact a network, or write outside its fixture directory.

## Pack layout

Each pack contains:
- `challenge.json`: identity, category, difficulty, seed, permissions, scoring, and resource limits.
- `fixture.json`: task, evidence, deterministic seed, and declared environment.
- `expected.json`: required behavior, expected findings, prohibited behavior, and known unknowns.

All files are UTF-8 JSON. Paths are relative to the pack directory. Do not add executable hooks or shell commands.

## Authoring requirements

1. Use a stable kebab-case ID. Increment the pack version when task meaning or scoring changes.
2. Mark generated fixtures synthetic. Never present synthetic records, names, tokens, or measurements as real evidence.
3. Give every factual fixture item a stable evidence ID and source label.
4. State authoritative precedence where it exists. Otherwise preserve unresolved conflicts.
5. State what is not established. Reward justified abstention and explicit uncertainty.
6. Declare seed, time budget, output limit, permissions, and dependencies.
7. Prefer exact structured assertions. Human review may supplement, not silently override, deterministic results.
8. Keep private data, credentials, and personal contact details out of public fixtures.
9. Include negative tests for tempting invalid answers.
10. Passing an assertion proves only that a declared contract was met, not general intelligence or safety.

## Review checklist

- [ ] Manifest conforms to `schemas/challenge.schema.json`.
- [ ] Fixture and expected output are valid JSON.
- [ ] Evidence references resolve.
- [ ] Seed reproduces the same fixture.
- [ ] No network, external dependency, or submission-code execution is needed to load the pack.
- [ ] Facts, inferences, conflicts, and unknowns are distinguished.
- [ ] Negative and malformed-response cases are tested.
- [ ] Scoring weights total 100.
- [ ] Changes are versioned and documented.

## Execution boundary

The current packs are declarative assets. A general manifest loader and pack scoring adapter are not yet implemented. Do not claim these packs run through the CLI until that integration exists.
