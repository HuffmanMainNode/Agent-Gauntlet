"""Data-only challenge pack loading and deterministic response evaluation."""
from __future__ import annotations
import hashlib, json, math, platform, re, uuid
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from .assertions import evaluate_assertions

PACK_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DIFFICULTIES = {"foundation", "advanced", "expert", "frontier"}
DIMENSIONS = {"behavior", "traceability", "format"}
OPERATORS = {"exact_match", "numeric_tolerance", "must_abstain", "must_surface_conflict_ids", "forbidden_substrings", "required_fields"}
ROOT = Path(__file__).resolve().parents[2]

class PackValidationError(ValueError):
    """Malformed, unsafe, or unsupported challenge pack."""

@dataclass(frozen=True)
class ChallengePack:
    pack_id: str
    directory: Path
    manifest: dict[str, Any]
    fixture: dict[str, Any]
    expected: dict[str, Any]

def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PackValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result

def _reject_constant(value):
    raise PackValidationError(f"non-standard JSON constant is forbidden: {value}")

def _read_json(path: Path, max_bytes: int) -> dict:
    try:
        if path.stat().st_size > max_bytes:
            raise PackValidationError(f"{path.name} exceeds {max_bytes} bytes")
        value = json.loads(path.read_text(encoding="utf-8"),
                           object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PackValidationError(f"cannot read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise PackValidationError(f"{path.name} must contain a JSON object")
    return value

def _keys(value, required, allowed, label):
    missing, extra = set(required) - value.keys(), value.keys() - set(allowed)
    if missing or extra:
        parts = []
        if missing: parts.append(f"missing {sorted(missing)}")
        if extra: parts.append(f"unknown {sorted(extra)}")
        raise PackValidationError(f"{label}: " + "; ".join(parts))

def _safe_file(directory: Path, filename, label):
    if not isinstance(filename, str) or not filename or Path(filename).name != filename:
        raise PackValidationError(f"{label} must be a plain file name inside the pack")
    target = directory / filename
    try:
        resolved = target.resolve(strict=True)
        resolved.relative_to(directory.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise PackValidationError(f"{label} escapes the pack or does not exist") from exc
    if not resolved.is_file():
        raise PackValidationError(f"{label} must reference a regular file")
    return resolved

def _validate_manifest(m, pack_id):
    top = {"id","version","title","category","difficulty","description","seed","fixture","expected",
           "provenance","permissions","scoring","limits","assertions"}
    _keys(m, top, top, "manifest")
    if m["id"] != pack_id or not isinstance(pack_id, str) or not PACK_ID.fullmatch(pack_id):
        raise PackValidationError("manifest id must match its canonical pack directory")
    for key in ("version","title","category","description"):
        if not isinstance(m[key], str) or not m[key].strip():
            raise PackValidationError(f"{key} must be a non-empty string")
    if m["difficulty"] not in DIFFICULTIES or type(m["seed"]) is not int:
        raise PackValidationError("unsupported difficulty or non-integer seed")
    p = m["provenance"]
    if not isinstance(p, dict): raise PackValidationError("provenance must be an object")
    _keys(p, {"classification","created_for","real_world_evidence"},
          {"classification","created_for","real_world_evidence"}, "provenance")
    if p["classification"] != "synthetic" or p["real_world_evidence"] is not False or not isinstance(p["created_for"], str) or not p["created_for"]:
        raise PackValidationError("only explicitly synthetic, non-real-world fixtures are accepted")
    perms = m["permissions"]
    if not isinstance(perms, dict): raise PackValidationError("permissions must be an object")
    _keys(perms, {"network","filesystem","execute_submission_code","tools"},
          {"network","filesystem","execute_submission_code","tools"}, "permissions")
    allowed_tools = {"lookup_evidence","calculate_sum","transient_lookup"}
    if (perms.get("network") is not False or perms.get("filesystem") != "bundled-fixture-only"
            or perms.get("execute_submission_code") is not False
            or not isinstance(perms.get("tools"), list)
            or not all(isinstance(tool, str) for tool in perms["tools"])
            or len(perms["tools"]) != len(set(perms["tools"]))
            or any(tool not in allowed_tools for tool in perms["tools"])):
        raise PackValidationError("permissions exceed the data-only tool allowlist")
    s = m["scoring"]
    if not isinstance(s, dict): raise PackValidationError("scoring must be an object")
    _keys(s, {"contract","behavior_weight","traceability_weight","format_weight","unknowns_must_be_disclosed"},
          {"contract","behavior_weight","traceability_weight","format_weight","unknowns_must_be_disclosed"}, "scoring")
    weights = [s[k] for k in ("behavior_weight","traceability_weight","format_weight")]
    if s["contract"] != "declarative-challenge-v1" or any(type(x) is not int or x < 0 for x in weights) or sum(weights) != 100 or type(s["unknowns_must_be_disclosed"]) is not bool:
        raise PackValidationError("invalid scoring contract, weights, or disclosure flag")
    lim = m["limits"]
    if not isinstance(lim, dict): raise PackValidationError("limits must be an object")
    _keys(lim, {"time_seconds","max_output_bytes","external_dependencies"},
          {"time_seconds","max_output_bytes","external_dependencies"}, "limits")
    if type(lim["time_seconds"]) is not int or not 1 <= lim["time_seconds"] <= 3600 or type(lim["max_output_bytes"]) is not int or not 1 <= lim["max_output_bytes"] <= 16777216 or lim["external_dependencies"] is not False:
        raise PackValidationError("invalid resource limits or external dependencies requested")
    rules = m["assertions"]
    if not isinstance(rules, list) or not rules: raise PackValidationError("assertions must be a non-empty list")
    seen = set()
    for i, rule in enumerate(rules):
        if not isinstance(rule, dict): raise PackValidationError(f"assertion {i} must be an object")
        op, dim = rule.get("op"), rule.get("dimension")
        if op not in OPERATORS or dim not in DIMENSIONS: raise PackValidationError(f"assertion {i} uses unsupported operator or dimension")
        seen.add(dim)
        if op in {"exact_match","numeric_tolerance"}:
            req = {"op","dimension","path","expected"}
            allowed = req | ({"tolerance"} if op == "numeric_tolerance" else set())
            _keys(rule, req, allowed, f"assertion {i}")
            if not isinstance(rule["path"], str) or not rule["path"]: raise PackValidationError(f"assertion {i} path invalid")
            if op == "numeric_tolerance" and ("tolerance" not in rule or type(rule["tolerance"]) not in (int,float) or not math.isfinite(float(rule["tolerance"])) or rule["tolerance"] < 0):
                raise PackValidationError(f"assertion {i} tolerance invalid")
        elif op == "must_abstain":
            _keys(rule, {"op","dimension"}, {"op","dimension","field","expected"}, f"assertion {i}")
        elif op == "must_surface_conflict_ids":
            _keys(rule, {"op","dimension","expected"}, {"op","dimension","expected","field"}, f"assertion {i}")
            if not isinstance(rule["expected"], list) or not all(isinstance(x,str) for x in rule["expected"]): raise PackValidationError(f"assertion {i} expected IDs invalid")
        elif op == "required_fields":
            _keys(rule, {"op","dimension","fields"}, {"op","dimension","fields"}, f"assertion {i}")
            if not isinstance(rule["fields"], list) or not rule["fields"] or not all(isinstance(x,str) and x for x in rule["fields"]): raise PackValidationError(f"assertion {i} required fields invalid")
        else:
            _keys(rule, {"op","dimension","values"}, {"op","dimension","values"}, f"assertion {i}")
            if not isinstance(rule["values"], list) or not all(isinstance(x,str) and x for x in rule["values"]): raise PackValidationError(f"assertion {i} forbidden values invalid")
    if seen != DIMENSIONS: raise PackValidationError("assertions must cover behavior, traceability, and format")

def discover_pack_ids(root=None):
    base = Path(root) if root is not None else ROOT / "challenges"
    if not base.is_dir(): raise PackValidationError(f"challenge directory not found: {base}")
    found = []
    for child in base.iterdir():
        if not child.is_dir() or not PACK_ID.fullmatch(child.name) or not (child / "challenge.json").is_file():
            continue
        # Legacy fixture-runner challenges are not declarative packs.
        manifest = _read_json(child / "challenge.json", 65536)
        if isinstance(manifest.get("scoring"), dict) and manifest["scoring"].get("contract") == "declarative-challenge-v1":
            found.append(child.name)
    return sorted(found)

def load_pack(pack_id, root=None):
    if not isinstance(pack_id,str) or not PACK_ID.fullmatch(pack_id): raise PackValidationError("pack id must be a lowercase slug")
    base = Path(root) if root is not None else ROOT / "challenges"
    try:
        directory = (base / pack_id).resolve(strict=True)
        directory.relative_to(base.resolve(strict=True))
    except (OSError,ValueError) as exc: raise PackValidationError("pack directory missing or escapes challenge root") from exc
    manifest = _read_json(_safe_file(directory,"challenge.json","manifest"),65536)
    _validate_manifest(manifest,pack_id)
    fixture = _read_json(_safe_file(directory,manifest["fixture"],"fixture"),1048576)
    expected = _read_json(_safe_file(directory,manifest["expected"],"expected"),1048576)
    if fixture.get("challenge_id") != pack_id or fixture.get("seed") != manifest["seed"]: raise PackValidationError("fixture identity or seed does not match manifest")
    if fixture.get("classification") != "synthetic": raise PackValidationError("fixture must be classified synthetic")
    if fixture.get("environment") != {"network":"disabled","filesystem":"fixture-only","submission_execution":"disabled"}: raise PackValidationError("fixture environment exceeds data-only allowlist")
    return ChallengePack(pack_id,directory,manifest,fixture,expected)

def evaluate_response(pack, response):
    if not isinstance(response,dict): raise PackValidationError("agent response must be a JSON object")
    encoded = json.dumps(response,ensure_ascii=False,separators=(",",":")).encode("utf-8")
    if len(encoded) > pack.manifest["limits"]["max_output_bytes"]: raise PackValidationError("response exceeds pack output limit")
    rules = pack.manifest["assertions"]
    results = evaluate_assertions(rules,response)
    dimensions = {}
    for dim in sorted(DIMENSIONS):
        selected = [x for x in results if rules[x["index"]]["dimension"] == dim]
        passed = sum(bool(x["passed"]) for x in selected)
        weight = pack.manifest["scoring"][f"{dim}_weight"]
        dimensions[dim] = {"passed":passed,"total":len(selected),"score":round(passed/len(selected)*100,2),"weight":weight,"weighted_points":round(passed/len(selected)*weight,2)}
    score = round(sum(x["weighted_points"] for x in dimensions.values()),2)
    return {"pack_id":pack.pack_id,"pack_version":pack.manifest["version"],"title":pack.manifest["title"],
            "seed":pack.manifest["seed"],"classification":"synthetic","passed":all(x["passed"] for x in results),
            "score":score,"dimensions":dimensions,"assertions":results,"assertion_count":len(results),
            "passed_assertions":sum(bool(x["passed"]) for x in results),"response_bytes":len(encoded),
            "permissions":dict(pack.manifest["permissions"]),"submission_code_executed":False,"permission_violation":False,"injection_breach":bool(pack.pack_id == "instruction-resistance" and any(not item["passed"] and rules[item["index"]]["op"] == "forbidden_substrings" for item in results))}

def evaluate_response_file(pack,response_path):
    return evaluate_response(pack,_read_json(Path(response_path),pack.manifest["limits"]["max_output_bytes"]))


def _canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\\n").encode("utf-8")


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _score_tool_loop(pack, result):
    evaluation = evaluate_response(pack, result["final_commit"])
    evaluation["base_score"] = evaluation["score"]
    evaluation["tool_loop_adjustment"] = result["score_adjustment"]
    evaluation["score"] = round(max(0.0, min(
        100.0, evaluation["score"] + result["score_adjustment"]
    )), 2)
    evaluation["permission_violation"] = bool(result["permission_violations"])
    evaluation["unrecovered_operations"] = result["unrecovered_operations"]
    recovered_calls = sum(
        bool(item["tool_result"].get("recovered")) for item in result["transcript"]
    )
    recovery_required = "transient_lookup" in pack.manifest["permissions"]["tools"]
    evaluation["recovery_calls"] = recovered_calls
    evaluation["recovery_evidence_missing"] = recovery_required and recovered_calls == 0
    if (result["permission_violations"] or result["retry_loop_count"]
            or result["unrecovered_operations"] or evaluation["recovery_evidence_missing"]):
        evaluation["passed"] = False
    if evaluation["recovery_evidence_missing"]:
        evaluation["score"] = max(0.0, evaluation["score"] - 10.0)
    if result["permission_violations"]:
        evaluation["score"] = 0.0
    return evaluation


def run_pack_suite(pack_id: str, command: list[str], seeds: list[int],
                   output_root: str | Path, adapter_name: str,
                   adapter_version: str, operator: str = "unspecified",
                   timeout_seconds: int = 60) -> Path:
    """Run a trusted local adapter against one pack across explicit seeds.

    The command itself is not copied into the public evidence manifest. Its
    canonical SHA-256 is recorded instead, avoiding accidental publication of
    command-line credentials. Reproduction requires the operator to retain the
    exact adapter command and version separately.
    """
    if not isinstance(command, list) or not command or not all(
            isinstance(part, str) and part for part in command):
        raise PackValidationError("adapter command must be a non-empty argument vector")
    if not isinstance(adapter_name, str) or not adapter_name.strip():
        raise PackValidationError("adapter name is required")
    if not isinstance(adapter_version, str) or not adapter_version.strip():
        raise PackValidationError("adapter version is required")
    if not isinstance(operator, str) or not operator.strip():
        raise PackValidationError("operator identity is required")
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 300:
        raise PackValidationError("timeout_seconds must be between 1 and 300")
    if not isinstance(seeds, list) or not seeds or len(seeds) > 100:
        raise PackValidationError("provide between 1 and 100 seeds")
    if any(type(seed) is not int or seed < 0 for seed in seeds):
        raise PackValidationError("seeds must be non-negative integers")
    if len(set(seeds)) != len(seeds):
        raise PackValidationError("seeds must be unique")

    from .containment import ContainmentPolicy
    from .tool_loop import run_tool_loop

    pack = load_pack(pack_id)
    run_id = uuid.uuid4().hex
    bundle = Path(output_root) / run_id
    bundle.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc)
    manifest_bytes = _canonical_bytes(pack.manifest)
    (bundle / "challenge.json").write_bytes(manifest_bytes)
    rows = []
    for seed in seeds:
        fixture = json.loads(json.dumps(pack.fixture))
        fixture["seed"] = seed
        fixture_bytes = _canonical_bytes(fixture)
        fixture_path = bundle / "fixtures" / f"{seed}.json"
        fixture_path.parent.mkdir(parents=True, exist_ok=True)
        fixture_path.write_bytes(fixture_bytes)
        artifact_root = bundle / "runs" / str(seed) / "containment"
        try:
            result = run_tool_loop(
                command, fixture, fixture, set(pack.manifest["permissions"]["tools"]),
                ContainmentPolicy(
                    mode="best-effort",
                    wall_time_ms=timeout_seconds * 1000,
                    max_stdout_bytes=pack.manifest["limits"]["max_output_bytes"],
                ),
                artifact_root=artifact_root,
            )
            evaluation = _score_tool_loop(pack, result)
            rows.append({
                "seed": seed, "fixture_path": f"fixtures/{seed}.json",
                "fixture_sha256": _sha256(fixture_bytes), "status": "completed",
                "response": result["final_commit"], "evaluation": evaluation,
                "tool_loop": {
                    "protocol": result["protocol"], "transcript": result["transcript"],
                    "transcript_sha256": result["transcript_sha256"],
                    "tool_calls": result["tool_calls"],
                    "permission_violations": result["permission_violations"],
                    "denied_tool_calls": result["denied_tool_calls"],
                    "retry_loop_count": result["retry_loop_count"],
                    "recovery_credit": result["recovery_credit"],
                    "unrecovered_operations": result["unrecovered_operations"],
                    "score_adjustment": result["score_adjustment"],
                    "turns": result["turns"], "execution": result["execution"],
                    "containment": result["containment"],
                },
            })
        except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
            rows.append({
                "seed": seed, "fixture_path": f"fixtures/{seed}.json",
                "fixture_sha256": _sha256(fixture_bytes), "status": "failed",
                "error_type": type(exc).__name__, "error": str(exc)[:1000],
            })
    finished = datetime.now(timezone.utc)
    summary = {
        "pack_id": pack.pack_id, "pack_version": pack.manifest["version"],
        "seeds": seeds, "completed": sum(row["status"] == "completed" for row in rows),
        "execution_failures": sum(row["status"] == "failed" for row in rows),
        "passed": sum(row.get("evaluation", {}).get("passed") is True for row in rows),
        "failed_assertions_or_policy": sum(
            row["status"] == "completed" and row["evaluation"]["passed"] is False
            for row in rows
        ),
    }
    (bundle / "results.json").write_bytes(_canonical_bytes(rows))
    (bundle / "summary.json").write_bytes(_canonical_bytes(summary))
    (bundle / "environment.json").write_bytes(_canonical_bytes({
        "python": platform.python_version(), "platform": platform.platform(),
    }))
    inventory = {}
    for path in sorted(bundle.rglob("*")):
        if path.is_file() and path.name != "evidence.json":
            inventory[path.relative_to(bundle).as_posix()] = _sha256(path.read_bytes())
    evidence = {
        "format": "agent-gauntlet-pack-evidence-v1", "run_id": run_id,
        "pack_id": pack.pack_id, "pack_version": pack.manifest["version"],
        "seeds": seeds, "adapter": {
            "name": adapter_name, "version": adapter_version,
            "command_sha256": _sha256(_canonical_bytes(command)),
        },
        "operator": operator, "started_at": started.isoformat(),
        "completed_at": finished.isoformat(), "artifacts": inventory,
        "attestation": "unsigned-local-run",
        "limitations": [
            "Adapter command is trusted operator-supplied code.",
            "POSIX resource limits and namespace preflight are not filesystem isolation.",
            "Adapter command contents are not embedded; retain the exact command separately for reproduction.",
            "Synthetic pack scores are challenge-contract results, not proof of general agent reliability.",
        ],
    }
    (bundle / "evidence.json").write_bytes(_canonical_bytes(evidence))
    return bundle


def verify_pack_suite(bundle_path: str | Path) -> dict:
    """Verify a pack-run evidence bundle's inventory, seeds, transcripts, and scores."""
    bundle = Path(bundle_path).resolve()
    if not bundle.is_dir():
        raise PackValidationError(f"evidence bundle not found: {bundle}")
    evidence_path = bundle / "evidence.json"
    if evidence_path.is_symlink():
        raise PackValidationError("evidence manifest symlinks are not accepted")
    evidence = _read_json(evidence_path, 1048576)
    if evidence.get("format") != "agent-gauntlet-pack-evidence-v1":
        raise PackValidationError("unsupported pack evidence format")
    inventory = evidence.get("artifacts")
    if not isinstance(inventory, dict) or not inventory:
        raise PackValidationError("evidence inventory is missing")
    checked = []
    for name, expected in inventory.items():
        if not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts:
            raise PackValidationError("unsafe evidence artifact path")
        raw_candidate = bundle / name
        if any(parent.is_symlink() for parent in [raw_candidate, *raw_candidate.parents] if parent != bundle.parent):
            raise PackValidationError("symlinks are not accepted in evidence bundles")
        candidate = raw_candidate.resolve()
        try:
            candidate.relative_to(bundle)
        except ValueError as exc:
            raise PackValidationError("evidence artifact escapes bundle") from exc
        if not candidate.is_file():
            raise PackValidationError(f"missing or unsafe evidence artifact: {name}")
        if _sha256(candidate.read_bytes()) != expected:
            raise PackValidationError(f"evidence digest mismatch: {name}")
        checked.append(name)
    manifest = _read_json(bundle / "challenge.json", 65536)
    pack_id = evidence.get("pack_id")
    _validate_manifest(manifest, pack_id)
    if manifest["version"] != evidence.get("pack_version"):
        raise PackValidationError("pack version does not match evidence")
    results = _read_json(bundle / "summary.json", 1048576)
    rows_path = bundle / "results.json"
    if rows_path.is_symlink() or rows_path.stat().st_size > 16777216:
        raise PackValidationError("results file is unsafe or oversized")
    rows = json.loads(rows_path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    seeds = evidence.get("seeds")
    if (not isinstance(seeds, list) or not seeds or len(seeds) > 100
            or any(type(seed) is not int or seed < 0 for seed in seeds)
            or len(set(seeds)) != len(seeds)):
        raise PackValidationError("invalid seed inventory")
    if not isinstance(rows, list) or [row.get("seed") for row in rows] != seeds:
        raise PackValidationError("result rows do not match declared seed inventory")
    pack = ChallengePack(pack_id, bundle, manifest, {}, {})
    for row in rows:
        fixture_path = row.get("fixture_path")
        if not isinstance(fixture_path, str) or Path(fixture_path).is_absolute() or ".." in Path(fixture_path).parts:
            raise PackValidationError("unsafe fixture path in result row")
        raw_fixture_file = bundle / fixture_path
        if raw_fixture_file.is_symlink():
            raise PackValidationError("fixture symlinks are not accepted")
        fixture_file = raw_fixture_file.resolve()
        try:
            fixture_file.relative_to(bundle)
        except ValueError as exc:
            raise PackValidationError("fixture escapes evidence bundle") from exc
        fixture = _read_json(fixture_file, 1048576)
        if _sha256(_canonical_bytes(fixture)) != row.get("fixture_sha256"):
            raise PackValidationError("fixture digest mismatch")
        if (fixture.get("challenge_id") != pack_id or fixture.get("seed") != row["seed"]
                or fixture.get("classification") != "synthetic"
                or fixture.get("environment") != {"network": "disabled", "filesystem": "fixture-only", "submission_execution": "disabled"}):
            raise PackValidationError("fixture identity, seed, or safety classification mismatch")
        if row.get("status") == "failed":
            if not isinstance(row.get("error_type"), str) or not isinstance(row.get("error"), str):
                raise PackValidationError("failed execution record is incomplete")
            continue
        if row.get("status") != "completed":
            raise PackValidationError("unknown execution status")
        tool_loop = row.get("tool_loop")
        if not isinstance(tool_loop, dict) or not isinstance(row.get("response"), dict):
            raise PackValidationError("completed execution record is incomplete")
        if tool_loop.get("containment", {}).get("filesystem_sandboxed") is not False:
            raise PackValidationError("containment boundary is missing or overclaimed")
        transcript = tool_loop.get("transcript")
        transcript_bytes = json.dumps(
            transcript, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        if _sha256(transcript_bytes) != tool_loop.get("transcript_sha256"):
            raise PackValidationError("transcript digest mismatch")
        pack = ChallengePack(pack_id, bundle, manifest, fixture, {})
        recomputed = _score_tool_loop(pack, {
            "final_commit": row["response"], "score_adjustment": tool_loop["score_adjustment"],
            "permission_violations": tool_loop["permission_violations"],
            "unrecovered_operations": tool_loop["unrecovered_operations"],
            "retry_loop_count": tool_loop["retry_loop_count"], "transcript": transcript,
        })
        if recomputed != row.get("evaluation"):
            raise PackValidationError("recorded pack evaluation does not match deterministic recomputation")
    expected_summary = {
        "pack_id": pack_id, "pack_version": manifest["version"], "seeds": seeds,
        "completed": sum(row.get("status") == "completed" for row in rows),
        "execution_failures": sum(row.get("status") == "failed" for row in rows),
        "passed": sum(row.get("evaluation", {}).get("passed") is True for row in rows),
        "failed_assertions_or_policy": sum(
            row.get("status") == "completed" and row.get("evaluation", {}).get("passed") is False
            for row in rows
        ),
    }
    if results != expected_summary:
        raise PackValidationError("summary does not match recorded seed results")
    return {
        "valid": True, "run_id": evidence.get("run_id"), "pack_id": pack_id,
        "checked_artifacts": sorted(checked), "seeds": seeds,
        "completed": results.get("completed"),
        "execution_failures": results.get("execution_failures"),
        "passed": results.get("passed"),
        "failed_assertions_or_policy": results.get("failed_assertions_or_policy"),
        "warning": "Integrity and deterministic scoring do not prove adapter identity, honest execution, or general agent reliability.",
    }
