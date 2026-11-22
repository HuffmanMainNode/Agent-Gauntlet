# Failure Ledger and Remediation Record

**Policy:** Failures are retained as engineering evidence. A failure is closed only when its cause is understood, the correction is committed, and a regression check demonstrates the correction. Historical workflow failures are never rewritten or deleted.

## Entry FG-2026-11-22-001: benchmark test fixtures missing required run metadata

- **Observed:** Five consecutive CI workflow runs failed on branch `feature/attested-run-metadata` during PR #4 development. The failure affected Python 3.11, 3.12, and 3.13.
- **Evidence:** GitHub Actions runs:
  - [45015885559](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45015885559)
  - [45015910194](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45015910194)
  - [45015913119](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45015913119)
  - [45015937451](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45015937451)
  - [45015940913](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45015940913)
- **Root cause:** Run creation was strengthened to require declared agent name, model ID, and adapter version. Several test fixtures still called `run_suite()` using the previous signature and omitted those fields. The production validation was correct; the tests were stale.
- **Correction:** Updated every affected test invocation to declare metadata. Scorecard generation checks that the declarations match the run manifest.
- **Regression coverage:** The complete test suite and Python 3.11/3.12/3.13 CI matrix passed on main at [run 45016099794](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45016099794).
- **Disposition:** Closed by correction and green post-merge matrix. Historical failures remain visible in Actions.

## Entry FG-2026-11-22-002: adapter execution errors could erase the run

- **Observed:** The adversarial runner invoked an adapter inside the seed loop without preserving handled execution errors. A timeout, non-zero exit, malformed JSON, or launch error could abort the entire run before the evidence bundle was written.
- **Impact:** Failed attempts could disappear from the result set, undermining the benchmark's requirement to preserve failures.
- **Correction:** Each handled adapter execution failure is now recorded as an individual failed case with error type, bounded diagnostic text, failed execution status, and zero score. The runner continues through the remaining seeds and writes the evidence bundle.
- **Regression coverage:** New tests cover adapter timeout, malformed output, duplicate seeds, zero-score failure retention, and bundle verification.
- **Disposition:** Closed by PR #5 and the passing Python 3.11/3.12/3.13 workflow [45016903375](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45016903375).

## Entry FG-2026-11-22-003: README described an obsolete execution boundary

- **Observed:** README statements described only the original fixture runner and said participant adapters were not executed, while the adversarial CLI had since gained an explicitly configured command adapter.
- **Impact:** Users could misunderstand what code executes locally and the associated trust boundary.
- **Correction:** README now distinguishes the fixture runner from the operator-supplied adapter and clearly states that the adapter is not sandboxed.
- **Disposition:** Closed by PR #5 and the passing Python 3.11/3.12/3.13 workflow [45016903375](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45016903375).

## Known warnings and limitations (not closed defects)

- GitHub Actions emitted a Node.js 20 deprecation warning for the selected action versions. It did not fail the latest workflow. Track and update action versions deliberately after compatibility verification.
- The command adapter is not a sandbox. Do not run untrusted adapters on a host containing sensitive data or credentials.
- Evidence hashes detect content changes; unsigned manifests do not authenticate the agent, model provider, operator, or honest execution.
- The current evaluator checks narrow declared contracts. Evidence-ID presence is not semantic entailment or independent fact verification.
- Live-source snapshots, cryptographic signatures, a hardened sandbox, confidence calibration, and independent semantic evaluation remain future work.

## Closure standard

Every new failure record should include:
1. Observable symptom and affected versions.
2. Reproduction command or workflow link.
3. Root cause, or an explicit statement that the cause remains unknown.
4. Impact and scope.
5. Corrective change and commit/PR reference.
6. Regression test or independent reproduction.
7. Status: open, investigating, fixed-pending-verification, closed, or accepted limitation.

Never mark a failure closed merely because a later unrelated CI run is green.

## Entry FG-2026-11-22-004: verifier did not independently validate execution state

- **Observed:** The adversarial verifier recomputed the deterministic behavior score but did not validate the execution-status record that can force a failed case to zero points.
- **Impact:** An internally inconsistent results file could claim a failed execution while retaining a successful evaluation, and the verifier would not reject that contradiction if the artifact digest inventory were also updated.
- **Correction:** The verifier now validates suite and seed inventory, deterministic case reconstruction, row shape, response type, execution status, failure diagnostics, and recomputes the evaluation with the correct zero-score rule for failed executions.
- **Regression coverage:** Added tests that alter a result and update its artifact digest to ensure the verifier still rejects a failed execution with a nonzero score, and rejects a case that does not match the deterministic seed generator.
- **Verification:** PR #6 merged after the Python 3.11/3.12/3.13 test matrix passed on the final branch commit. See [workflow 45017472323](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45017472323).
- **Disposition:** Closed by PR #6. The historical issue remains documented; unsigned-manifest forgery remains an explicit limitation.

## Entry FG-2026-11-22-005: public scorecards omitted execution-failure counts

- **Observed:** The scorecard exposed behavior pass rates and unsupported claims but did not show adapter execution failures.
- **Impact:** A reader could miss an important operational reliability dimension.
- **Correction:** Added per-suite `execution_failures` to scorecard generation and the scorecard schema.
- **Verification:** PR #6 merged after the Python 3.11/3.12/3.13 test matrix passed on the final branch commit. See [workflow 45017472323](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45017472323).
- **Disposition:** Closed by PR #6.


## Entry FG-2026-11-22-006: JSONL session input used an escaped delimiter

- **Observed:** The first multi-turn session regression test failed across Python 3.11, 3.12, and 3.13. The adapter process received one physical line containing literal backslash-n sequences rather than one JSON frame per line, so it emitted fewer responses than the protocol required.
- **Impact:** The new stateful session path incorrectly marked otherwise valid adapters as failed.
- **Root cause:** The session input serializer used a double-escaped newline delimiter.
- **Correction:** Changed the serializer to append an actual newline between JSON frames.
- **Regression coverage:** The persistent-session integration test requires one response for each of three input frames, checks state replacement and latest-evidence citation, and verifies the resulting evidence bundle.
- **Historical failed workflows:** [45018387153](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45018387153), [45018390260](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45018390260), [45018413453](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45018413453), [45018416413](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45018416413), and [45018435417](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45018435417) all exposed this same defect while the branch was being developed.
- **Verification:** The corrected branch passed the complete Python 3.11/3.12/3.13 matrix in [workflow 45018506152](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45018506152), and PR #8 was merged as `e4b8dfb7b127d4c0bfc8b11a54d42588e70aa5b6`.
- **Disposition:** Closed by correction, regression test, and passing cross-version CI. Historical failed workflows remain available as evidence.


## Entry FG-2026-11-22-007: detached signature did not bind public scorecard claims

- **Observed:** The OpenSSH payload committed the provenance root and embedded pack-result hashes, but scorecard fields used by the leaderboard gate (suite summaries, seed inventories, GRI disclosure, and evidence references) were outside that signed payload.
- **Impact:** A scorecard editor could alter those public claims and recalculate the ordinary scorecard checksum without changing the detached signature's signed provenance payload. This weakened the integrity boundary of federated admission.
- **Detection:** Post-release source audit of `attestation.py`, `leaderboard.py`, and the scorecard schema on 22 November 2026.
- **Correction in progress:** Add a canonical `scorecard_claims_sha256` to provenance, include it in the OpenSSH payload, verify it before admission, require it in the schema, and reconcile each suite's declared case count against its unique seed inventory.
- **Regression coverage:** Add a signed-scorecard tampering test that changes a suite pass rate and recomputes the ordinary scorecard checksum. The leaderboard gate must still reject the modified scorecard.
- **Verification:** The final PR branch passed the complete Python 3.11/3.12/3.13 test matrix in [workflow 45054991877](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45054991877). The leaderboard submission gate passed in [workflow 45054997644](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45054997644). The signed-claim tampering regression test passed.
- **Disposition:** Closed by PR #18 after the final cross-version CI matrix and leaderboard gate passed. Earlier red CI attempts remain in Actions as preserved development history.


## Entry FG-2026-11-22-008: interactive tool-loop containment and turn validation diverged

- **Observed:** The single-turn containment runner attempted best-effort Linux namespace isolation when supported, while the interactive tool-loop attempted namespaces only in strict mode. The live tool-loop also compared turn indices by equality without requiring an exact integer type, allowing JSON boolean `true` to compare equal to integer turn 1. Offline trace replay already rejected booleans.
- **Impact:** Best-effort containment behavior differed between execution paths, and live protocol validation accepted a frame that offline replay rejected.
- **Correction:** Make the tool-loop probe namespace capability in best-effort mode and use the same fail-closed strict-mode requirement. Report requested/effective mode, namespace activation, host OS, and the explicit non-sandbox filesystem boundary. Require exact integer turn indices in the live process path.
- **Regression coverage:** Add tests for best-effort namespace probing, effective capability reporting, strict-mode rejection when network isolation is disabled, and boolean turn-index rejection in both live and offline protocol paths.
- **Disposition:** Fixed-pending-verification until the full Python 3.11/3.12/3.13 matrix passes.


## Entry FG-2026-11-22-009: containment import formatting regression during PR #20

- **Observed:** Several consecutive PR #20 CI attempts failed test collection on Python 3.11, 3.12, and 3.13 with the same syntax error in the new multi-line containment import.
- **Root cause:** The initial source edit wrote the literal backslash-n escape into the Python import statement instead of inserting a physical newline. The first corrective edit did not match the actual one-backslash sequence, so subsequent CI attempts continued to fail until the exact source text was inspected.
- **Correction:** Replaced the literal escape with a real line break before the next CI attempt.
- **Evidence:** Failed workflows [45055729009](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45055729009), [45055738895](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45055738895), [45055755569](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45055755569), [45055770229](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45055770229), and [45055775760](https://github.com/HuffmanMainNode/Agent-Gauntlet/actions/runs/45055775760). The exact literal escape has now been replaced with a physical newline; final disposition awaits the complete matrix.
- **Disposition:** Fixed-pending-verification. The historical failed run remains visible.
