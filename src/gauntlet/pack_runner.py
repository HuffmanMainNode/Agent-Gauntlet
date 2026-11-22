"""Data-only challenge pack loading and deterministic response evaluation."""
from __future__ import annotations
import json, math, re
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
            "permissions":dict(pack.manifest["permissions"]),"submission_code_executed":False}

def evaluate_response_file(pack,response_path):
    return evaluate_response(pack,_read_json(Path(response_path),pack.manifest["limits"]["max_output_bytes"]))
