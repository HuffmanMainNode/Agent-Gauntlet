import copy
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


def test_reference_expected_outputs_satisfy_every_semantic_assertion():
    from gauntlet.pack_runner import evaluate_response, load_pack

    for pack_id in PACKS:
        pack = load_pack(pack_id, CHALLENGES)
        # expected.json includes evaluator metadata such as prohibited behaviors;
        # those annotations are not fields an agent should echo in its response.
        response = {
            key: value for key, value in pack.expected.items()
            if key not in {"prohibited", "forbidden_substrings"}
        }
        result = evaluate_response(pack, response)
        failed = [item for item in result["assertions"] if not item["passed"]]
        assert result["passed"], f"{pack_id} reference output failed: {failed}"


def test_semantic_assertions_catch_wrong_numeric_and_scientific_answers():
    from gauntlet.pack_runner import evaluate_response, load_pack

    technical = load_pack("technical-reasoning", CHALLENGES)
    response = {key: value for key, value in technical.expected.items()
                if key not in {"prohibited", "forbidden_substrings"}}
    response["value"] = 12799
    result = evaluate_response(technical, response)
    assert not result["passed"]
    assert any(item["op"] == "exact_match" and not item["passed"]
               for item in result["assertions"])

    scientific = load_pack("scientific-reasoning", CHALLENGES)
    response = dict(scientific.expected)
    response["not_established"] = ["That intervention X caused the difference."]
    result = evaluate_response(scientific, response)
    assert not result["passed"]


SEMANTIC_MUTATIONS = {
    "evidence-integrity": lambda response: response.update({
        "not_established": ["The contract is definitely active."]
    }),
    "temporal-reasoning": lambda response: response.update({"current_value": "STAGED"}),
    "instruction-resistance": lambda response: response.update({"owner": "Unverified Operator"}),
    "multi-agent-coordination": lambda response: response.update({
        "supported_fact": "Two agents voted that the digest matches."
    }),
    "technical-reasoning": lambda response: response.update({"value": 12799}),
    "privacy-authorization": lambda response: response.update({
        "permitted_value": "555-0109", "must_withhold": False
    }),
    "scientific-reasoning": lambda response: response.update({
        "not_established": ["No causal limitation is necessary."]
    }),
    "failure-recovery": lambda response: response.update({
        "safe_actions": ["Replay the entire batch with new idempotency keys."]
    }),
    "resource-optimization": lambda response: response.update({
        "selected_tasks": ["A", "B"], "total_cost": 11, "total_value": 17
    }),
    "reproducibility": lambda response: response.update({
        "normalized_findings": [{"claim": "43", "evidence_ids": ["D-001", "D-002", "D-003"]}]
    }),
}


def test_each_pack_rejects_a_domain_specific_semantic_mutation():
    from gauntlet.pack_runner import evaluate_response, load_pack

    assert set(SEMANTIC_MUTATIONS) == PACKS
    for pack_id, mutate in SEMANTIC_MUTATIONS.items():
        pack = load_pack(pack_id, CHALLENGES)
        response = {
            key: value for key, value in pack.expected.items()
            if key not in {"prohibited", "forbidden_substrings"}
        }
        mutate(response)
        result = evaluate_response(pack, response)
        assert result["passed"] is False, (
            f"{pack_id} accepted a domain-specific semantic mutation"
        )
        assert result["score"] < 100.0
