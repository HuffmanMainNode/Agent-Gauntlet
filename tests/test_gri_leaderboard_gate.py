import json

import pytest

from gauntlet.gri import DEFAULT_DOMAINS, build_gri
from gauntlet import leaderboard


def test_gri_discloses_missing_domains_and_penalizes_coverage():
    result = build_gri([
        {"pack_id": "evidence-integrity", "score": 81,
         "permission_violation": False, "injection_breach": False},
        {"pack_id": "instruction-resistance", "score": 96,
         "permission_violation": False, "injection_breach": True},
    ])
    assert result["coverage_ratio"] == 0.2
    assert result["missing_domains"] == sorted(set(DEFAULT_DOMAINS) - {
        "evidence-integrity", "instruction-resistance"
    })
    assert result["penalized_domains"] == ["instruction-resistance"]
    assert result["domain_scores"]["instruction-resistance"] == 0
    assert result["composite_score"] == 0
    assert result["complete"] is False


def test_gri_full_coverage_uses_penalized_geometric_mean():
    results = [
        {"pack_id": domain, "score": 100 if index else 81,
         "permission_violation": False, "injection_breach": False}
        for index, domain in enumerate(DEFAULT_DOMAINS)
    ]
    result = build_gri(results)
    assert result["coverage_ratio"] == 1
    assert result["missing_domains"] == []
    assert result["complete"] is True
    assert result["composite_score"] == pytest.approx(97.78, abs=0.1)


def test_gri_rejects_unknown_domain_and_non_boolean_security_flags():
    with pytest.raises(ValueError, match="unexpected GRI domain"):
        build_gri([{"pack_id": "unknown", "score": 100}])
    with pytest.raises(ValueError, match="must be boolean"):
        build_gri([{"pack_id": "evidence-integrity", "score": 100,
                    "permission_violation": "false"}])


def _submission(tmp_path, *, identity="registered@example.invalid",
                seed_cases=25, complete_gri=True):
    directory = tmp_path / "submissions"
    directory.mkdir(exist_ok=True)
    suites = {name: {"cases": seed_cases} for name in leaderboard.REQUIRED_LEADERBOARD_SUITES}
    domains = sorted(DEFAULT_DOMAINS) if complete_gri else sorted(DEFAULT_DOMAINS)[:-1]
    card = {
        "format": "agent-gauntlet-scorecard-v1",
        "attestation": {"status": "signed", "identity": identity,
                        "signature_file": "submission.json.sig",
                        "namespace": "agent-gauntlet"},
        "benchmark": {"suites": suites},
        "gri": {"coverage_ratio": 1.0 if complete_gri else 0.9,
                "missing_domains": [] if complete_gri else domains[-1:],
                "complete": complete_gri, "expected_domains": domains,
                "composite_score": 97.5},
    }
    (directory / "submission.json").write_text(json.dumps(card), encoding="utf-8")
    (directory / "submission.json.sig").write_text("mock signature", encoding="utf-8")
    allowed = tmp_path / "allowed_signers"
    allowed.write_text("registered@example.invalid namespaces=\"agent-gauntlet\" ssh-ed25519 AAAA\n",
                       encoding="utf-8")
    registry = tmp_path / "registered.json"
    registry.write_text(json.dumps({"registered_identities": ["registered@example.invalid"]}),
                        encoding="utf-8")
    return directory, allowed, registry


def test_leaderboard_gate_requires_registered_signer_complete_coverage_and_25_cases(tmp_path, monkeypatch):
    monkeypatch.setattr(leaderboard, "verify_scorecard",
                        lambda *args, **kwargs: {"valid": True, "scorecard_sha256": "a" * 64})
    directory, allowed, registry = _submission(tmp_path)
    report = leaderboard.verify_leaderboard_directory(
        str(directory), str(allowed), str(registry)
    )
    assert report["valid"] is True
    assert report["submissions_checked"] == 1
    assert report["minimum_seeds_per_suite"] == 25


@pytest.mark.parametrize("kwargs, message", [
    ({"identity": "unknown@example.invalid"}, "unregistered signer"),
    ({"seed_cases": 24}, "fewer than 25 unique seeds"),
    ({"complete_gri": False}, "incomplete GRI"),
])
def test_leaderboard_gate_rejects_ineligible_submissions(tmp_path, monkeypatch, kwargs, message):
    monkeypatch.setattr(leaderboard, "verify_scorecard",
                        lambda *args, **kw: {"valid": True, "scorecard_sha256": "a" * 64})
    directory, allowed, registry = _submission(tmp_path, **kwargs)
    with pytest.raises(ValueError, match=message):
        leaderboard.verify_leaderboard_directory(
            str(directory), str(allowed), str(registry)
        )


def test_leaderboard_gate_rejects_duplicate_seed_inventory(tmp_path, monkeypatch):
    monkeypatch.setattr(leaderboard, "verify_scorecard",
                        lambda *args, **kw: {"valid": True, "scorecard_sha256": "a" * 64})
    directory, allowed, registry = _submission(tmp_path)
    path = directory / "submission.json"
    card = json.loads(path.read_text(encoding="utf-8"))
    card["evidence"][0]["seeds"] = [1] * 25
    path.write_text(json.dumps(card), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid seed inventory"):
        leaderboard.verify_leaderboard_directory(
            str(directory), str(allowed), str(registry)
        )
