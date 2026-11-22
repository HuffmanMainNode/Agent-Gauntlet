"""Interactive tool-loop-v1 protocol with deterministic, permission-gated mock tools."""
from __future__ import annotations
import hashlib, json, os, selectors, signal, sys, tempfile, time, uuid
from collections import Counter
from pathlib import Path
from typing import Any

from .containment import (ContainmentPolicy, ContainmentUnavailableError,
                          spawn_contained_process, finish_process_group, resource)

PROTOCOL = "tool-loop-v1"
MAX_TURNS = 32
MAX_FRAME_BYTES = 65536


class ToolLoopProtocolError(ValueError):
    """Malformed or out-of-order tool-loop protocol frame."""


class ToolDispatcher:
    """Stateful deterministic tool dispatcher with fixture-controlled fault injection."""

    def __init__(self, fixture: dict, allowed_tools: set[str]):
        self.fixture = fixture
        self.allowed_tools = set(allowed_tools)
        self.attempts: Counter[str] = Counter()
        self.completed: dict[str, Any] = {}
        self.exhausted: set[str] = set()

    def dispatch(self, tool: str, arguments: dict) -> dict:
        if tool not in self.allowed_tools:
            return {"status": 403, "error": "permission_denied", "tool": tool}
        if not isinstance(arguments, dict):
            return {"status": 400, "error": "arguments_must_be_object", "tool": tool}
        if tool == "lookup_evidence":
            evidence_id = arguments.get("evidence_id")
            records = self.fixture.get("evidence", [])
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
            tool_faults = self.fixture.get("tool_faults", {})
            if not isinstance(tool_faults, dict):
                return {"status": 500, "tool": tool, "error": "invalid_fixture_fault_configuration"}
            fault = tool_faults.get("transient_lookup", {})
            if not isinstance(fault, dict):
                return {"status": 500, "tool": tool, "error": "invalid_fixture_fault_configuration"}
            operation_id = arguments.get("operation_id")
            if not isinstance(operation_id, str) or operation_id != fault.get("operation_id"):
                return {"status": 404, "tool": tool, "error": "operation_not_found"}
            if operation_id in self.completed:
                return {"status": 200, "tool": tool, "result": self.completed[operation_id],
                        "duplicate": True, "recovered": False}
            failures = fault.get("failures", 0)
            max_retries = fault.get("max_retries", 2)
            if (type(failures) is not int or not 0 <= failures <= 10
                    or type(max_retries) is not int or not 0 <= max_retries <= 5):
                return {"status": 500, "tool": tool, "error": "invalid_fixture_fault_configuration"}
            attempt = self.attempts[operation_id] + 1
            self.attempts[operation_id] = attempt
            if attempt <= failures:
                exhausted = attempt > max_retries
                return {
                    "status": 503, "tool": tool, "error": (
                        "retry_budget_exhausted" if exhausted else "service_unavailable"
                    ),
                    "operation_id": operation_id, "attempt": attempt,
                    "max_retries": max_retries,
                    "retry_after_ms": 100 * (2 ** min(attempt - 1, max_retries)),
                    "retry_budget_exhausted": exhausted,
                }
            if attempt > max_retries + 1:
                return {"status": 503, "tool": tool, "error": "retry_budget_exhausted",
                        "operation_id": operation_id, "attempt": attempt,
                        "max_retries": max_retries, "retry_budget_exhausted": True}
            value = fault.get("value")
            self.completed[operation_id] = value
            retries = attempt - 1
            return {
                "status": 200, "tool": tool, "result": value, "operation_id": operation_id,
                "attempts": attempt, "recovered": retries > 0,
                "retry_delays_ms": [100 * (2 ** index) for index in range(retries)],
            }
        return {"status": 404, "tool": tool, "error": "unknown_tool"}

    def unresolved_operations(self) -> list[str]:
        return sorted(set(self.attempts) - set(self.completed))


def dispatch_tool(tool: str, arguments: dict, fixture: dict,
                  allowed_tools: set[str]) -> dict:
    """Single-call convenience wrapper; stateful retries use ToolDispatcher."""
    return ToolDispatcher(fixture, allowed_tools).dispatch(tool, arguments)


def evaluate_trace(frames: list[dict], fixture: dict, allowed_tools: set[str]) -> dict:
    """Replay an agent event trace through the same runtime gate used by live sessions."""
    if not isinstance(frames, list):
        raise ToolLoopProtocolError("frames must be a list")
    expected_turn = 1
    dispatcher = ToolDispatcher(fixture, allowed_tools)
    call_ids = set()
    denied = Counter()
    violations = 0
    retry_loops = 0
    recovery_credit = 0
    service_unavailable = Counter()
    transcript = []
    final_commit = None
    for frame in frames:
        if not isinstance(frame, dict):
            raise ToolLoopProtocolError("each agent frame must be an object")
        if type(frame.get("turn_index")) is not int or frame.get("turn_index") != expected_turn:
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
            result = dispatcher.dispatch(tool, frame.get("arguments", {}))
            if result["status"] == 503:
                service_unavailable[tool] += 1
                if result.get("retry_budget_exhausted") and result.get("operation_id") not in dispatcher.exhausted:
                    retry_loops += 1
                    dispatcher.exhausted.add(result["operation_id"])
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
        "recovery_credit": recovery_credit, "unrecovered_operations": dispatcher.unresolved_operations(),
        "score_adjustment": recovery_credit - retry_loops * 5 - violations * 100 - len(dispatcher.unresolved_operations()) * 10,
        "turns": expected_turn - 1,
    }


def run_tool_loop(command: list[str], task: dict, fixture: dict, allowed_tools: set[str],
                  policy: ContainmentPolicy | None = None,
                  artifact_root: str | Path = "artifacts") -> dict:
    """Interact with a persistent JSONL agent process until FINAL_COMMIT or a hard limit.

    Child code remains operator-trusted. This uses POSIX resource limits and process
    group cleanup; it is not a filesystem sandbox.
    """
    if os.name != "posix" or resource is None:
        raise RuntimeError("interactive tool-loop currently requires POSIX resource limits")
    if not command or any(not isinstance(x, str) or not x for x in command):
        raise ValueError("command must be a non-empty argument vector")
    policy = policy or ContainmentPolicy(mode="best-effort", wall_time_ms=30000)
    if policy.mode == "strict" and not policy.disable_network:
        raise ValueError("strict mode requires disable_network=True")
    allowed_tools = set(allowed_tools)
    run_id = uuid.uuid4().hex
    containment_path = Path(artifact_root) / run_id / "containment.json"
    with tempfile.TemporaryDirectory(prefix="gauntlet-tool-loop-") as cwd:
        process, containment_report = spawn_contained_process(
            command, policy, int(fixture.get("seed", 0)), cwd
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
        stderr_truncated = False
        total_output = 0
        stdout_truncated = False
        transcript = []
        call_ids = set()
        denied = Counter()
        violations = retry_loops = recovery_credit = 0
        service_unavailable = Counter()
        dispatcher = ToolDispatcher(fixture, allowed_tools)
        expected_turn = 1
        final_commit = None
        timed_out = False
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
                            if len(chunk) > capacity:
                                stderr_truncated = True
                            continue
                        capacity = max(0, policy.max_stdout_bytes - total_output)
                        if len(chunk) > capacity:
                            stdout_truncated = True
                            raise ToolLoopProtocolError("agent output exceeded configured byte limit")
                        total_output += len(chunk)
                        buffer.extend(chunk)
                        while b"\n" in buffer:
                            raw, _, remainder = buffer.partition(b"\n")
                            buffer = bytearray(remainder)
                            if len(raw) > MAX_FRAME_BYTES:
                                raise ToolLoopProtocolError("protocol frame exceeds maximum size")
                            if buffer:
                                raise ToolLoopProtocolError("agent emitted multiple frames before receiving the pending tool result")
                            frame = json.loads(raw.decode("utf-8"))
                            if not isinstance(frame, dict) or frame.get("protocol") != PROTOCOL:
                                raise ToolLoopProtocolError("invalid protocol frame")
                            if type(frame.get("turn_index")) is not int or frame.get("turn_index") != expected_turn:
                                raise ToolLoopProtocolError(f"turn_index must be integer {expected_turn}")
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
                                result = dispatcher.dispatch(tool, frame.get("arguments", {}))
                                if result["status"] == 503:
                                    service_unavailable[tool] += 1
                                    if result.get("retry_budget_exhausted") and result.get("operation_id") not in dispatcher.exhausted:
                                        retry_loops += 1
                                        dispatcher.exhausted.add(result["operation_id"])
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
                                        selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
                            elif frame.get("event") == "FINAL_COMMIT":
                                if not isinstance(frame.get("payload"), dict):
                                    raise ToolLoopProtocolError("FINAL_COMMIT payload must be an object")
                                if buffer:
                                    raise ToolLoopProtocolError("frames may not follow FINAL_COMMIT")
                                final_commit = frame["payload"]
                                break
                            else:
                                raise ToolLoopProtocolError(f"unsupported event: {frame.get('event')!r}")
                        if final_commit is not None:
                            break
                if final_commit is not None:
                    break
            if final_commit is None:
                timed_out = time.monotonic() >= deadline
                raise TimeoutError("tool-loop timed out or exited without FINAL_COMMIT")
        except Exception:
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            raise
        finally:
            selector.close()
            returncode = finish_process_group(process)
            transcript_bytes = json.dumps(
            transcript, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return {"protocol":PROTOCOL,"final_commit":final_commit,"transcript":transcript,
                "tool_calls":len(transcript),"permission_violations":violations,
                "denied_tool_calls":dict(sorted(denied.items())),"retry_loop_count":retry_loops,
                "recovery_credit":recovery_credit,"unrecovered_operations":dispatcher.unresolved_operations(),
                "score_adjustment":recovery_credit-retry_loops*5-violations*100-len(dispatcher.unresolved_operations())*10,
                "turns":expected_turn-1,"stderr":stderr_bytes.decode("utf-8",errors="replace"),
                "execution": {"returncode": returncode, "timed_out": timed_out,
                              "stdout_bytes": total_output, "stderr_bytes": len(stderr_bytes),
                              "stdout_truncated": stdout_truncated,
                              "stderr_truncated": stderr_truncated},
                "transcript_sha256": hashlib.sha256(transcript_bytes).hexdigest(),
                "run_id": run_id, "containment_report_path": str(containment_path),
                "containment": containment_report.to_dict()}
