import json

import pytest

from gauntlet.leaderboard import build_scorecard, verify_scorecard, write_scorecard
from gauntlet.adversarial_runner import run_suite


def test_scorecard_is_built_from_verified_evidence(tmp_path):
    import sys
    code = "import json,sys; t=json.load(sys.stdin); print(json.dumps({'claims': [], 'abstain': True, 'conflict_detected': True}))"
    bundle = run_suite("hallucination", [sys.executable, "-c", code], [1, 2], tmp_path / "runs",
                       agent_name="Example Agent", model_id="example/model-v1",
                       adapter_version="adapter-1", operator="unspecified")
    card = build_scorecard([str(bundle)], "Example Agent", "example/model-v1", "adapter-1")
    path = write_scorecard(card, str(tmp_path / "scorecard.json"))
    report = verify_scorecard(str(path))
    assert report["valid"] is True
    assert report["suites"] == 1
    assert report["cases"] == 2
    assert card["benchmark"]["suites"]["hallucination"]["execution_failures"] == 0


def test_scorecard_tampering_is_detected(tmp_path):
    import sys
    code = "import json,sys; json.load(sys.stdin); print(json.dumps({'claims': [], 'abstain': True}))"
    bundle = run_suite("hallucination", [sys.executable, "-c", code], [1], tmp_path / "runs",
                       agent_name="Example Agent", model_id="example/model-v1",
                       adapter_version="adapter-1", operator="unspecified")
    card = build_scorecard([str(bundle)], "Example Agent", "example/model-v1", "adapter-1")
    path = write_scorecard(card, str(tmp_path / "scorecard.json"))
    data = json.loads(path.read_text())
    data["balanced_behavior_index"] = 100
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="digest mismatch"):
        verify_scorecard(str(path))


def test_duplicate_suite_is_rejected(tmp_path):
    import sys
    code = "import json,sys; json.load(sys.stdin); print(json.dumps({'claims': [], 'abstain': True}))"
    bundle = run_suite("hallucination", [sys.executable, "-c", code], [1], tmp_path / "runs",
                       agent_name="Example Agent", model_id="example/model-v1",
                       adapter_version="adapter-1", operator="unspecified")
    with pytest.raises(ValueError, match="Duplicate suite"):
        build_scorecard([str(bundle), str(bundle)], "Example Agent", "example/model-v1", "adapter-1")


def test_scorecard_reports_execution_failures(tmp_path):
    import sys
    code = "import time; time.sleep(5)"
    bundle = run_suite("hallucination", [sys.executable, "-c", code], [51], tmp_path / "runs",
                      timeout_seconds=1, agent_name="Example Agent",
                      model_id="example/model-v1", adapter_version="adapter-1")
    card = build_scorecard([str(bundle)], "Example Agent", "example/model-v1", "adapter-1")
    assert card["benchmark"]["suites"]["hallucination"]["execution_failures"] == 1
    assert card["benchmark"]["suites"]["hallucination"]["behavior_pass_rate"] == 0
