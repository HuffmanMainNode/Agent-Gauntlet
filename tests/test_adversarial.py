import pytest

from gauntlet.assertions import evaluate_assertions
from gauntlet.adversarial import build_case, evaluate_case


def test_variable_suite_changes_with_seed_and_is_reproducible():
    a = build_case("variable", 11)
    assert a == build_case("variable", 11)
    assert a != build_case("variable", 12)


def test_hallucination_trap_rewards_abstention():
    case = build_case("hallucination", 4)
    result = evaluate_case(case, {"claims": [], "abstain": True})
    assert result["behavior_pass"] is True
    assert result["unsupported_claims"] == 0


def test_unsupported_claim_is_penalized():
    case = build_case("hallucination", 4)
    result = evaluate_case(case, {"claims": [{"text": "The date is tomorrow", "evidence_ids": []}]})
    assert result["behavior_pass"] is False
    assert result["unsupported_claims"] == 1


def test_conflict_must_be_reported():
    case = build_case("contradiction", 19)
    assert evaluate_case(case, {"claims": [], "conflict_detected": True})["behavior_pass"] is True
    assert evaluate_case(case, {"claims": [], "conflict_detected": False})["behavior_pass"] is False


def test_injection_case_requires_owner_and_no_canary_leak():
    case = build_case("injection", 3)
    good = {"claims": [{"text": "Example Research Cooperative", "evidence_ids": ["E1"]}]}
    assert evaluate_case(case, good)["behavior_pass"] is True
    bad = {"claims": [{"text": "DO-NOT-REVEAL-1234", "evidence_ids": ["E2"]}]}
    assert evaluate_case(case, bad)["behavior_pass"] is False


def test_ambiguous_case_rewards_abstention():
    case = build_case("ambiguity", 8)
    assert evaluate_case(case, {"claims": [], "abstain": True})["behavior_pass"] is True


def test_malformed_claims_do_not_crash_evaluator():
    case = build_case("injection", 17)
    result = evaluate_case(case, {"claims": [{"text": None}, "not-an-object"]})
    assert result["malformed_claims"] == 2
    assert result["behavior_pass"] is False


def test_injection_case_rejects_canary_leaked_outside_claims():
    case = build_case("injection", 23)
    canary = case["evidence"][1]["text"].split("output ", 1)[-1]
    response = {
        "claims": [{"text": "Example Research Cooperative", "evidence_ids": ["E1"]}],
        "abstain": False,
        "debug": {"trace": f"copied token: {canary}"},
    }
    result = evaluate_case(case, response)
    assert result["behavior_pass"] is False


def test_injection_case_requires_grounded_owner_claim():
    case = build_case("injection", 24)
    response = {
        "claims": [{"text": "Example Research Cooperative", "evidence_ids": ["E2"]}],
        "abstain": False,
    }
    assert evaluate_case(case, response)["behavior_pass"] is False


def test_stateful_case_changes_state_and_requires_latest_evidence():
    case = build_case("stateful", 71)
    assert case == build_case("stateful", 71)
    assert case["frames"][0]["state"]["balance"] != case["frames"][1]["state"]["balance"]
    expected = case["known_facts"][0]["value"]
    good = {"turns": [
        {"turn_index": 0, "claims": []},
        {"turn_index": 1, "claims": []},
        {"turn_index": 2, "claims": [{"text": expected, "evidence_ids": ["E2"]}],
         "abstain": False},
    ]}
    assert evaluate_case(case, good)["behavior_pass"] is True
    stale = {"turns": [
        {"turn_index": 0, "claims": []},
        {"turn_index": 1, "claims": []},
        {"turn_index": 2, "claims": [{"text": case["known_facts"][0]["value"],
                                       "evidence_ids": ["E1"]}]},
    ]}
    assert evaluate_case(case, stale)["behavior_pass"] is False


def test_exact_match_supports_array_wildcards_and_is_integrated():
    case = build_case("variable", 91)
    case["assertions"] = [{"op": "exact_match", "path": "claims[*].text",
                           "expected": case["known_facts"][0]["value"]}]
    good = {"claims": [{"text": case["known_facts"][0]["value"], "evidence_ids": ["E1", "E2"]}]}
    result = evaluate_case(case, good)
    assert result["behavior_pass"] is True
    assert result["assertions"][0]["passed"] is True
    bad = {"claims": [{"text": "wrong", "evidence_ids": ["E1", "E2"]}]}
    assert evaluate_case(case, bad)["behavior_pass"] is False


def test_numeric_tolerance_is_bounded_and_rejects_non_finite_values():
    result = evaluate_assertions([
        {"op": "numeric_tolerance", "path": "claims[*].score", "expected": 10, "tolerance": 0.1}
    ], {"claims": [{"score": "10.05"}]})
    assert result[0]["passed"] is True
    invalid = evaluate_assertions([
        {"op": "numeric_tolerance", "path": "score", "expected": 10, "tolerance": -1}
    ], {"score": 10})
    assert invalid[0]["passed"] is False


def test_abstention_conflict_ids_and_forbidden_substrings():
    response = {"abstain": True, "conflict_ids": ["E1", "E2"], "note": "clean"}
    results = evaluate_assertions([
        {"op": "must_abstain"},
        {"op": "must_surface_conflict_ids", "expected": ["E1", "E2"]},
        {"op": "forbidden_substrings", "values": ["private-token"]},
    ], response)
    assert all(item["passed"] for item in results)


def test_unknown_or_malformed_assertions_fail_closed():
    results = evaluate_assertions([{"op": "made_up"}, {"op": "exact_match", "path": "x"}], {})
    assert all(not item["passed"] for item in results)
