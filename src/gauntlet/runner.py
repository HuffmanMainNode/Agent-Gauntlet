"""Safe fixture-only challenge runner and evidence bundle writer."""
import hashlib
import json
import platform
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .agents import run_agent
from .scoring import score

ROOT = Path(__file__).resolve().parents[2]
CHALLENGES = ROOT / "challenges"


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_challenge(challenge_id):
    if not challenge_id.replace("-", "").isalnum():
        raise ValueError("Invalid challenge identifier")
    folder = CHALLENGES / challenge_id
    manifest = json.loads((folder / "challenge.json").read_text(encoding="utf-8"))
    task = dict(manifest)
    task["fixture_text"] = (folder / "fixture" / "sample.py").read_text(encoding="utf-8")
    return manifest, task


def run(challenge_id, agent_id, output_root=None):
    manifest, task = load_challenge(challenge_id)
    started = datetime.now(timezone.utc)
    response = run_agent(agent_id, task)
    result = score(task, response)
    ended = datetime.now(timezone.utc)
    run_id = uuid.uuid4().hex
    root = Path(output_root or ROOT / "artifacts")
    bundle = root / run_id
    bundle.mkdir(parents=True, exist_ok=False)
    payloads = {
        "challenge.json": canonical_bytes(manifest),
        "task.json": canonical_bytes({"challenge_id": challenge_id, "version": manifest["version"],
                                      "fixture_text": task["fixture_text"],
                                      "expected_findings": task["expected_findings"]}),
        "response.json": canonical_bytes(response),
        "score.json": canonical_bytes(result),
        "environment.json": canonical_bytes({"python": platform.python_version(),
                                               "platform": platform.platform()}),
    }
    for name, data in payloads.items():
        (bundle / name).write_bytes(data)
    evidence = {
        "format": "agent-gauntlet-evidence-v1", "run_id": run_id,
        "challenge_id": challenge_id, "challenge_version": manifest["version"],
        "agent_id": agent_id, "agent_kind": "bundled-fixture",
        "started_at": started.isoformat(), "completed_at": ended.isoformat(),
        "artifacts": {name: digest(data) for name, data in sorted(payloads.items())},
        "integrity": "sha256", "verification_scope": "payload-integrity-and-deterministic-score",
        "attestation": "unsigned-local-run",
    }
    (bundle / "evidence.json").write_bytes(canonical_bytes(evidence))
    root.mkdir(parents=True, exist_ok=True)
    (root / "LATEST").write_text(bundle.name + "\n", encoding="utf-8")
    return bundle


def verify(bundle):
    bundle = Path(bundle).resolve()
    if not bundle.is_dir():
        raise ValueError(f"Evidence bundle directory not found: {bundle}")
    evidence = json.loads((bundle / "evidence.json").read_text(encoding="utf-8"))
    evidence_format = evidence.get("format")
    if evidence_format not in {"agent-gauntlet-evidence-v1", "agent-gauntlet-adversarial-evidence-v1"}:
        raise ValueError("Unsupported evidence format")
    inventory = evidence.get("artifacts")
    if not isinstance(inventory, dict) or not inventory:
        raise ValueError("Evidence artifact inventory is missing")
    checked = []
    for name, expected in inventory.items():
        candidate = (bundle / name).resolve()
        if candidate.parent != bundle or not candidate.is_file():
            raise ValueError(f"Invalid or missing artifact: {name}")
        if digest(candidate.read_bytes()) != expected:
            raise ValueError(f"Digest mismatch: {name}")
        checked.append(name)
    if evidence_format == "agent-gauntlet-adversarial-evidence-v1":
        from .adversarial import evaluate_case

        rows = json.loads((bundle / "results.json").read_text(encoding="utf-8"))
        if not isinstance(rows, list) or not rows:
            raise ValueError("Adversarial results must be a non-empty list")
        declared_seeds = evidence.get("seeds")
        if (not isinstance(declared_seeds, list) or
                any(type(seed) is not int for seed in declared_seeds) or
                len(set(declared_seeds)) != len(declared_seeds) or
                len(declared_seeds) > 100):
            raise ValueError("Invalid seed inventory in evidence manifest")
        if len(rows) != len(declared_seeds):
            raise ValueError("Result count does not match declared seed inventory")
        if [row.get("case", {}).get("seed") for row in rows] != declared_seeds:
            raise ValueError("Result seeds or ordering do not match evidence manifest")
        suite = evidence.get("suite")
        if not isinstance(suite, str) or not suite:
            raise ValueError("Missing suite identifier")
        from .adversarial import build_case
        for row in rows:
            if not isinstance(row, dict) or not {"case", "response", "execution", "evaluation"} <= set(row):
                raise ValueError("Malformed adversarial result row")
            case = row["case"]
            if case != build_case(suite, case.get("seed")):
                raise ValueError(f"Challenge case does not match deterministic generator: {case.get('case_id')}")
            if not isinstance(row["response"], dict):
                raise ValueError("Adapter response must be a JSON object")
            execution = row["execution"]
            if not isinstance(execution, dict) or execution.get("status") not in {"completed", "failed"}:
                raise ValueError("Invalid execution status")
            if execution["status"] == "completed":
                if execution.get("error_type") is not None or execution.get("error") is not None:
                    raise ValueError("Completed execution cannot carry failure diagnostics")
                recomputed = evaluate_case(case, row["response"])
            else:
                if not isinstance(execution.get("error_type"), str) or not execution["error_type"]:
                    raise ValueError("Failed execution must include an error type")
                if not isinstance(execution.get("error"), str):
                    raise ValueError("Failed execution must include a diagnostic")
                recomputed = evaluate_case(case, row["response"])
                recomputed["behavior_pass"] = False
                recomputed["score"] = 0.0
            if recomputed != row["evaluation"]:
                raise ValueError(f"Adversarial evaluation mismatch: {case.get('case_id')}")
        return {
            "valid": True,
            "run_id": evidence["run_id"],
            "checked_artifacts": sorted(checked),
            "cases": len(rows),
            "suite": evidence.get("suite"),
            "attestation": evidence.get("attestation", "unknown"),
            "warning": "Integrity and evaluator consistency do not prove agent identity, honest execution, semantic truth, or independent observation.",
        }

    task = json.loads((bundle / "task.json").read_text(encoding="utf-8"))
    response = json.loads((bundle / "response.json").read_text(encoding="utf-8"))
    recorded = json.loads((bundle / "score.json").read_text(encoding="utf-8"))
    recomputed = score(task, response)
    if recomputed != recorded:
        raise ValueError("Deterministic score does not match recorded score")
    return {"valid": True, "run_id": evidence["run_id"], "checked_artifacts": sorted(checked),
            "score": recomputed, "attestation": evidence.get("attestation", "unknown"),
            "warning": "Integrity is not proof of identity, honest execution, safety, or independent observation."}
