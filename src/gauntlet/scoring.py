"""Deterministic scoring for the starter repository challenge."""

def score(task: dict, response: dict) -> dict:
    expected = task["expected_findings"]
    expected_by_id = {item["id"]: item for item in expected}
    matched, invalid, seen = [], [], set()
    for item in response.get("findings", []):
        finding_id = item.get("id")
        if finding_id in seen:
            invalid.append({"id": finding_id, "reason": "duplicate"})
            continue
        seen.add(finding_id)
        target = expected_by_id.get(finding_id)
        if target is None:
            invalid.append({"id": finding_id, "reason": "unknown finding"})
        elif item.get("path") != target["path"] or item.get("line") != target["line"]:
            invalid.append({"id": finding_id, "reason": "evidence location mismatch"})
        else:
            matched.append(finding_id)
    total = len(expected)
    points = len(matched)
    return {
        "scorer": "exact-fixture-match-v1",
        "score": points,
        "maximum": total,
        "percentage": round(points / total * 100, 2) if total else 100.0,
        "matched": matched,
        "invalid": invalid,
        "limitations": ["Exact fixture matching only; not a measure of general code-review ability."],
    }
