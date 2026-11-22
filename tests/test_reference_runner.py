import json
from pathlib import Path

from gauntlet.reference_runner import run_reference_matrix, verify_reference_baseline

def test_reference_matrix_is_reproducible_and_verifiable(tmp_path):
    path=run_reference_matrix(tmp_path/"reference",seeds=[1,2])
    report=json.loads(path.read_text(encoding="utf-8"))
    assert report["synthetic"] is True
    assert report["seed_count"]==2
    assert report["profile_count"]==4
    assert report["suite_run_count"]==14
    assert report["case_count"]==28
    assert report["all_bundles_verified"] is True
    verified=verify_reference_baseline(path)
    assert verified["valid"] is True
    assert verified["runs_checked"]==14

def test_reference_profiles_expose_expected_failure_modes(tmp_path):
    path=run_reference_matrix(tmp_path/"reference",seeds=[3])
    report=json.loads(path.read_text(encoding="utf-8"))
    by_key={(item["profile"],item["suite"]):item for item in report["runs"]}
    assert by_key[("demo-good","hallucination")]["behavior_pass_rate"]==1.0
    assert by_key[("demo-good","injection")]["behavior_pass_rate"]==1.0
    assert by_key[("demo-good","stateful")]["behavior_pass_rate"]==1.0
    assert by_key[("demo-bad","hallucination")]["behavior_pass_rate"]==0.0
    assert by_key[("demo-vulnerable-injection","injection")]["behavior_pass_rate"]==0.0
    assert by_key[("demo-stale-state","stateful")]["behavior_pass_rate"]==0.0

def test_reference_baseline_digest_tampering_is_detected(tmp_path):
    path=run_reference_matrix(tmp_path/"reference",seeds=[4])
    report=json.loads(path.read_text(encoding="utf-8"))
    report["case_count"]+=1
    path.write_text(json.dumps(report),encoding="utf-8")
    import pytest
    with pytest.raises(ValueError,match="digest mismatch"):
        verify_reference_baseline(path)
