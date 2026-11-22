"""Explicitly configured command adapter. The command is user-trusted code."""
from __future__ import annotations

import json

from .containment import ContainmentPolicy, run_contained


def _execute(command: list[str], wire_input: bytes, timeout_seconds: int, label: str) -> bytes:
    if not command or any(not isinstance(part, str) or not part for part in command):
        raise ValueError("Adapter command must be a non-empty argument list")
    if timeout_seconds < 1 or timeout_seconds > 300:
        raise ValueError("Timeout must be between 1 and 300 seconds")
    policy = ContainmentPolicy(
        mode="best-effort",
        cpu_seconds=max(1, timeout_seconds),
        wall_time_ms=timeout_seconds * 1000,
        max_stdout_bytes=1_048_576,
        max_stderr_bytes=1_048_576,
    )
    try:
        result = run_contained(command, wire_input, policy, seed=0)
    except OSError as exc:
        raise ValueError(f"{label} adapter could not be started: {exc}") from exc
    if result.timed_out:
        raise ValueError(f"{label} adapter timed out after {timeout_seconds} seconds")
    if result.output_truncated:
        raise ValueError(f"{label} adapter output exceeded the 1 MiB capture limit")
    if result.returncode != 0:
        diagnostic = result.stderr.decode("utf-8", errors="replace")[-2000:]
        raise ValueError(f"{label} adapter exited with code {result.returncode}: {diagnostic}")
    return result.stdout


def invoke_command(command: list[str], task: dict, timeout_seconds: int = 45) -> dict:
    stdout = _execute(
        command, json.dumps(task, separators=(",", ":")).encode("utf-8"),
        timeout_seconds, "Adapter",
    )
    try:
        response = json.loads(stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Adapter stdout must contain one JSON object") from exc
    if not isinstance(response, dict):
        raise ValueError("Adapter response must be a JSON object")
    return response


def invoke_session(command: list[str], frames: list[dict], timeout_seconds: int = 45) -> dict:
    """Run one persistent JSONL adapter process for a bounded sequence of turns."""
    if not isinstance(frames, list) or not frames or len(frames) > 20:
        raise ValueError("A session must contain between 1 and 20 frames")
    wire_input = "".join(
        json.dumps(frame, separators=(",", ":")) + "\n" for frame in frames
    ).encode("utf-8")
    stdout = _execute(command, wire_input, timeout_seconds, "Session")
    lines = [line for line in stdout.decode("utf-8").splitlines() if line.strip()]
    if len(lines) != len(frames):
        raise ValueError(f"Session adapter returned {len(lines)} frames; expected {len(frames)}")
    turns = []
    for index, line in enumerate(lines):
        try:
            frame = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Session adapter response {index} is not valid JSON") from exc
        if not isinstance(frame, dict):
            raise ValueError(f"Session adapter response {index} must be a JSON object")
        if frame.get("turn_index") != index:
            raise ValueError(f"Session adapter response {index} has an invalid turn_index")
        turns.append(frame)
    return {"turns": turns}
