import json
import sys

from gauntlet.adversarial_runner import run_suite
from gauntlet.runner import verify


def test_seeded_adversarial_run_produces_evidence(tmp_path):
    code = (
        "import json,sys; t=json.load(sys.stdin); "
        "print(json.dumps({'claims': [], 'abstain': True, 'conflict_detected': True}))"
    )
    bundle = run_suite("hallucination", [sys.executable, "-c", code], [1, 2, 3], tmp_path,
                      agent_name="Example", model_id="example/model-v1", adapter_version="adapter-1")
    evidence = json.loads((bundle / "evidence.json").read_text())
    summary = json.loads((bundle / "summary.json").read_text())
    assert evidence["attestation"] == "unsigned-local-run"
    assert len(evidence["seeds"]) == 3
    assert summary["cases"] == 3
    assert "adapter_command" not in evidence
    assert verify(bundle)["valid"] is True


def test_adapter_timeout_is_preserved_as_failed_case(tmp_path):
    code = "import time; time.sleep(5)"
    bundle = run_suite("hallucination", [sys.executable, "-c", code], [7, 8], tmp_path,
                      timeout_seconds=1, agent_name="Example", model_id="example/model-v1",
                      adapter_version="adapter-1")
    rows = json.loads((bundle / "results.json").read_text())
    summary = json.loads((bundle / "summary.json").read_text())
    assert len(rows) == 2
    assert all(row["execution"]["status"] == "failed" for row in rows)
    assert all(row["evaluation"]["score"] == 0 for row in rows)
    assert summary["execution_failures"] == 2
    assert verify(bundle)["valid"] is True


def test_malformed_adapter_output_is_preserved_as_failed_case(tmp_path):
    bundle = run_suite("hallucination", [sys.executable, "-c", "print('not-json')"], [9], tmp_path,
                      agent_name="Example", model_id="example/model-v1", adapter_version="adapter-1")
    rows = json.loads((bundle / "results.json").read_text())
    assert rows[0]["execution"]["status"] == "failed"
    assert rows[0]["execution"]["error_type"] == "ValueError"
    assert verify(bundle)["valid"] is True


def test_duplicate_seeds_are_rejected_before_execution(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="unique"):
        run_suite("hallucination", [sys.executable, "-c", "pass"], [1, 1], tmp_path,
                  agent_name="Example", model_id="example/model-v1", adapter_version="adapter-1")


def test_verifier_rejects_failure_record_with_nonzero_score(tmp_path):
    import hashlib
    from gauntlet.runner import canonical_bytes

    code = "import json,sys; json.load(sys.stdin); print(json.dumps({'claims': [], 'abstain': True}))"
    bundle = run_suite("hallucination", [sys.executable, "-c", code], [31], tmp_path,
                       agent_name="Example", model_id="example/model-v1", adapter_version="adapter-1")
    rows = json.loads((bundle / "results.json").read_text())
    rows[0]["execution"] = {"status": "failed", "error_type": "TimeoutError", "error": "forced test"}
    # Deliberately retain the successful score: the verifier must reject this contradiction.
    (bundle / "results.json").write_bytes(canonical_bytes(rows))
    evidence = json.loads((bundle / "evidence.json").read_text())
    evidence["artifacts"]["results.json"] = hashlib.sha256((bundle / "results.json").read_bytes()).hexdigest()
    (bundle / "evidence.json").write_bytes(canonical_bytes(evidence))
    import pytest
    with pytest.raises(ValueError, match="evaluation mismatch"):
        verify(bundle)


def test_verifier_rejects_case_not_matching_declared_seed(tmp_path):
    import hashlib
    from gauntlet.runner import canonical_bytes

    code = "import json,sys; json.load(sys.stdin); print(json.dumps({'claims': [], 'abstain': True}))"
    bundle = run_suite("hallucination", [sys.executable, "-c", code], [41], tmp_path,
                       agent_name="Example", model_id="example/model-v1", adapter_version="adapter-1")
    rows = json.loads((bundle / "results.json").read_text())
    rows[0]["case"]["question"] = "FORGED QUESTION"
    (bundle / "results.json").write_bytes(canonical_bytes(rows))
    evidence = json.loads((bundle / "evidence.json").read_text())
    evidence["artifacts"]["results.json"] = hashlib.sha256((bundle / "results.json").read_bytes()).hexdigest()
    (bundle / "evidence.json").write_bytes(canonical_bytes(evidence))
    import pytest
    with pytest.raises(ValueError, match="deterministic generator"):
        verify(bundle)
