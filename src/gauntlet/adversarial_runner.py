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
              timeout_seconds: int = 45) -> Path:
    if not seeds:
        raise ValueError("At least one seed is required")
    if len(seeds) > 100:
        raise ValueError("A suite run is limited to 100 seeds")
    run_id = uuid.uuid4().hex
    bundle = Path(output_root) / run_id
    bundle.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc)
    rows = []
    for seed in seeds:
        case = build_case(suite, seed)
        task = {key: value for key, value in case.items() if key != "trap"}
        response = invoke_command(command, task, timeout_seconds)
        rows.append({"case": case, "response": response, "evaluation": evaluate_case(case, response)})
    finished = datetime.now(timezone.utc)
    payloads = {
        "results.json": canonical_bytes(rows),
        "summary.json": canonical_bytes({
            "suite": suite, "cases": len(rows),
            "mean_score": round(sum(row["evaluation"]["score"] for row in rows) / len(rows), 2),
            "behavior_passes": sum(bool(row["evaluation"]["behavior_pass"]) for row in rows),
            "unsupported_claims": sum(row["evaluation"]["unsupported_claims"] for row in rows),
            "abstentions": sum(bool(row["evaluation"]["abstained"]) for row in rows),
        }),
        "environment.json": canonical_bytes({"python": platform.python_version(), "platform": platform.platform()}),
    }
    for name, data in payloads.items():
        (bundle / name).write_bytes(data)
    manifest = {
        "format": "agent-gauntlet-adversarial-evidence-v1", "run_id": run_id,
        "suite": suite, "seeds": seeds, "adapter_command_sha256": hashlib.sha256(canonical_bytes(command)).hexdigest(),
        "started_at": started.isoformat(), "completed_at": finished.isoformat(),
        "artifacts": {name: digest(data) for name, data in sorted(payloads.items())},
        "attestation": "unsigned-local-run",
        "limitations": ["Adapter command is trusted participant-supplied code.",
                        "No sandbox is provided by this adapter.",
                        "A passing score is not proof of general agent reliability."],
    }
    (bundle / "evidence.json").write_bytes(canonical_bytes(manifest))
    return bundle
