"""Run seeded adversarial cases through a user-configured command adapter."""
from __future__ import annotations

import hashlib
import json
import platform
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .adapters import invoke_command
from .adversarial import build_case, evaluate_case
from .runner import canonical_bytes, digest


def run_suite(suite: str, command: list[str], seeds: list[int], output_root: Path,
              timeout_seconds: int = 45, agent_name: str = "", model_id: str = "",
              adapter_version: str = "", operator: str = "unspecified") -> Path:
    if not agent_name.strip() or not model_id.strip() or not adapter_version.strip():
        raise ValueError("Agent name, model ID, and adapter version are required for a benchmark run")
    if not seeds:
        raise ValueError("At least one seed is required")
    if any(type(seed) is not int for seed in seeds):
        raise ValueError("Every seed must be an integer")
    if len(set(seeds)) != len(seeds):
        raise ValueError("Seeds must be unique within a run")
    if len(seeds) > 100:
        raise ValueError("A suite run is limited to 100 seeds")
    run_id = uuid.uuid4().hex
    bundle = Path(output_root) / run_id
    started = datetime.now(timezone.utc)
    rows = []
    for seed in seeds:
        case = build_case(suite, seed)
        task = {key: value for key, value in case.items() if key != "trap"}
        try:
            response = invoke_command(command, task, timeout_seconds)
            execution = {"status": "completed", "error_type": None, "error": None}
        except (OSError, ValueError, TimeoutError) as exc:
            # A failed adapter attempt is evidence, not a reason to discard the entire run.
            response = {"claims": [], "abstain": False, "adapter_error": type(exc).__name__}
            execution = {"status": "failed", "error_type": type(exc).__name__,
                         "error": str(exc)[:1000]}
        evaluation = evaluate_case(case, response)
        if execution["status"] == "failed":
            evaluation["behavior_pass"] = False
            evaluation["score"] = 0.0
        rows.append({"case": case, "response": response, "execution": execution,
                     "evaluation": evaluation})
    finished = datetime.now(timezone.utc)
    bundle.mkdir(parents=True, exist_ok=False)
    payloads = {
        "results.json": canonical_bytes(rows),
        "summary.json": canonical_bytes({
            "suite": suite, "cases": len(rows),
            "mean_score": round(sum(row["evaluation"]["score"] for row in rows) / len(rows), 2),
            "behavior_passes": sum(bool(row["evaluation"]["behavior_pass"]) for row in rows),
            "unsupported_claims": sum(row["evaluation"]["unsupported_claims"] for row in rows),
            "execution_failures": sum(row["execution"]["status"] == "failed" for row in rows),
            "abstentions": sum(bool(row["evaluation"]["abstained"]) for row in rows),
        }),
        "environment.json": canonical_bytes({"python": platform.python_version(), "platform": platform.platform()}),
    }
    for name, data in payloads.items():
        (bundle / name).write_bytes(data)
    manifest = {
        "format": "agent-gauntlet-adversarial-evidence-v1", "run_id": run_id,
        "suite": suite, "seeds": seeds,
        "agent": {"name": agent_name, "model_id": model_id, "adapter_version": adapter_version},
        "operator": operator,
        "adapter_command_sha256": hashlib.sha256(canonical_bytes(command)).hexdigest(),
        "timeout_seconds": timeout_seconds,
        "started_at": started.isoformat(), "completed_at": finished.isoformat(),
        "artifacts": {name: digest(data) for name, data in sorted(payloads.items())},
        "attestation": "unsigned-local-run",
        "limitations": ["Adapter command is trusted participant-supplied code.",
                        "No sandbox is provided by this adapter.",
                        "A passing score is not proof of general agent reliability."],
    }
    (bundle / "evidence.json").write_bytes(canonical_bytes(manifest))
    return bundle
