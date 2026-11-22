"""Explicitly configured command adapter. The command is user-trusted code."""
from __future__ import annotations

import json
import os
import subprocess


def invoke_command(command: list[str], task: dict, timeout_seconds: int = 45) -> dict:
    if not command or any(not isinstance(part, str) or not part for part in command):
        raise ValueError("Adapter command must be a non-empty argument list")
    if timeout_seconds < 1 or timeout_seconds > 300:
        raise ValueError("Timeout must be between 1 and 300 seconds")
    env = {"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8", "PYTHONIOENCODING": "utf-8"}
    try:
        completed = subprocess.run(
            command, input=json.dumps(task), text=True, capture_output=True,
            timeout=timeout_seconds, check=False, shell=False, env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"Adapter timed out after {timeout_seconds} seconds") from exc
    if completed.returncode != 0:
        raise ValueError(f"Adapter exited with code {completed.returncode}: {completed.stderr[-2000:]}")
    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("Adapter stdout must contain one JSON object") from exc
    if not isinstance(response, dict):
        raise ValueError("Adapter response must be a JSON object")
    return response
