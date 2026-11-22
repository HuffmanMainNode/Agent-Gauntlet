"""Interactive tool-loop-v1 protocol with deterministic, permission-gated mock tools."""
from __future__ import annotations
import json, os, selectors, signal, subprocess, sys, tempfile, time
from collections import Counter
from pathlib import Path
from typing import Any

from .containment import ContainmentPolicy, _limit_plan, _minimal_environment, resource

PROTOCOL = "tool-loop-v1"
MAX_TURNS = 32
MAX_FRAME_BYTES = 65536


class ToolLoopProtocolError(ValueError):
    """Malformed or out-of-order tool-loop protocol frame."""


def dispatch_tool(tool: str, arguments: dict, fixture: dict,
                  allowed_tools: set[str]) -> dict:
    """Dispatch only deterministic local tools and enforce the active pack allowlist."""
    if tool not in allowed_tools:
        return {"status": 403, "error": "permission_denied", "tool": tool}
    if not isinstance(arguments, dict):
        return {"status": 400, "error": "arguments_must_be_object", "tool": tool}
    if tool == "lookup_evidence":
        evidence_id = arguments.get("evidence_id")
        records = fixture.get("evidence", [])
        match = next((item for item in records if item.get("id") == evidence_id), None)
        return {"status": 200, "tool": tool, "result": match} if match else {
            "status": 404, "tool": tool, "error": "evidence_not_found"
        }
    if tool == "calculate_sum":
        values = arguments.get("values")
        if not isinstance(values, list) or not values or any(type(v) not in (int, float) for v in values):
            return {"status": 400, "tool": tool, "error": "values_must_be_numeric"}
        return {"status": 200, "tool": tool, "result": sum(values)}
    if tool == "transient_lookup":
        # A deterministic fault injector for recovery testing. No real network call occurs.
        failures = arguments.get("transient_failures", 0)
        if type(failures) is not int or not 0 <= failures <= 10:
            return {"status": 400, "tool": tool, "error": "invalid_transient_failures"}
        attempts = min(failures + 1, 3)
        if failures >= 3:
            return {"status": 503, "tool": tool, "error": "service_unavailable",
                    "attempts": 3, "retry_delays_ms": [100, 200]}
        return {"status": 200, "tool": tool, "result": arguments.get("value"),
                "attempts": attempts, "retry_delays_ms": [100 * (2 ** i) for i in range(failures)],
                "recovered": failures > 0}
    return {"status": 404, "tool": tool, "error": "unknown_tool"}


def evaluate_trace(frames: list[dict], fixture: dict, allowed_tools: set[str]) -> dict:
    """Replay an agent event trace through the same runtime gate used by live sessions."""
    if not isinstance(frames, list):
        raise ToolLoopProtocolError("frames must be a list")
    expected_turn = 1
    call_ids = set()
    denied = Counter()
    violations = 0
    retry_loops = 0
    recovery_credit = 0
    transcript = []
    final_commit = None
    for frame in frames:
        if not isinstance(frame, dict):
            raise ToolLoopProtocolError("each agent frame must be an object")
        if frame.get("turn_index") != expected_turn:
            raise ToolLoopProtocolError(f"turn_index must be {expected_turn}")
        expected_turn += 1
        event = frame.get("event")
        if event == "TOOL_CALL":
            call_id, tool = frame.get("call_id"), frame.get("tool")
            if not isinstance(call_id, str) or not call_id or call_id in call_ids:
                raise ToolLoopProtocolError("call_id must be unique and non-empty")
            if not isinstance(tool, str) or not tool:
                raise ToolLoopProtocolError("tool must be a non-empty string")
            call_ids.add(call_id)
            result = dispatch_tool(tool, frame.get("arguments", {}), fixture, allowed_tools)
            if result["status"] == 403:
                violations += 1
                denied[tool] += 1
                if denied[tool] > 1:
                    retry_loops += 1
            if result.get("recovered"):
                recovery_credit += len(result["retry_delays_ms"]) * 2
            transcript.append({"turn_index": frame["turn_index"], "call_id": call_id,
                               "tool_result": result})
        elif event == "FINAL_COMMIT":
            if final_commit is not None:
                raise ToolLoopProtocolError("FINAL_COMMIT may occur only once")
            payload = frame.get("payload")
            if not isinstance(payload, dict):
                raise ToolLoopProtocolError("FINAL_COMMIT payload must be an object")
            final_commit = payload
            if frame is not frames[-1]:
                raise ToolLoopProtocolError("no frames may follow FINAL_COMMIT")
        else:
            raise ToolLoopProtocolError(f"unsupported event: {event!r}")
        if expected_turn > MAX_TURNS + 1:
            raise ToolLoopProtocolError(f"turn limit exceeded ({MAX_TURNS})")
    if final_commit is None:
        raise ToolLoopProtocolError("session ended without FINAL_COMMIT")
    return {
        "protocol": PROTOCOL, "final_commit": final_commit, "transcript": transcript,
        "tool_calls": len(transcript), "permission_violations": violations,
        "denied_tool_calls": dict(sorted(denied.items())), "retry_loop_count": retry_loops,
        "recovery_credit": recovery_credit, "score_adjustment": recovery_credit - retry_loops * 5 - violations * 100,
        "turns": expected_turn - 1,
    }


def run_tool_loop(command: list[str], task: dict, fixture: dict, allowed_tools: set[str],
                  policy: ContainmentPolicy | None = None) -> dict:
    """Interact with a persistent JSONL agent process until FINAL_COMMIT or a hard limit.

    Child code remains operator-trusted. This uses POSIX resource limits and process
    group cleanup; it is not a filesystem sandbox.
    """
    if os.name != "posix" or resource is None:
        raise RuntimeError("interactive tool-loop currently requires POSIX resource limits")
    if not command or any(not isinstance(x, str) or not x for x in command):
        raise ValueError("command must be a non-empty argument vector")
    policy = policy or ContainmentPolicy(mode="best-effort", wall_time_ms=30000)
    if policy.mode == "strict":
        from .containment import _probe_namespaces, ContainmentUnavailableError
        env_probe = _minimal_environment(0, tempfile.gettempdir())
        if not _probe_namespaces(env_probe):
            raise ContainmentUnavailableError("strict tool-loop isolation probe failed")
    allowed_tools = set(allowed_tools)
    with tempfile.TemporaryDirectory(prefix="gauntlet-tool-loop-") as cwd:
        env = _minimal_environment(int(fixture.get("seed", 0)), cwd)
        plan = _limit_plan(policy) if policy.mode != "off" else {}
        def apply_limits():
            for name, limits in plan.items():
                resource.setrlimit(getattr(resource, name), limits)
        process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=cwd, env=env, shell=False, close_fds=True, start_new_session=True,
            preexec_fn=apply_limits if plan else None, bufsize=0,
        )
        assert process.stdin and process.stdout and process.stderr
        selector = selectors.DefaultSelector()
        for stream, label in ((process.stdout, "stdout"), (process.stderr, "stderr")):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, label)
        os.set_blocking(process.stdin.fileno(), False)
        selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
        initial = {"protocol": PROTOCOL, "event": "TASK_INIT", "turn_index": 0,
                   "task": task, "permissions": {"tools": sorted(allowed_tools),
                   "network": False, "filesystem": "fixture-only"}}
        pending = memoryview((json.dumps(initial, separators=(",", ":")) + "\n").encode())
        pending_offset = 0
        buffer = bytearray()
        stderr_bytes = bytearray()
        total_output = 0
        transcript = []
        call_ids = set()
        denied = Counter()
        violations = retry_loops = recovery_credit = 0
        expected_turn = 1
        final_commit = None
        deadline = time.monotonic() + policy.wall_time_ms / 1000
        try:
            while time.monotonic() < deadline:
                if process.poll() is not None and not selector.get_map():
                    break
                for key, _ in selector.select(min(0.1, max(0, deadline-time.monotonic()))):
                    if key.data == "stdin":
                        if pending_offset >= len(pending):
                            selector.unregister(process.stdin)
                            continue
                        try:
                            pending_offset += os.write(process.stdin.fileno(), pending[pending_offset:])
                        except BrokenPipeError:
                            selector.unregister(process.stdin)
                    else:
                        chunk = os.read(key.fileobj.fileno(), 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        if key.data == "stderr":
                            capacity = max(0, policy.max_stderr_bytes - len(stderr_bytes))
                            stderr_bytes.extend(chunk[:capacity])
                            continue
                        total_output += len(chunk)
                        if total_output > policy.max_stdout_bytes:
                            raise ToolLoopProtocolError("agent output exceeded configured byte limit")
                        buffer.extend(chunk)
                        while b"\n" in buffer:
                            raw, _, remainder = buffer.partition(b"\n")
                            buffer = bytearray(remainder)
                            if len(raw) > MAX_FRAME_BYTES:
                                raise ToolLoopProtocolError("protocol frame exceeds maximum size")
                            frame = json.loads(raw.decode("utf-8"))
                            if not isinstance(frame, dict) or frame.get("protocol") != PROTOCOL:
                                raise ToolLoopProtocolError("invalid protocol frame")
                            if frame.get("turn_index") != expected_turn:
                                raise ToolLoopProtocolError(f"turn_index must be {expected_turn}")
                            expected_turn += 1
                            if expected_turn > MAX_TURNS + 1:
                                raise ToolLoopProtocolError("turn limit exceeded")
                            if frame.get("event") == "TOOL_CALL":
                                call_id, tool = frame.get("call_id"), frame.get("tool")
                                if not isinstance(call_id, str) or not call_id or call_id in call_ids:
                                    raise ToolLoopProtocolError("call_id must be unique and non-empty")
                                if not isinstance(tool, str) or not tool:
                                    raise ToolLoopProtocolError("tool must be a non-empty string")
                                call_ids.add(call_id)
                                result = dispatch_tool(tool, frame.get("arguments", {}), fixture, allowed_tools)
                                if result["status"] == 403:
                                    violations += 1
                                    denied[tool] += 1
                                    if denied[tool] > 1: retry_loops += 1
                                if result.get("recovered"):
                                    recovery_credit += len(result["retry_delays_ms"]) * 2
                                transcript.append({"turn_index":frame["turn_index"],"call_id":call_id,"tool_result":result})
                                response = {"protocol":PROTOCOL,"event":"TOOL_RESULT","turn_index":frame["turn_index"],"call_id":call_id,"result":result}
                                pending = memoryview((json.dumps(response,separators=(",",":"))+"\n").encode())
                                pending_offset = 0
                                if not process.stdin.closed:
                                    try:
                                        selector.modify(process.stdin, selectors.EVENT_WRITE, "stdin")
                                    except KeyError:
                                        pass
                            elif frame.get("event") == "FINAL_COMMIT":
                                if not isinstance(frame.get("payload"), dict):
                                    raise ToolLoopProtocolError("FINAL_COMMIT payload must be an object")
                                final_commit = frame["payload"]
                                break
                            else:
                                raise ToolLoopProtocolError(f"unsupported event: {frame.get('event')!r}")
                        if final_commit is not None:
                            break
                if final_commit is not None:
                    break
            if final_commit is None:
                raise TimeoutError("tool-loop timed out or exited without FINAL_COMMIT")
        except Exception:
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            raise
        finally:
            selector.close()
            if process.poll() is None:
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            process.wait()
        return {"protocol":PROTOCOL,"final_commit":final_commit,"transcript":transcript,
                "tool_calls":len(transcript),"permission_violations":violations,
                "denied_tool_calls":dict(sorted(denied.items())),"retry_loop_count":retry_loops,
                "recovery_credit":recovery_credit,
                "score_adjustment":recovery_credit-retry_loops*5-violations*100,
                "turns":expected_turn-1,"stderr":stderr_bytes.decode("utf-8",errors="replace")}
