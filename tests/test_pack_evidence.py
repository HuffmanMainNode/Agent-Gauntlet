import hashlib
import json
from pathlib import Path

import pytest

from gauntlet.fixture_variants import generate_seeded_fixture
from gauntlet.pack_runner import (
    PackValidationError,
    run_pack_suite,
    verify_pack_suite,
)


def _canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            .encode("utf-8"))


def test_seeded_pack_run_emits_verifiable_bundle(tmp_path, monkeypatch):
    import gauntlet.tool_loop as tool_loop

    response = {
        "behavior": "calculate_exactly",
        "value": 12800,
        "unit": "bytes",
        "evidence_ids": ["R-001"],
        "calculation": "3 * 4096 + 512",
    }
    transcript = []

    def fake_run(command, task, fixture, allowed_tools, policy, artifact_root):
        run_dir = Path(artifact_root) / "fake-run"
        run_dir.mkdir(parents=True)
        containment = {"filesystem_sandboxed": False, "effective_mode": "rlimit_only"}
        execution = {"returncode": 0, "timed_out": False, "stdout_bytes": 0,
                     "stderr_bytes": 0, "stdout_truncated": False,
                     "stderr_truncated": False}
        (run_dir / "containment.json").write_text(json.dumps(containment), encoding="utf-8")
        (run_dir / "execution.json").write_text(json.dumps(execution), encoding="utf-8")
        return {
            "protocol": "tool-loop-v1",
            "final_commit": response,
            "transcript": transcript,
            "transcript_sha256": hashlib.sha256(_canonical(transcript)).hexdigest(),
            "tool_calls": 0,
            "permission_violations": 0,
            "denied_tool_calls": {},
            "retry_loop_count": 0,
            "recovery_credit": 0,
            "unrecovered_operations": [],
            "score_adjustment": 0,
            "turns": 1,
            "execution": execution,
            "containment": containment,
            "containment_report_path": str(run_dir / "containment.json"),
        }

    monkeypatch.setattr(tool_loop, "run_tool_loop", fake_run)
    bundle = run_pack_suite(
        "technical-reasoning", ["python", "adapter.py"], [3, 8], tmp_path,
        "test-adapter", "git:abc123", "test-operator",
    )
    report = verify_pack_suite(bundle)
    assert report["valid"] is True
    assert report["seeds"] == [3, 8]
    assert report["completed"] == 2
    assert report["execution_failures"] == 0
    assert report["passed"] == 2
    assert (bundle / "fixtures" / "3.json").is_file()
    assert (bundle / "fixtures" / "8.json").is_file()


def test_pack_run_rejects_duplicate_or_invalid_seeds(tmp_path):
    with pytest.raises(PackValidationError, match="unique"):
        run_pack_suite("technical-reasoning", ["python", "adapter.py"], [1, 1],
                       tmp_path, "adapter", "v1")
    with pytest.raises(PackValidationError, match="non-negative"):
        run_pack_suite("technical-reasoning", ["python", "adapter.py"], [-1],
                       tmp_path, "adapter", "v1")


def test_pack_run_verifier_rejects_tampered_transcript(tmp_path, monkeypatch):
    import gauntlet.tool_loop as tool_loop

    response = {
        "behavior": "calculate_exactly", "value": 12800, "unit": "bytes",
        "evidence_ids": ["R-001"], "calculation": "3 * 4096 + 512",
    }

    def fake_run(command, task, fixture, allowed_tools, policy, artifact_root):
        run_dir = Path(artifact_root) / "fake-run"
        run_dir.mkdir(parents=True)
        containment = {"filesystem_sandboxed": False}
        execution = {"returncode": 0, "timed_out": False, "stdout_bytes": 0,
                     "stderr_bytes": 0, "stdout_truncated": False,
                     "stderr_truncated": False}
        (run_dir / "containment.json").write_text(json.dumps(containment), encoding="utf-8")
        (run_dir / "execution.json").write_text(json.dumps(execution), encoding="utf-8")
        return {
            "protocol": "tool-loop-v1", "final_commit": response, "transcript": [],
            "transcript_sha256": hashlib.sha256(_canonical([])).hexdigest(),
            "tool_calls": 0, "permission_violations": 0, "denied_tool_calls": {},
            "retry_loop_count": 0, "recovery_credit": 0, "unrecovered_operations": [],
            "score_adjustment": 0, "turns": 1,
            "execution": execution,
            "containment": containment,
            "containment_report_path": str(run_dir / "containment.json"),
        }

    monkeypatch.setattr(tool_loop, "run_tool_loop", fake_run)
    bundle = run_pack_suite("technical-reasoning", ["python", "adapter.py"], [1],
                            tmp_path, "adapter", "v1")
    results_path = bundle / "results.json"
    rows = json.loads(results_path.read_text(encoding="utf-8"))
    rows[0]["tool_loop"]["transcript"].append({"forged": True})
    results_path.write_text(json.dumps(rows), encoding="utf-8")
    with pytest.raises(PackValidationError, match="digest mismatch"):
        verify_pack_suite(bundle)


def test_pack_run_preserves_failed_attempts(tmp_path, monkeypatch):
    import gauntlet.tool_loop as tool_loop

    def failing_run(command, task, fixture, allowed_tools, policy, artifact_root):
        run_dir = Path(artifact_root) / "failed-run"
        run_dir.mkdir(parents=True)
        containment = {"filesystem_sandboxed": False}
        execution = {"returncode": -9, "timed_out": True, "stdout_bytes": 0,
                     "stderr_bytes": 0, "stdout_truncated": False,
                     "stderr_truncated": False}
        (run_dir / "containment.json").write_text(json.dumps(containment), encoding="utf-8")
        (run_dir / "execution.json").write_text(json.dumps(execution), encoding="utf-8")
        raise TimeoutError("adapter did not commit")

    monkeypatch.setattr(tool_loop, "run_tool_loop", failing_run)
    bundle = run_pack_suite("technical-reasoning", ["python", "slow-agent.py"], [5],
                            tmp_path, "slow-agent", "v1")
    report = verify_pack_suite(bundle)
    assert report["valid"] is True
    assert report["execution_failures"] == 1
    rows = json.loads((bundle / "results.json").read_text(encoding="utf-8"))
    assert rows[0]["status"] == "failed"
    assert rows[0]["error_type"] == "TimeoutError"
    assert len(rows[0]["failure_artifacts"]) == 2


def test_seeded_fixture_generator_is_deterministic_and_preserves_evidence(tmp_path):
    from gauntlet.pack_runner import load_pack

    base = load_pack("evidence-integrity").fixture
    first = generate_seeded_fixture(base, 1)
    repeat = generate_seeded_fixture(base, 1)
    second = generate_seeded_fixture(base, 5)
    assert first == repeat
    assert first["seed"] == 1
    assert second["seed"] == 5
    assert first["variant"]["generator"] == "evidence-order-sha256-v1"
    assert first["variant"]["evidence_order"] != second["variant"]["evidence_order"]
    assert {item["id"] for item in first["evidence"]} == {
        item["id"] for item in base["evidence"]
    }
    assert first["evidence"] != base["evidence"]
    assert base["seed"] == 20261122
