import json
import sys
from pathlib import Path
import pytest
from gauntlet.pack_runner import load_pack
from gauntlet.tool_loop import (
    ToolLoopProtocolError, dispatch_tool, evaluate_trace, run_tool_loop,
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
    result=dispatch_tool("transient_lookup",{"value":"ready","transient_failures":2},FIXTURE,{"transient_lookup"})
    assert result["status"]==200 and result["recovered"]
    assert result["attempts"]==3
    assert result["retry_delays_ms"]==[100,200]
    trace=evaluate_trace([
        {"turn_index":1,"event":"TOOL_CALL","call_id":"r1","tool":"transient_lookup","arguments":{"value":"ready","transient_failures":2}},
        {"turn_index":2,"event":"FINAL_COMMIT","payload":{"status":"ready"}},
    ],FIXTURE,{"transient_lookup"})
    assert trace["recovery_credit"]==4

def test_retry_budget_is_bounded():
    result=dispatch_tool("transient_lookup",{"value":"never","transient_failures":3},FIXTURE,{"transient_lookup"})
    assert result["status"]==503 and result["attempts"]==3
    assert result["retry_delays_ms"]==[100,200]

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
    result=run_tool_loop([sys.executable,"-c",code],{"task":"test"},FIXTURE,{"lookup_evidence"})
    assert result["final_commit"]=={"seen":"E1"}
    assert result["tool_calls"]==1
    assert result["permission_violations"]==0

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
