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
