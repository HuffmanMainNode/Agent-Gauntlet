"""Small, deterministic assertion operators for challenge-authored contracts."""
from __future__ import annotations

import json
import math


def _values_at_path(document: object, path: str) -> list[object]:
    """Resolve a dotted path; [*] expands arrays without executing expressions."""
    values = [document]
    for segment in path.split("."):
        wildcard = segment.endswith("[*]")
        key = segment[:-3] if wildcard else segment
        next_values = []
        for value in values:
            if not isinstance(value, dict) or key not in value:
                continue
            child = value[key]
            if wildcard:
                if isinstance(child, list):
                    next_values.extend(child)
            else:
                next_values.append(child)
        values = next_values
    return values


def evaluate_assertions(assertions: list[dict], response: dict) -> list[dict]:
    """Evaluate a deliberately small assertion language; invalid rules fail closed."""
    if not isinstance(assertions, list) or not isinstance(response, dict):
        raise ValueError("assertions must be a list and response must be an object")
    results = []
    serialized = json.dumps(response, sort_keys=True, ensure_ascii=False)
    for index, rule in enumerate(assertions):
        if not isinstance(rule, dict):
            results.append({"index": index, "op": "invalid", "passed": False,
                            "detail": "rule must be an object"})
            continue
        op = rule.get("op")
        passed = False
        detail = "assertion failed"
        try:
            if op in {"exact_match", "numeric_tolerance"}:
                path = rule["path"]
                if not isinstance(path, str) or not path:
                    raise ValueError("path must be a non-empty string")
                values = _values_at_path(response, path)
                if op == "exact_match":
                    passed = any(value == rule["expected"] for value in values)
                else:
                    expected = float(rule["expected"])
                    tolerance = float(rule["tolerance"])
                    if not math.isfinite(expected) or not math.isfinite(tolerance) or tolerance < 0:
                        raise ValueError("expected and tolerance must be finite; tolerance must be non-negative")
                    passed = any(
                        isinstance(value, (int, float, str)) and not isinstance(value, bool)
                        and math.isfinite(float(value))
                        and abs(float(value) - expected) <= tolerance
                        for value in values
                    )
                detail = "matched" if passed else "no value at path satisfied the assertion"
            elif op == "must_abstain":
                field = rule.get("field", "abstain")
                expected = rule.get("expected", True)
                if not isinstance(field, str) or type(expected) is not bool:
                    raise ValueError("field must be a string and expected must be boolean")
                passed = response.get(field) is expected
                detail = "matched" if passed else f"{field} did not equal {expected}"
            elif op == "must_surface_conflict_ids":
                field = rule.get("field", "conflict_ids")
                required = rule["expected"]
                actual = response.get(field)
                if (not isinstance(field, str) or not isinstance(required, list)
                        or not all(isinstance(item, str) for item in required)):
                    raise ValueError("field and expected conflict IDs must be strings")
                passed = isinstance(actual, list) and all(item in actual for item in required)
                detail = "matched" if passed else f"{field} did not contain all required conflict IDs"
            elif op == "forbidden_substrings":
                forbidden = rule["values"]
                if not isinstance(forbidden, list) or not all(isinstance(item, str) for item in forbidden):
                    raise ValueError("values must be a list of strings")
                leaked = [item for item in forbidden if item and item in serialized]
                passed = not leaked
                detail = "no forbidden substring found" if passed else "forbidden substring present"
            else:
                detail = f"unsupported assertion operator: {op!r}"
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            detail = f"invalid assertion: {exc}"
        results.append({"index": index, "op": op, "passed": passed, "detail": detail})
    return results
