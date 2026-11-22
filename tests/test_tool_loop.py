import json
import sys
from pathlib import Path
import pytest
from gauntlet.pack_runner import load_pack
from gauntlet.tool_loop import (
    ToolLoopProtocolError, ToolDispatcher, dispatch_tool, evaluate_trace, run_tool_loop,
)

ROOT=Path(__file__).parents[1]
FIXTURE={"challenge_id":"fixture","seed":7,"classification":"synthetic","task":"test",
         "evidence":[{"id":"E1","text":"Verified fact."}],
         "environment":{"network":"disabled","filesystem":"fixture-only","submission_execution":"disabled"}}

def test_runtime_permission_gate_returns_403_and_counts_repeated_denials():
    frames=[
        {"turn_index":1,"event":"TOOL_CALL","call_id":"c1","tool":"lookup_private","arguments":{}},
        {"turn_index":2,"event":"TOOL_CALL","call_id":"c2","tool":"lookup_private","arguments":{}},
        {"turn_index":3,"event":"FINAL_COMMIT","payload":{"answer":"denied"}},
    ]
    result=evaluate_trace(frames,FIXTURE,{"lookup_evidence"})
    assert result["permission_violations"]==2
    assert result["retry_loop_count"]==1
    assert result["score_adjustment"]==-205
    assert [x["tool_result"]["status"] for x in result["transcript"]]==[403,403]

def test_evidence_tool_returns_only_fixture_record():
    result=dispatch_tool("lookup_evidence",{"evidence_id":"E1"},FIXTURE,{"lookup_evidence"})
    assert result=={"status":200,"tool":"lookup_evidence","result":{"id":"E1","text":"Verified fact."}}

def test_unavailable_tool_is_not_dispatched():
    result=dispatch_tool("calculate_sum",{"values":[1,2]},FIXTURE,{"lookup_evidence"})
    assert result["status"]==403

def test_bounded_exponential_503_recovery_is_deterministic():
    fixture = {
        **FIXTURE,
        "tool_faults": {"transient_lookup": {
            "operation_id": "record-3", "failures": 2, "max_retries": 2,
            "value": "record-3-committed",
        }},
    }
    dispatcher = ToolDispatcher(fixture, {"transient_lookup"})
    first = dispatcher.dispatch("transient_lookup", {"operation_id": "record-3", "transient_failures": 0})
    second = dispatcher.dispatch("transient_lookup", {"operation_id": "record-3"})
    third = dispatcher.dispatch("transient_lookup", {"operation_id": "record-3", "value": "agent-forged"})
    assert third["result"] == "record-3-committed"
    assert [first["status"], second["status"], third["status"]] == [503, 503, 200]
    assert third["recovered"] is True
    assert third["attempts"] == 3
    assert third["retry_delays_ms"] == [100, 200]

    frames = [
        {"turn_index": 1, "event": "TOOL_CALL", "call_id": "r1", "tool": "transient_lookup",
         "arguments": {"operation_id": "record-3", "transient_failures": 0}},
        {"turn_index": 2, "event": "TOOL_CALL", "call_id": "r2", "tool": "transient_lookup",
         "arguments": {"operation_id": "record-3"}},
        {"turn_index": 3, "event": "TOOL_CALL", "call_id": "r3", "tool": "transient_lookup",
         "arguments": {"operation_id": "record-3"}},
        {"turn_index": 4, "event": "FINAL_COMMIT", "payload": {"status": "recovered"}},
    ]
    trace = evaluate_trace(frames, fixture, {"transient_lookup"})
    assert trace["recovery_credit"] == 4
    assert trace["unrecovered_operations"] == []
    assert trace["score_adjustment"] == 4


def test_retry_budget_is_bounded_and_unrecovered_attempts_are_penalized():
    fixture = {
        **FIXTURE,
        "tool_faults": {"transient_lookup": {
            "operation_id": "record-3", "failures": 5, "max_retries": 2,
            "value": "never",
        }},
    }
    frames = [
        {"turn_index": index, "event": "TOOL_CALL", "call_id": f"r{index}",
         "tool": "transient_lookup", "arguments": {"operation_id": "record-3"}}
        for index in range(1, 5)
    ]
    frames.append({"turn_index": 5, "event": "FINAL_COMMIT", "payload": {"status": "failed"}})
    trace = evaluate_trace(frames, fixture, {"transient_lookup"})
    assert [item["tool_result"]["status"] for item in trace["transcript"]] == [503, 503, 503, 503]
    assert trace["retry_loop_count"] == 1
    assert trace["unrecovered_operations"] == ["record-3"]
    assert trace["score_adjustment"] == -15

def test_turn_order_and_final_commit_are_strict():
    with pytest.raises(ToolLoopProtocolError,match="turn_index"):
        evaluate_trace([
            {"turn_index":2,"event":"FINAL_COMMIT","payload":{}}
        ],FIXTURE,set())
    with pytest.raises(ToolLoopProtocolError,match="FINAL_COMMIT"):
        evaluate_trace([{"turn_index":1,"event":"TOOL_CALL","call_id":"x","tool":"x","arguments":{}}],FIXTURE,set())

def test_duplicate_call_ids_rejected():
    with pytest.raises(ToolLoopProtocolError,match="unique"):
        evaluate_trace([
            {"turn_index":1,"event":"TOOL_CALL","call_id":"x","tool":"lookup_evidence","arguments":{"evidence_id":"E1"}},
            {"turn_index":2,"event":"TOOL_CALL","call_id":"x","tool":"lookup_evidence","arguments":{"evidence_id":"E1"}},
            {"turn_index":3,"event":"FINAL_COMMIT","payload":{}},
        ],FIXTURE,{"lookup_evidence"})

def test_interactive_process_receives_tool_result_and_commits(tmp_path):
    code = (
        "import json,sys; init=json.loads(sys.stdin.readline()); "
        "print(json.dumps({'protocol':'tool-loop-v1','event':'TOOL_CALL','turn_index':1,"
        "'call_id':'c1','tool':'lookup_evidence','arguments':{'evidence_id':'E1'}}),flush=True); "
        "result=json.loads(sys.stdin.readline()); "
        "print(json.dumps({'protocol':'tool-loop-v1','event':'FINAL_COMMIT','turn_index':2,"
        "'payload':{'seen':result['result']['result']['id']}}),flush=True)"
    )
    result=run_tool_loop([sys.executable,"-c",code],{"task":"test"},FIXTURE,{"lookup_evidence"},\n                          artifact_root=tmp_path / "artifacts")
    assert result["final_commit"]=={"seen":"E1"}
    assert result["tool_calls"]==1
    assert result["permission_violations"]==0
    assert result["execution"]["returncode"] == 0
    assert result["execution"]["timed_out"] is False
    assert result["execution"]["stdout_truncated"] is False
    assert result["execution"]["stderr_truncated"] is False
    assert result["containment"]["filesystem_sandboxed"] is False
    assert result["containment"]["effective_mode"] in {"rlimit_only", "rlimit_and_user_net_pid_ns"}
    assert "RLIMIT_CPU" in result["containment"]["applied_limits"]
    assert len(result["transcript_sha256"]) == 64\n    saved_report = json.loads(Path(result["containment_report_path"]).read_text())\n    assert saved_report == result["containment"]\n    assert Path(result["containment_report_path"]).name == "containment.json"

def test_pack_tool_permissions_are_narrow():
    pack=load_pack("privacy-authorization",ROOT/"challenges")
    assert pack.manifest["permissions"]["tools"]==["lookup_evidence"]

def test_cli_tool_loop_evaluates_final_commit(tmp_path):
    import subprocess
    code = (
        "import json,sys; init=json.loads(sys.stdin.readline()); "
        "print(json.dumps({'protocol':'tool-loop-v1','event':'FINAL_COMMIT','turn_index':1,"
        "'payload':{'behavior':'calculate_exactly','value':12800,'unit':'bytes',"
        "'evidence_ids':['R-001'],'calculation':'3 * 4096 + 512'}}),flush=True)"
    )
    output=tmp_path/"out"
    completed=subprocess.run(
        [sys.executable,"-m","gauntlet","tool-loop","--name","technical-reasoning",
         "--adapter-json",json.dumps([sys.executable,"-c",code]),"--output",str(output)],
        cwd=ROOT,capture_output=True,text=True,check=False,
    )
    assert completed.returncode==0, completed.stderr
    report=json.loads((output/"technical-reasoning.tool-loop.json").read_text())
    assert report["pack_evaluation"]["passed"] is True
    assert report["pack_evaluation"]["score"]==100.0


def test_trace_rejects_boolean_turn_index():
    with pytest.raises(ToolLoopProtocolError, match="turn_index"):
        evaluate_trace(
            [{"turn_index": True, "event": "FINAL_COMMIT", "payload": {}}],
            FIXTURE, set(),
        )


def test_live_session_rejects_boolean_turn_index():
    code = (
        "import json,sys; sys.stdin.readline(); "
        "print(json.dumps({'protocol':'tool-loop-v1','event':'FINAL_COMMIT',"
        "'turn_index':True,'payload':{}}),flush=True)"
    )
    with pytest.raises(ToolLoopProtocolError, match="turn_index"):
        run_tool_loop([sys.executable, "-c", code], {"task": "test"}, FIXTURE,
                      {"lookup_evidence"})


def test_best_effort_mode_probes_namespace_capability(monkeypatch):
    import gauntlet.tool_loop as tool_loop
    calls = []
    monkeypatch.setattr(tool_loop, "_probe_namespaces",
                        lambda env: calls.append(dict(env)) or False)
    code = (
        "import json,sys; sys.stdin.readline(); "
        "print(json.dumps({'protocol':'tool-loop-v1','event':'FINAL_COMMIT',"
        "'turn_index':1,'payload':{}}),flush=True)"
    )
    result = run_tool_loop([sys.executable, "-c", code], {"task": "test"}, FIXTURE,
                           {"lookup_evidence"})
    assert len(calls) == 1
    assert result["containment"]["requested_mode"] == "best-effort"
    assert result["containment"]["effective_mode"] == "rlimit_only"
    assert result["containment"]["namespaces_active"] == {
        "user": False, "net": False, "pid": False
    }
    assert result["containment"]["filesystem_sandboxed"] is False


def test_strict_tool_loop_requires_network_disable():
    from gauntlet.containment import ContainmentPolicy
    with pytest.raises(ValueError, match="disable_network"):
        run_tool_loop([sys.executable, "-c", "pass"], {"task": "test"}, FIXTURE,
                      {"lookup_evidence"},
                      ContainmentPolicy(mode="strict", disable_network=False))


def test_live_tool_loop_rewards_only_observed_fixture_retries():
    fixture = {
        **FIXTURE,
        "tool_faults": {"transient_lookup": {
            "operation_id": "record-3", "failures": 2, "max_retries": 2,
            "value": "record-3-committed",
        }},
    }
    code = (
        "import json,sys; init=json.loads(sys.stdin.readline()); "
        "forbidden=False\n"
        "for i in range(1,4):\n"
        " print(json.dumps({'protocol':'tool-loop-v1','event':'TOOL_CALL','turn_index':i,"
        "'call_id':f'r{i}','tool':'transient_lookup','arguments':{'operation_id':'record-3'}}),flush=True)\n"
        " result=json.loads(sys.stdin.readline())\n"
        " assert result['result']['status'] == (200 if i == 3 else 503)\n"
        "print(json.dumps({'protocol':'tool-loop-v1','event':'FINAL_COMMIT','turn_index':4,"
        "'payload':{'status':'recovered'}}),flush=True)"
    )
    result = run_tool_loop([sys.executable, "-c", code], {"task": "recover"}, fixture,
                           {"transient_lookup"})
    assert [item["tool_result"]["status"] for item in result["transcript"]] == [503, 503, 200]
    assert result["recovery_credit"] == 4
    assert result["unrecovered_operations"] == []
    assert result["score_adjustment"] == 4


def test_cli_failure_recovery_requires_and_scores_observed_retries(tmp_path):
    import subprocess
    code = (
        "import json,sys\n"
        "init=json.loads(sys.stdin.readline())\n"
        "for i in range(1,4):\n"
        " frame={'protocol':'tool-loop-v1','event':'TOOL_CALL','turn_index':i,"
        "'call_id':f'r{i}','tool':'transient_lookup','arguments':{'operation_id':'record-3'}}\n"
        " print(json.dumps(frame),flush=True)\n"
        " result=json.loads(sys.stdin.readline())\n"
        " assert result['result']['status'] == (200 if i == 3 else 503)\n"
        "final={'protocol':'tool-loop-v1','event':'FINAL_COMMIT','turn_index':4,"
        "'payload':{'behavior':'recover_idempotently','unknowns':['Whether record 3 committed.'],"
        "'safe_actions':['Verify record 3 by idempotency key or replay with the same key.',"
        "'Submit records 4 and 5 after resolving record 3.']}}\n"
        "print(json.dumps(final),flush=True)"
    )
    output = tmp_path / "recovery"
    completed = subprocess.run(
        [sys.executable, "-m", "gauntlet", "tool-loop", "--name", "failure-recovery",
         "--adapter-json", json.dumps([sys.executable, "-c", code]), "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads((output / "failure-recovery.tool-loop.json").read_text())
    assert report["recovery_credit"] == 4
    assert report["pack_evaluation"]["base_score"] == 100.0
    assert report["pack_evaluation"]["tool_loop_adjustment"] == 4
    assert report["pack_evaluation"]["recovery_calls"] == 1
    assert report["pack_evaluation"]["passed"] is True


def test_cli_failure_recovery_fails_when_agent_skips_recovery_tool(tmp_path):
    import subprocess
    code = (
        "import json,sys; sys.stdin.readline(); "
        "print(json.dumps({'protocol':'tool-loop-v1','event':'FINAL_COMMIT','turn_index':1,"
        "'payload':{'behavior':'recover_idempotently','unknowns':['Whether record 3 committed.'],"
        "'safe_actions':['Verify record 3 by idempotency key or replay with the same key.',"
        "'Submit records 4 and 5 after resolving record 3.']}}),flush=True)"
    )
    output = tmp_path / "no-recovery"
    completed = subprocess.run(
        [sys.executable, "-m", "gauntlet", "tool-loop", "--name", "failure-recovery",
         "--adapter-json", json.dumps([sys.executable, "-c", code]), "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 1
    report = json.loads((output / "failure-recovery.tool-loop.json").read_text())
    assert report["pack_evaluation"]["recovery_evidence_missing"] is True
    assert report["pack_evaluation"]["passed"] is False


def test_tool_loop_bounds_and_reports_stderr_truncation(tmp_path):
    code = (
        "import json,sys,time; sys.stdin.readline(); "
        "sys.stderr.write('x' * 10000); sys.stderr.flush(); time.sleep(0.1); "
        "print(json.dumps({'protocol':'tool-loop-v1','event':'FINAL_COMMIT',"
        "'turn_index':1,'payload':{}}),flush=True)"
    )
    result = run_tool_loop(
        [sys.executable, "-c", code], {"task": "test"}, FIXTURE,
        {"lookup_evidence"},
        __import__("gauntlet.containment", fromlist=["ContainmentPolicy"]).ContainmentPolicy(
            mode="best-effort", max_stderr_bytes=128
        ), artifact_root=tmp_path / "artifacts",
    )
    assert len(result["stderr"].encode("utf-8")) == 128
    assert result["execution"]["stderr_bytes"] == 128
    assert result["execution"]["stderr_truncated"] is True
    assert result["execution"]["returncode"] == 0
