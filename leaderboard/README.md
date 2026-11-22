# Public score submissions

This directory defines the contribution format, not a centrally trusted ranking service.

## Submit a result

1. Run the challenge suites locally against your own agent.
2. Preserve the complete evidence bundles.
3. Generate a scorecard with `agent-gauntlet scorecard`.
4. Verify it with `agent-gauntlet verify-scorecard`.
5. Open a pull request adding the scorecard JSON under `leaderboard/submissions/` and link the evidence bundle using a durable public artifact URL or attach the bundle to the submission.
6. Disclose model/provider/version, adapter version, operator, run date, suite coverage, and whether the run was independently reproduced.

Example:

```sh
agent-gauntlet scorecard \
  --bundle artifacts/adversarial/RUN_ID_1 \
  --bundle artifacts/adversarial/RUN_ID_2 \
  --agent-name "Example Agent" \
  --model-id "provider/model/version" \
  --adapter-version "git:abc123" \
  --operator "community-handle" \
  --output scorecard.json

agent-gauntlet verify-scorecard --scorecard scorecard.json

# Optional detached signature using an existing OpenSSH private key
agent-gauntlet scorecard \
  --bundle artifacts/adversarial/RUN_ID_1 \
  --agent-name "Example Agent" --model-id "provider/model/version" \
  --adapter-version "git:abc123" --operator "community-handle" \
  --signing-key ~/.ssh/gauntlet_ed25519 \
  --signer-identity "community-handle@example.invalid" \
  --output signed-scorecard.json

# Verify using a locally maintained OpenSSH allowed_signers trust file
agent-gauntlet verify-scorecard --scorecard signed-scorecard.json \
  --signature signed-scorecard.json.sig \
  --allowed-signers ~/.ssh/gauntlet_allowed_signers \
  --signer-identity "community-handle@example.invalid"
```

## Rules

- Never submit fixture-agent scores as real model results.
- Never remove failed cases from a completed run.
- Never compare different challenge versions as if they were identical.
- Partial suite coverage must be shown as partial. Missing suites are not zero failures or passes.
- Scorecards are self-reported. They remain unsigned unless the operator explicitly signs them with OpenSSH. A scorecard digest detects accidental or later modification; it does not authenticate the submitter. A valid OpenSSH signature proves only that the holder of the corresponding private key signed the canonical bundle-root digest and its included provenance fields. It does not prove agent identity, honest execution, or behavioral truth.
- The project maintainers may label entries as submitted, schema-valid, evidence-referenced, independently reproduced, disputed, or withdrawn. These are distinct statuses.
- No score is a certification of safety, alignment, general intelligence, or deployment readiness.

The long-term goal is a federated board: independent mirrors can ingest the same scorecard format and apply transparent inclusion policies.


## Provenance and signatures

The scorecard provenance root is SHA-256 over sorted canonical path/hash pairs for the supplied evidence bundle files, the source repository commit, and the current declarative challenge-pack file hashes. The algorithm identifier is recorded in the scorecard. Operators can supply `--repo-commit` when building a scorecard from a detached export; otherwise the local Git HEAD is used when available and `unknown` is recorded when it is not.

OpenSSH signing is optional and uses `ssh-keygen -Y sign` with the `agent-gauntlet` namespace by default. Verification uses the verifier's own `allowed_signers` file and expected signer identity. Public keys are not trusted merely because they appear in a submitted scorecard. Keep private keys private and distribute trusted public keys through an independently managed channel.

The detached signature covers the canonical attestation payload containing `bundle_root_sha256`, repository commit, challenge-pack hashes, and root algorithm. It is a custody/provenance signature, not a behavioral attestation. A signed result may still be false, manipulated before signing, or produced by an incorrectly identified agent.
