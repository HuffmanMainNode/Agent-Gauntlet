# Post-release engineering roadmap

**Audit date:** 22 November 2026  
**Baseline:** `ea82dff252fa936989e3f66a09ddc4bdb7c76bf4`  
**Scope:** Post-Commit 45 review of the public repository

This roadmap separates confirmed repository state, current design limits, and the next engineering sequence. It is not a claim that planned work has already been implemented.

## Current verified state

- The Commit 39-45 sequence is merged to `main`.
- The signed-scorecard-claims correction from PR #18 is merged. Its tampering regression test and leaderboard gate passed; the full Python 3.11, 3.12, and 3.13 CI matrix passed on the merged revision.
- The latest main CI matrix and leaderboard workflow passed.
- There are no open issues or pull requests on the audited main snapshot.
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
| P0 | Tool-loop containment parity | `run_tool_loop` applies resource limits and strict namespace enforcement, but its best-effort mode does not currently attempt the same namespace capability path as `run_contained`. The two execution paths should share one containment supervisor. |
| P0 | Protocol/runtime parity tests | Keep live subprocess behavior and offline trace replay aligned for turn typing, frame limits, duplicate calls, FINAL_COMMIT handling, 403 accounting, and transient retry behavior. |
| P1 | Tool-loop evidence completeness | Persist a structured containment report, stdout/stderr truncation flags, timeout/exit status, and a canonical transcript digest alongside the tool-loop report. |
| P1 | Pack-to-benchmark integration | The declarative pack evaluator scores supplied response JSON. It does not by itself create agent responses. Make the adapter execution path explicit and connect tool-loop sessions to a reproducible per-seed pack result pipeline. |
| P1 | External evidence verification | The leaderboard validates signed claims and internal consistency. It does not retrieve evidence archives or replay remote runs. Add an optional evidence-bundle intake format with strict path, hash, size, and schema checks, then support independent replay. |
| P2 | Cross-platform containment matrix | The current containment contract is POSIX-focused and CI tests Linux. Add a documented capability matrix and run tests on additional supported POSIX platforms; strict mode must continue to fail closed. |
| P2 | Schema enforcement in CI | Validate every committed challenge pack, scorecard, GRI report, and reference baseline against the checked-in schemas as a required CI job. |
| P2 | Release packaging | Publish a tagged version, reproducible source archive, SBOM/dependency statement, and signed release notes after the owner chooses a version. |

## Proposed implementation sequence

### Phase A: unify the execution supervisor

Create a single internal supervisor used by both adversarial adapters and tool-loop agents. It should own:
- environment construction and temporary working directories;
- resource limit application and post-application confirmation;
- namespace preflight and best-effort/strict behavior;
- process-group lifecycle, timeout cleanup, and reaping;
- bounded stdout/stderr readers and explicit truncation metadata;
- one serialized containment report format.

Do not add claims of filesystem isolation. Keep untrusted code out of the host process unless an independently maintained OS sandbox is configured.

### Phase B: make tool-loop protocol conformance measurable

Use one protocol validator for live sessions and offline traces. Require exact integer turn indices (booleans must not pass as integers), unique call IDs, one outstanding call/result exchange, bounded frame size, exactly one final commit, and no frames after final commit.

Make retry scoring explicit and deterministic. A repeated 403 should remain a permission violation and must never earn recovery credit. Transient 503 recovery credit should be capped and based on observed bounded retry frames, not merely a caller-supplied number in a tool argument.

### Phase C: make challenge packs executable end-to-end

Add a per-pack, per-seed execution record:
- immutable challenge and fixture hashes;
- adapter identity/version and command declaration;
- tool-loop transcript and containment report when applicable;
- raw final response;
- deterministic assertion results and score;
- explicit permission/injection flags;
- canonical evidence manifest.

The runner should preserve failed attempts as records, support bounded parallelism only after deterministic ordering is proven, and emit a machine-readable coverage report for all ten domains.

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

- Live and replay protocol validators share conformance tests.
- Best-effort and strict tool-loop modes report their actual containment capabilities.
- All output limits are enforced without unbounded buffering.
- Every pack can be executed across a declared seed set and produces verifiable evidence.
- Schema validation runs in CI.
- Attested and independently reproduced results are represented as distinct states.
- Python 3.11, 3.12, and 3.13 CI remains green with no third-party runtime dependency added.

## Non-goals

- No hosted service requirement.
- No paid API or subscription dependency.
- No claim that a signature proves agent honesty or truth.
- No claim that temporary directories or POSIX resource limits constitute filesystem sandboxing.
- No global ranking until external submissions and independent reproductions exist.
