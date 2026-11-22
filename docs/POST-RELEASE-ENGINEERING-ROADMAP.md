# Post-release engineering roadmap

**Audit date:** 22 November 2026  
**Baseline:** `fcf6a085bf01b75c58b71e7ceb6d8c56e56d5511`  
**Scope:** Post-Commit 45 review of the public repository

This roadmap separates confirmed repository state, current design limits, and the next engineering sequence. It is not a claim that planned work has already been implemented.

## Current verified state

- The Commit 39-45 sequence is merged to `main`.
- PR #24 (unified execution supervisor), PR #25 (shared live/replay protocol validator), PR #26 (seeded pack-run evidence pipeline), PR #27 (schema validation in CI), PR #29 (deterministic seed-derived evidence-order variants), PR #30 (semantic assertions v1.1.0), and PR #31 (ten-domain semantic mutation tests) are merged to `main`.
- The final PR #24-#27 and #29-#31 revisions passed the Python 3.11, 3.12, and 3.13 CI matrix. PR #26 and PR #29 also passed the leaderboard submission gate; PR #27 validates the generated reference baseline against its schema in the 3.11 CI job.
- The signed-scorecard-claims correction from PR #18 is merged. Its tampering regression test and leaderboard gate passed; the full Python 3.11, 3.12, and 3.13 CI matrix passed on the merged revision.
- The latest main CI matrix and leaderboard workflow passed.
- At the PR #27 merged snapshot, there were no open issues or pull requests; subsequent engineering work is tracked through reviewable pull requests.
- The signer registry contains no identities and the submissions directory contains no scorecards. The leaderboard gate is therefore bootstrapped but has no external participants.
- The reference baseline is a synthetic, deterministic local benchmark. It is not an independent evaluation of third-party agents.

## Audit findings and design limits

### Confirmed strengths

1. **Evidence integrity:** deterministic case reconstruction, artifact hashes, and bundle verification are implemented.
2. **Execution hardening:** POSIX resource limits, minimal environment, temporary working directory, process-group cleanup, and bounded byte capture exist.
3. **Trust boundary:** filesystem isolation is explicitly not claimed.
4. **Tool permissions:** the interactive tool loop checks tool names against the active pack allowlist at dispatch and records denials.
5. **Scorecard claims:** PR #18 binds public scorecard claims to the OpenSSH attestation and rejects post-signing edits.
6. **Coverage disclosure:** GRI reports missing domains and zeroes domains affected by permission violations or injection breaches.

### Remaining engineering gaps

| Priority | Gap | Why it matters |
|---|---|---|
| P0 | Tool-loop containment parity | **Implemented in PR #24:** `run_contained` and `run_tool_loop` share child launch, environment scrubbing, namespace preflight, exact child-confirmed resource limits, and process-group cleanup. Tool-loop runs persist `containment.json` plus `execution.json`; successful result records include a canonical transcript digest. Remaining follow-up is cross-platform capability coverage and durable transcript artifacts for failed sessions. |
| P0 | Protocol/runtime parity tests | **Implemented in PR #25:** live JSONL sessions and offline replay use one `ProtocolValidator` for turn order, exact integer types, unique call IDs, frame bounds, protocol markers, and terminal final commits. Legacy offline traces may omit the marker; incorrect or explicit-null markers are rejected. |
| P1 | Tool-loop evidence completeness | **Partially implemented in PR #26:** completed pack runs bind transcript digests, containment reports, and execution records to each seed. Failed attempts retain bounded error records and any containment/execution artifacts written before failure. A protocol failure can still occur before a complete transcript is returned; durable partial transcript and bounded stdout/stderr capture for failed sessions remain follow-up work. |
| P1 | Pack-to-benchmark integration | **Implemented in PR #26 and extended in PR #29:** `pack-run` executes a trusted local `tool-loop-v1` adapter across explicit seeds, evaluates final commits, and writes verifiable evidence bundles. Each seed now deterministically permutes existing synthetic evidence records using a SHA-256 sort key. Evidence content is preserved; finite permutations can repeat. Domain-specific content generation remains outstanding. |
| P1 | Semantic assertion adequacy | **Strengthened in PR #30 and regression-tested in PR #31:** all ten packs now assert domain-critical response content, every reference oracle passes, and one semantic mutation per domain is required to fail with a score below 100. Broader adversarial mutation families and assertion-boundary tests remain useful follow-up work. |
| P1 | External evidence verification | The leaderboard validates signed claims and internal consistency. It does not retrieve evidence archives or replay remote runs. Add an optional evidence-bundle intake format with strict path, hash, size, and schema checks, then support independent replay. |
| P2 | Cross-platform containment matrix | The current containment contract is POSIX-focused and CI tests Linux. Add a documented capability matrix and run tests on additional supported POSIX platforms; strict mode must continue to fail closed. |
| P2 | Schema enforcement in CI | **Implemented in PR #27:** all declarative challenge manifests, generated GRI output, generated scorecards, and the generated reference baseline are validated against Draft 2020-12 schemas. `jsonschema` is development-only; runtime dependencies remain empty. |
| P2 | Release packaging | Publish a tagged version, reproducible source archive, SBOM/dependency statement, and signed release notes after the owner chooses a version. |

## Proposed implementation sequence

### Phase A: unify the execution supervisor

**Implemented and merged in PR #24; the Python 3.11/3.12/3.13 matrix and 25-seed reference workflow passed.** The shared `spawn_contained_process` and process-group lifecycle helpers are now used by both adversarial adapters and interactive tool-loop agents. The supervisor owns:
- environment construction and temporary working directories;
- resource limit application and post-application confirmation;
- namespace preflight and best-effort/strict behavior;
- process-group lifecycle, timeout cleanup, and reaping;
- bounded stdout/stderr readers and explicit truncation metadata;
- one serialized containment report format. Tool-loop sessions additionally write a run-scoped execution record with exit status, timeout state, output byte counts, and truncation flags.

Do not add claims of filesystem isolation. Keep untrusted code out of the host process unless an independently maintained OS sandbox is configured.

### Phase B: make tool-loop protocol conformance measurable

Use one protocol validator for live sessions and offline traces. Require exact integer turn indices (booleans must not pass as integers), unique call IDs, one outstanding call/result exchange, bounded frame size, exactly one final commit, and no frames after final commit.

**Implemented in PR #22:** transient failures are fixture-controlled, bound to a stable operation ID, emitted one 503 per actual tool call, and capped by a retry budget. Recovery credit is awarded only after observed retries and successful completion; caller-supplied failure counts and result values are ignored. Repeated 403s remain permission violations. Retry-delay values are deterministic guidance, not proof of actual wall-clock waiting.

**Shared conformance implemented and merged in PR #25:** live sessions and offline traces now call the same frame validator. The live path requires the protocol marker; replay preserves legacy marker-free traces while rejecting any incorrect marker that is present.

### Phase C: make challenge packs executable end-to-end

**Initial local execution/evidence pipeline implemented and merged in PR #26; deterministic presentation variants added in PR #29.** The `pack-run` and `verify-pack-run` commands provide per-pack, per-seed records. Each seed now orders the existing evidence records using a seed-scoped SHA-256 key. Evidence contents and identifiers remain unchanged; finite evidence sets mean different seeds may share a permutation. The next Phase C increment is domain-specific content variation with updated expected oracles and assertion contracts, not synthetic changes to evidence without matching scoring rules.

The implemented runner records:
- hash-bound challenge and per-seed fixture artifacts;
- operator-declared adapter name/version and command digest;
- tool-loop transcript and containment report when applicable;
- raw final response;
- deterministic assertion results and score;
- explicit permission/injection flags;
- canonical evidence manifest.

The runner preserves failed attempts and their available containment/execution artifacts. Next, add pack-specific content variants with matching oracle/assertion updates, a reproducible adapter descriptor that does not leak credentials, bounded parallelism only after deterministic ordering is proven, and a machine-readable coverage report for all ten domains.

### Phase D: federated evidence intake and independent replay

Keep signer registration operator-controlled. Define a portable submission archive containing the scorecard, detached signature, and referenced evidence bundles. Intake must reject path traversal, symlinks, oversized files, missing manifests, duplicate logical paths, and mismatched hashes.

Provide two separate states:
- **attested:** a registered key holder signed the declared scorecard and evidence digests;
- **reproduced:** an independent evaluator downloaded the archive, verified it, replayed the declared benchmark under a recorded environment, and matched the deterministic outputs.

Never collapse these into one green check.

### Phase E: release and community participation

After the P0/P1 work is complete:
1. Publish a tagged prototype release.
2. Invite external evaluators to register keys through a documented review process.
3. Accept signed submissions through pull requests, not direct writes to the default branch.
4. Require independent reproduction before promoting a submission to the reproduced-results view.
5. Publish challenge-version changes and benchmark comparability notes.

## Acceptance criteria for the next milestone

- Live and replay protocol validators share conformance tests. **Complete in PR #25.**
- Best-effort and strict tool-loop modes report their actual containment capabilities.
- All output limits are enforced without unbounded buffering.
- Every pack can be executed across a declared seed set and produces verifiable evidence. **Initial pipeline complete in PR #26; true seed-derived fixture variation remains open.**
- Schema validation runs in CI. **Complete in PR #27.**
- Attested and independently reproduced results are represented as distinct states.
- Python 3.11, 3.12, and 3.13 CI remains green with no third-party runtime dependency added.

## Non-goals

- No hosted service requirement.
- No paid API or subscription dependency.
- No claim that a signature proves agent honesty or truth.
- No claim that temporary directories or POSIX resource limits constitute filesystem sandboxing.
- No global ranking until external submissions and independent reproductions exist.


## Audit closeout update

PR #21 aligned best-effort namespace probing and exact turn-index typing. PR #22 replaced caller-controlled transient retry simulation with fixture-controlled, stateful retries and wired the observed adjustment into the pack CLI score. PR #24 completed the unified containment supervisor; PR #25 completed shared live/replay protocol validation; PR #26 added a verifiable per-seed pack execution pipeline; PR #27 made challenge, GRI, scorecard, and reference-baseline schemas enforceable in CI. All four final PR heads passed the Python 3.11/3.12/3.13 matrix. The P0 execution and protocol milestones are closed. PR #29 adds deterministic evidence-order variation; PR #30 strengthens semantic scoring contracts to v1.1.0; PR #31 requires one semantic mutation regression per domain. The next material gaps are pack-specific content variants with synchronized oracles, failed-session partial transcript preservation, cross-platform containment coverage, and independent evidence intake/replay.
