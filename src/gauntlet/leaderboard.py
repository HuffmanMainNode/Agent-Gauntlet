"""Portable, non-authoritative scorecards for independently published runs."""
from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

from .runner import canonical_bytes, digest, verify


def build_scorecard(bundle_paths: list[str], agent_name: str, model_id: str,
                    adapter_version: str, operator: str = "unspecified") -> dict:
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
            "malformed_claims": sum(x["malformed_claims"] for x in evaluations),
            "abstention_rate": round(sum(bool(x["abstained"]) for x in evaluations) / n, 4),
            "conflict_reports": sum(bool(x["conflict_reported"]) for x in evaluations),
        }
        evidence_refs.append({
            "suite": suite, "run_id": evidence["run_id"],
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
    now = datetime.now(timezone.utc).isoformat()
    scorecard = {
        "format": "agent-gauntlet-scorecard-v1",
        "created_at": now,
        "agent": {"name": agent_name, "model_id": model_id, "adapter_version": adapter_version},
        "operator": operator,
        "benchmark": {"suite_count": len(suites), "case_count": sum(x["cases"] for x in suites.values()),
                      "suites": suites},
        "balanced_behavior_index": balanced,
        "index_explanation": "Geometric mean of the submitted suites' behavior pass rates. Not a universal intelligence, safety, or capability score. Compare only identical challenge versions and suite coverage.",
        "evidence": evidence_refs,
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "attestation": "unsigned-operator-submission",
        "limitations": [
            "Evidence bundle integrity and evaluator consistency are verified; agent identity and honest execution are not.",
            "Evidence references do not prove semantic entailment or source truth.",
            "Only submitted suites are represented; missing suites are not scored as passes.",
            "Results are self-reported until independently reproduced.",
        ],
    }
    scorecard["scorecard_sha256"] = hashlib.sha256(canonical_bytes(scorecard)).hexdigest()
    return scorecard


def write_scorecard(scorecard: dict, output: str) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(scorecard))
    return path


def verify_scorecard(path: str) -> dict:
    scorecard = json.loads(Path(path).read_text(encoding="utf-8"))
    if scorecard.get("format") != "agent-gauntlet-scorecard-v1":
        raise ValueError("Unsupported scorecard format")
    recorded = scorecard.pop("scorecard_sha256", None)
    actual = hashlib.sha256(canonical_bytes(scorecard)).hexdigest()
    if not recorded or recorded != actual:
        raise ValueError("Scorecard digest mismatch")
    if not scorecard.get("evidence"):
        raise ValueError("Scorecard has no evidence references")
    return {"valid": True, "scorecard_sha256": recorded,
            "suites": scorecard["benchmark"]["suite_count"],
            "cases": scorecard["benchmark"]["case_count"],
            "attestation": scorecard.get("attestation")}
