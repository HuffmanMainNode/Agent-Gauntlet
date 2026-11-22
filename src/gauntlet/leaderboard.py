"""Portable, non-authoritative scorecards for independently published runs."""
from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

from .runner import canonical_bytes, digest, verify
from .attestation import (build_provenance, verify_scorecard_signature, scorecard_claims_digest, NAMESPACE, AttestationError)
from .gri import build_gri, DEFAULT_DOMAINS


def build_scorecard(bundle_paths: list[str], agent_name: str, model_id: str,
                    adapter_version: str, operator: str = "unspecified",
                    repo_commit: str | None = None,
                    pack_result_paths: list[str] | None = None) -> dict:
    if not bundle_paths:
        raise ValueError("At least one evidence bundle is required")
    if not agent_name.strip() or not model_id.strip() or not adapter_version.strip():
        raise ValueError("Agent name, model ID, and adapter version are required")
    suites = {}
    evidence_refs = []
    for raw_path in bundle_paths:
        path = Path(raw_path).resolve()
        verified = verify(path)
        evidence = json.loads((path / "evidence.json").read_text(encoding="utf-8"))
        if evidence.get("format") != "agent-gauntlet-adversarial-evidence-v1":
            raise ValueError(f"Not an adversarial evidence bundle: {path}")
        rows = json.loads((path / "results.json").read_text(encoding="utf-8"))
        declared_agent = evidence.get("agent")
        expected_agent = {"name": agent_name, "model_id": model_id, "adapter_version": adapter_version}
        if declared_agent != expected_agent:
            raise ValueError("Scorecard metadata does not match run-time evidence manifest")
        if evidence.get("operator", "unspecified") != operator:
            raise ValueError("Operator metadata does not match run-time evidence manifest")
        suite = evidence["suite"]
        if suite in suites:
            raise ValueError(f"Duplicate suite bundle supplied: {suite}")
        evaluations = [row["evaluation"] for row in rows]
        if not evaluations:
            raise ValueError(f"Empty suite bundle: {suite}")
        n = len(evaluations)
        suites[suite] = {
            "cases": n,
            "behavior_pass_rate": round(sum(bool(x["behavior_pass"]) for x in evaluations) / n, 4),
            "mean_case_score": round(sum(x["score"] for x in evaluations) / n, 2),
            "unsupported_claims": sum(x["unsupported_claims"] for x in evaluations),
            "execution_failures": sum(row.get("execution", {}).get("status") == "failed" for row in rows),
            "malformed_claims": sum(x["malformed_claims"] for x in evaluations),
            "abstention_rate": round(sum(bool(x["abstained"]) for x in evaluations) / n, 4),
            "conflict_reports": sum(bool(x["conflict_reported"]) for x in evaluations),
        }
        evidence_refs.append({
            "suite": suite, "run_id": evidence["run_id"], "seeds": evidence.get("seeds", []),
            "evidence_sha256": digest((path / "evidence.json").read_bytes()),
            "results_sha256": digest((path / "results.json").read_bytes()),
            "verified_artifacts": verified["checked_artifacts"],
        })
    rates = [row["behavior_pass_rate"] for row in suites.values()]
    # Geometric mean punishes a lopsided profile. This is a summary, not an intelligence score.
    product = 1.0
    for rate in rates:
        product *= rate
    balanced = round(product ** (1 / len(rates)) * 100, 2)
    pack_results = [json.loads(Path(raw).read_text(encoding="utf-8")) for raw in (pack_result_paths or [])]
    gri = build_gri(pack_results, DEFAULT_DOMAINS)
    provenance = build_provenance(bundle_paths, repo_commit=repo_commit, additional_files=pack_result_paths)
    now = datetime.now(timezone.utc).isoformat()
    scorecard = {
        "format": "agent-gauntlet-scorecard-v1",
        "created_at": now,
        "agent": {"name": agent_name, "model_id": model_id, "adapter_version": adapter_version},
        "operator": operator,
        "benchmark": {"suite_count": len(suites), "case_count": sum(x["cases"] for x in suites.values()),
                      "suites": suites},
        "balanced_behavior_index": balanced,
        "gri": gri,
        "pack_results": pack_results,
        "index_explanation": "Geometric mean of the submitted suites' behavior pass rates. Not a universal intelligence, safety, or capability score. Compare only identical challenge versions and suite coverage.",
        "evidence": evidence_refs,
        "provenance": provenance,
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "attestation": {"status": "unsigned", "scheme": None, "identity": None, "namespace": None, "signature_file": None, "signed_object": None},
        "limitations": [
            "Evidence bundle integrity and evaluator consistency are verified; agent identity and honest execution are not.",
            "Evidence references do not prove semantic entailment or source truth.",
            "Only submitted suites are represented; missing suites are not scored as passes.",
            "Results are self-reported until independently reproduced.",
        ],
    }
    scorecard["provenance"]["scorecard_claims_sha256"] = scorecard_claims_digest(scorecard)
    scorecard["scorecard_sha256"] = hashlib.sha256(canonical_bytes(scorecard)).hexdigest()
    return scorecard


def write_scorecard(scorecard: dict, output: str) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(scorecard))
    return path


def verify_scorecard(path: str, signature_path: str | None = None,
                     allowed_signers: str | None = None, signer_identity: str | None = None,
                     namespace: str = NAMESPACE) -> dict:
    scorecard = json.loads(Path(path).read_text(encoding="utf-8"))
    if scorecard.get("format") != "agent-gauntlet-scorecard-v1":
        raise ValueError("Unsupported scorecard format")
    recorded = scorecard.pop("scorecard_sha256", None)
    actual = hashlib.sha256(canonical_bytes(scorecard)).hexdigest()
    if not recorded or recorded != actual:
        raise ValueError("Scorecard digest mismatch")
    if not scorecard.get("evidence"):
        raise ValueError("Scorecard has no evidence references")
    pack_results = scorecard.get("pack_results", [])
    if not isinstance(pack_results, list):
        raise ValueError("Scorecard pack_results must be a list")
    recomputed_gri = build_gri(pack_results, DEFAULT_DOMAINS)
    if recomputed_gri != scorecard.get("gri"):
        raise ValueError("Scorecard GRI does not match its embedded pack results")
    provenance = scorecard.get("provenance", {})
    if not isinstance(provenance, dict):
        raise ValueError("Scorecard provenance must be an object")
    if provenance.get("scorecard_claims_sha256") != scorecard_claims_digest(scorecard):
        raise ValueError("Scorecard claims do not match signed provenance digest")
    if provenance.get("pack_result_count") != len(pack_results):
        raise ValueError("Scorecard pack-result count does not match provenance")
    from .runner import digest
    if any(not isinstance(item, dict) or not isinstance(item.get("pack_id"), str) for item in pack_results):
        raise ValueError("Scorecard contains malformed pack results")
    expected_hashes = sorted([{"pack_id": item["pack_id"], "seed": item.get("seed", "unspecified"),
                               "sha256": digest(canonical_bytes(item))} for item in pack_results],
                             key=lambda item: (item["pack_id"], str(item["seed"]), item["sha256"]))
    if expected_hashes != provenance.get("pack_result_hashes"):
        raise ValueError("Scorecard pack results do not match signed provenance hashes")
    attestation = scorecard.get("attestation", {})
    signature_inputs = (signature_path, allowed_signers, signer_identity)
    if any(signature_inputs) and not all(signature_inputs):
        raise ValueError("signature, allowed_signers, and signer_identity must be supplied together")
    signature_report = None
    if all(signature_inputs):
        signature_report = verify_scorecard_signature(
            scorecard, signature_path, allowed_signers, signer_identity, namespace
        )
    status = attestation.get("status", "unknown") if isinstance(attestation, dict) else "legacy-unsigned"
    if status == "signed" and signature_report is None:
        status = "signature-present-not-verified"
    elif signature_report:
        status = "verified"
    return {"valid": True, "scorecard_sha256": recorded,
            "suites": scorecard["benchmark"]["suite_count"],
            "cases": scorecard["benchmark"]["case_count"],
            "attestation": status, "signature": signature_report}



REQUIRED_LEADERBOARD_SUITES = (
    "hallucination", "contradiction", "injection", "variable", "ambiguity", "stateful",
)


def verify_leaderboard_directory(directory: str, allowed_signers: str,
                                 registered_signers: str,
                                 minimum_seeds: int = 25) -> dict:
    """Fail-closed inclusion gate for signed, complete, reproducible submissions."""
    if type(minimum_seeds) is not int or minimum_seeds < 1:
        raise ValueError("minimum_seeds must be a positive integer")
    submission_dir = Path(directory)
    trust_file = Path(allowed_signers)
    registry_file = Path(registered_signers)
    if not submission_dir.is_dir() or not trust_file.is_file() or not registry_file.is_file():
        raise ValueError("submission directory, allowed_signers, and signer registry must exist")
    registry = json.loads(registry_file.read_text(encoding="utf-8"))
    identities = registry.get("registered_identities") if isinstance(registry, dict) else None
    if not isinstance(identities, list) or any(not isinstance(item, str) or not item for item in identities):
        raise ValueError("registered signer registry must contain registered_identities")
    if len(identities) != len(set(identities)):
        raise ValueError("registered signer identities must be unique")
    submissions = sorted(path for path in submission_dir.glob("*.json") if path.is_file() and not path.is_symlink())
    verified = []
    for path in submissions:
        card = json.loads(path.read_text(encoding="utf-8"))
        attestation = card.get("attestation", {})
        identity = attestation.get("identity") if isinstance(attestation, dict) else None
        if not identity or identity not in identities:
            raise ValueError(f"unregistered signer for submission {path.name}")
        signature_name = attestation.get("signature_file")
        if (not isinstance(signature_name, str) or not signature_name
                or Path(signature_name).name != signature_name):
            raise ValueError(f"invalid detached signature path in {path.name}")
        signature_path = path.parent / signature_name
        if signature_path.is_symlink():
            raise ValueError(f"signature file may not be a symlink: {path.name}")
        verify_report = verify_scorecard(
            str(path), str(signature_path), str(trust_file), identity,
            attestation.get("namespace", NAMESPACE),
        )
        benchmark = card.get("benchmark", {})
        suites = benchmark.get("suites", {}) if isinstance(benchmark, dict) else {}
        if (not isinstance(suites, dict) or set(suites) != set(REQUIRED_LEADERBOARD_SUITES)
                or benchmark.get("suite_count") != len(REQUIRED_LEADERBOARD_SUITES)
                or benchmark.get("case_count") != sum(
                    item.get("cases", -1) for item in suites.values() if isinstance(item, dict)
                )):
            raise ValueError(f"submission {path.name} does not have a consistent complete suite inventory")
        evidence_refs = card.get("evidence", [])
        if (not isinstance(evidence_refs, list)
                or {item.get("suite") for item in evidence_refs if isinstance(item, dict)}
                   != set(REQUIRED_LEADERBOARD_SUITES)
                or len(evidence_refs) != len(REQUIRED_LEADERBOARD_SUITES)):
            raise ValueError(f"submission {path.name} has incomplete or malformed evidence references")
        seeds_by_suite = {}
        for reference in evidence_refs:
            if not isinstance(reference, dict) or reference.get("suite") in seeds_by_suite:
                raise ValueError(f"submission {path.name} has duplicate or malformed suite evidence")
            seeds = reference.get("seeds")
            if (not isinstance(seeds, list) or any(type(seed) is not int for seed in seeds)
                    or len(seeds) != len(set(seeds))):
                raise ValueError(f"submission {path.name} has invalid seed inventory")
            seeds_by_suite[reference["suite"]] = seeds
        for name in REQUIRED_LEADERBOARD_SUITES:
            if (not isinstance(suites[name], dict) or type(suites[name].get("cases")) is not int
                    or suites[name]["cases"] < minimum_seeds
                    or len(seeds_by_suite.get(name, [])) != suites[name]["cases"]
                    or len(seeds_by_suite.get(name, [])) < minimum_seeds):
                raise ValueError(f"submission {path.name} has fewer than {minimum_seeds} unique seeds in a required suite")
        gri = card.get("gri", {})
        if (not isinstance(gri, dict) or gri.get("coverage_ratio") != 1.0
                or gri.get("missing_domains") != [] or gri.get("complete") is not True
                or gri.get("expected_domains") != sorted(DEFAULT_DOMAINS)):
            raise ValueError(f"submission {path.name} has incomplete GRI domain coverage")
        verified.append({"scorecard": path.name, "identity": identity,
                         "scorecard_sha256": verify_report["scorecard_sha256"],
                         "gri_score": gri["composite_score"],
                         "suite_count": len(REQUIRED_LEADERBOARD_SUITES),
                         "minimum_seeds_per_suite": minimum_seeds})
    return {"valid": True, "submissions_checked": len(verified),
            "minimum_seeds_per_suite": minimum_seeds, "submissions": verified}
