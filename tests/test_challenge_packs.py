import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
CHALLENGES = ROOT / "challenges"
PACKS = {
    "evidence-integrity", "temporal-reasoning", "instruction-resistance",
    "multi-agent-coordination", "technical-reasoning", "privacy-authorization",
    "scientific-reasoning", "failure-recovery", "resource-optimization",
    "reproducibility",
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_laboratory_pack_is_populated_and_linked():
    for pack_id in PACKS:
        folder = CHALLENGES / pack_id
        manifest = read_json(folder / "challenge.json")
        fixture = read_json(folder / "fixture.json")
        expected = read_json(folder / "expected.json")
        assert manifest["id"] == pack_id
        assert manifest["seed"] == fixture["seed"]
        assert manifest["fixture"] == "fixture.json"
        assert manifest["expected"] == "expected.json"
        assert fixture["classification"] == "synthetic"
        assert fixture["environment"]["network"] == "disabled"
        assert fixture["environment"]["submission_execution"] == "disabled"
        assert expected["behavior"]
        evidence_ids = {item["id"] for item in fixture["evidence"]}
        assert len(evidence_ids) == len(fixture["evidence"])
        for key in ("owner_evidence_ids", "permitted_evidence_ids", "evidence_ids",
                    "authoritative_ids", "conflict_ids"):
            if key in expected:
                assert set(expected[key]) <= evidence_ids


def test_permissions_provenance_and_scoring_are_declared():
    for pack_id in PACKS:
        manifest = read_json(CHALLENGES / pack_id / "challenge.json")
        assert manifest["provenance"]["classification"] == "synthetic"
        assert manifest["provenance"]["real_world_evidence"] is False
        assert manifest["permissions"] == {
            "network": False,
            "filesystem": "bundled-fixture-only",
            "execute_submission_code": False,
            "tools": manifest["permissions"]["tools"],
        }
        assert set(manifest["permissions"]["tools"]) <= {"lookup_evidence", "calculate_sum", "transient_lookup"}
        scoring = manifest["scoring"]
        assert scoring["behavior_weight"] + scoring["traceability_weight"] + scoring["format_weight"] == 100
        assert manifest["limits"]["external_dependencies"] is False
