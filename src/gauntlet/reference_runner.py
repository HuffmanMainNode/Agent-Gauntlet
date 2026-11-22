"""Reproducible, local reference-agent matrix for evaluator calibration."""
from __future__ import annotations
import json
import sys
from pathlib import Path

from .adversarial_runner import run_suite
from .runner import canonical_bytes, digest, verify

ROOT = Path(__file__).resolve().parents[2]
SUITES = ("hallucination", "contradiction", "injection", "variable", "ambiguity", "stateful")
PROFILES = {
    "demo-good": SUITES,
    "demo-bad": SUITES,
    "demo-vulnerable-injection": ("injection",),
    "demo-stale-state": ("stateful",),
}


def run_reference_matrix(output_root: str | Path = "artifacts/reference",
                         seeds: list[int] | None = None) -> Path:
    """Run the fixed-seed reference matrix and write a verified baseline index."""
    seeds = list(range(1, 26)) if seeds is None else list(seeds)
    if not seeds or len(seeds) > 100 or any(type(seed) is not int for seed in seeds):
        raise ValueError("reference seeds must be 1..100 unique integers")
    if len(set(seeds)) != len(seeds):
        raise ValueError("reference seeds must be unique")
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for profile, suites in PROFILES.items():
        script = ROOT / "examples" / "reference_agents" / f"{profile.replace('-', '_')}.py"
        command = [sys.executable, str(script)]
        for suite in suites:
            protocol = "jsonl-session" if suite == "stateful" else "single-turn"
            bundle = run_suite(
                suite, command, seeds, output / profile, timeout_seconds=15,
                agent_name=f"Agent Gauntlet Reference: {profile}",
                model_id="local/deterministic-reference-agent",
                adapter_version="agent-gauntlet-reference-v1",
                operator="agent-gauntlet-reference-suite", protocol=protocol,
            )
            verified = verify(bundle)
            rows = json.loads((bundle / "results.json").read_text(encoding="utf-8"))
            evidence = json.loads((bundle / "evidence.json").read_text(encoding="utf-8"))
            evaluations = [row["evaluation"] for row in rows]
            record = {
                "profile": profile,
                "suite": suite,
                "seeds": seeds,
                "run_id": evidence["run_id"],
                "bundle": bundle.resolve().relative_to(output.resolve()).as_posix(),
                "bundle_evidence_sha256": digest((bundle / "evidence.json").read_bytes()),
                "verified": verified["valid"],
                "cases": len(rows),
                "mean_score": round(sum(item["score"] for item in evaluations) / len(evaluations), 2),
                "behavior_passes": sum(bool(item["behavior_pass"]) for item in evaluations),
                "behavior_pass_rate": round(sum(bool(item["behavior_pass"]) for item in evaluations) / len(evaluations), 4),
                "execution_failures": sum(row["execution"]["status"] == "failed" for row in rows),
                "unsupported_claims": sum(item["unsupported_claims"] for item in evaluations),
            }
            records.append(record)
    report = {
        "format": "agent-gauntlet-reference-baseline-v1",
        "synthetic": True,
        "seed_count": len(seeds),
        "seed_values": seeds,
        "profile_count": len(PROFILES),
        "suite_run_count": len(records),
        "case_count": sum(item["cases"] for item in records),
        "all_bundles_verified": all(item["verified"] for item in records),
        "runs": records,
        "limitations": [
            "These are deterministic synthetic reference programs, not hosted model results.",
            "The good and deliberately failing agents are calibration controls, not claims about external agents.",
            "Evidence hashes and evaluator recomputation do not prove semantic truth or general reliability.",
        ],
    }
    report["baseline_sha256"] = digest(canonical_bytes(report))
    path = output / "reference-baseline.json"
    path.write_bytes(canonical_bytes(report))
    return path


def verify_reference_baseline(path: str | Path) -> dict:
    """Verify the baseline digest and independently re-verify every referenced bundle."""
    report_path = Path(path).resolve()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("format") != "agent-gauntlet-reference-baseline-v1":
        raise ValueError("unsupported reference baseline format")
    recorded = report.pop("baseline_sha256", None)
    actual = digest(canonical_bytes(report))
    if not recorded or recorded != actual:
        raise ValueError("reference baseline digest mismatch")
    runs = report.get("runs")
    if not isinstance(runs, list) or len(runs) != report.get("suite_run_count"):
        raise ValueError("reference baseline run inventory is invalid")
    checked = []
    for item in runs:
        if not isinstance(item, dict) or not item.get("bundle"):
            raise ValueError("reference baseline contains a malformed run entry")
        bundle = (report_path.parent / item["bundle"]).resolve()
        verified = verify(bundle)
        evidence_hash = digest((bundle / "evidence.json").read_bytes())
        if not verified["valid"] or evidence_hash != item.get("bundle_evidence_sha256"):
            raise ValueError(f"reference evidence verification failed: {item.get('run_id')}")
        rows = json.loads((bundle / "results.json").read_text(encoding="utf-8"))
        evaluations = [row["evaluation"] for row in rows]
        count = len(evaluations)
        if count != item.get("cases") or count == 0:
            raise ValueError("reference run case count mismatch")
        mean_score = round(sum(x["score"] for x in evaluations) / count, 2)
        passes = sum(bool(x["behavior_pass"]) for x in evaluations)
        failures = sum(row["execution"]["status"] == "failed" for row in rows)
        if (mean_score != item.get("mean_score") or passes != item.get("behavior_passes")
                or failures != item.get("execution_failures")):
            raise ValueError(f"reference run metrics mismatch: {item.get('run_id')}")
        checked.append(item["run_id"])
    return {"valid": True, "baseline_sha256": recorded, "runs_checked": len(checked),
            "case_count": report.get("case_count"), "all_bundles_verified": True}
