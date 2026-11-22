"""POSIX resource hardening for explicitly trusted adapter commands.

This module is not a filesystem sandbox. Use a dedicated VM/container for hostile code.
"""
from __future__ import annotations

import json
import os
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

try:
    import resource
except ImportError:  # pragma: no cover
    resource = None  # type: ignore[assignment]

ContainmentMode = Literal["off", "best-effort", "strict"]
EffectiveMode = Literal["none", "rlimit_only", "rlimit_and_user_net_pid_ns"]


class ContainmentUnavailableError(RuntimeError):
    """Raised when requested strict containment capabilities are unavailable."""


@dataclass(frozen=True)
class ContainmentPolicy:
    mode: ContainmentMode = "best-effort"
    cpu_seconds: int = 30
    max_memory_mb: int = 512
    max_file_bytes: int = 16 * 1024 * 1024
    max_open_files: int = 64
    wall_time_ms: int = 30_000
    max_stdout_bytes: int = 1_048_576
    max_stderr_bytes: int = 1_048_576
    disable_network: bool = True

    def __post_init__(self) -> None:
        if self.mode not in {"off", "best-effort", "strict"}:
            raise ValueError("mode must be off, best-effort, or strict")
        for name in ("cpu_seconds", "max_memory_mb", "max_file_bytes",
                     "max_open_files", "wall_time_ms"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")
        for name in ("max_stdout_bytes", "max_stderr_bytes"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if type(self.disable_network) is not bool:
            raise ValueError("disable_network must be a boolean")


@dataclass
class ContainmentReport:
    requested_mode: str
    effective_mode: EffectiveMode
    applied_limits: dict[str, tuple[int, int]] = field(default_factory=dict)
    namespaces_active: dict[str, bool] = field(
        default_factory=lambda: {"user": False, "net": False, "pid": False}
    )
    filesystem_sandboxed: bool = False
    host_os: str = sys.platform

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["applied_limits"] = {
            name: [soft, hard] for name, (soft, hard) in sorted(self.applied_limits.items())
        }
        payload["filesystem_sandboxed"] = False
        return payload


@dataclass
class ExecutionResult:
    argv: list[str]
    returncode: int | None
    stdout: bytes
    stderr: bytes
    timed_out: bool
    output_truncated: bool
    duration_ms: int
    seed: int
    report: ContainmentReport
    run_id: str
    report_path: str


def _minimal_environment(seed: int, temp_dir: str) -> dict[str, str]:
    lang = os.environ.get("LANG", "C.UTF-8")
    return {
        "PATH": os.environ.get("PATH", os.defpath),
        "LANG": lang,
        "LC_ALL": lang,
        "TMPDIR": temp_dir,
        "GAUNTLET_SEED": str(seed),
    }


def _probe_namespaces(env: dict[str, str]) -> bool:
    if sys.platform != "linux" or shutil.which("unshare", path=env.get("PATH")) is None:
        return False
    command = ["unshare", "--user", "--map-root-user", "--net", "--pid", "--fork", "true"]
    try:
        result = subprocess.run(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, env=env, timeout=5, check=False,
            close_fds=True, shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _limit_plan(policy: ContainmentPolicy) -> dict[str, tuple[int, int]]:
    if resource is None:
        raise ContainmentUnavailableError("POSIX resource limits are unavailable")
    requested = {
        "RLIMIT_CPU": (resource.RLIMIT_CPU, policy.cpu_seconds, policy.cpu_seconds + 1),
        "RLIMIT_AS": (getattr(resource, "RLIMIT_AS", None),
                      policy.max_memory_mb * 1024 * 1024, policy.max_memory_mb * 1024 * 1024),
        "RLIMIT_FSIZE": (resource.RLIMIT_FSIZE, policy.max_file_bytes, policy.max_file_bytes),
        "RLIMIT_NOFILE": (resource.RLIMIT_NOFILE, policy.max_open_files, policy.max_open_files),
        "RLIMIT_CORE": (resource.RLIMIT_CORE, 0, 0),
    }
    plan: dict[str, tuple[int, int]] = {}
    for name, (kind, soft, hard) in requested.items():
        if kind is None:
            continue
        _, inherited_hard = resource.getrlimit(kind)
        if inherited_hard != resource.RLIM_INFINITY:
            soft, hard = min(soft, inherited_hard), min(hard, inherited_hard)
        plan[name] = (soft, hard)
    return plan


def _apply_limits_in_child(plan: dict[str, tuple[int, int]], report_fd: int) -> None:
    confirmed: dict[str, tuple[int, int]] = {}
    try:
        for name, limits in plan.items():
            kind = getattr(resource, name)
            resource.setrlimit(kind, limits)
            actual = resource.getrlimit(kind)
            confirmed[name] = (int(actual[0]), int(actual[1]))
        os.write(report_fd, json.dumps(confirmed, sort_keys=True).encode("ascii"))
    finally:
        os.close(report_fd)



def spawn_contained_process(
    argv: list[str], policy: ContainmentPolicy, seed: int, cwd: str | Path,
) -> tuple[subprocess.Popen, ContainmentReport]:
    """Start one child under the shared POSIX execution policy.

    Both one-shot adapters and interactive tool-loop sessions use this function,
    so namespace probing, environment scrubbing, confirmed rlimits, and process
    group creation cannot silently diverge.
    """
    if not argv or any(not isinstance(arg, str) or not arg for arg in argv):
        raise ValueError("argv must be a non-empty list of non-empty strings")
    if type(seed) is not int:
        raise TypeError("seed must be an integer")
    if policy.mode == "strict" and not policy.disable_network:
        raise ValueError("strict mode requires disable_network=True")

    working_dir = str(Path(cwd).resolve())
    env = _minimal_environment(seed, working_dir)
    namespaces = (
        _probe_namespaces(env)
        if policy.mode != "off" and policy.disable_network else False
    )
    if policy.mode == "strict" and not namespaces:
        raise ContainmentUnavailableError(
            "Strict containment unavailable: Linux unshare user/net/PID namespace probe failed"
        )

    report = ContainmentReport(requested_mode=policy.mode, effective_mode="none")
    if namespaces:
        report.namespaces_active = {"user": True, "net": True, "pid": True}
        report.effective_mode = "rlimit_and_user_net_pid_ns"
    elif policy.mode != "off":
        if resource is None or os.name != "posix":
            if policy.mode == "strict":
                raise ContainmentUnavailableError("POSIX resource limits are unavailable")
        else:
            report.effective_mode = "rlimit_only"

    command = list(argv)
    if namespaces:
        command = [
            "unshare", "--user", "--map-root-user", "--net", "--pid", "--fork", "--", *argv
        ]

    plan = _limit_plan(policy) if policy.mode != "off" and resource is not None and os.name == "posix" else {}
    report_read = report_write = None
    preexec_fn = None
    pass_fds: tuple[int, ...] = ()
    if plan:
        report_read, report_write = os.pipe()
        preexec_fn = lambda: _apply_limits_in_child(plan, report_write)
        pass_fds = (report_write,)

    try:
        process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=working_dir, env=env, shell=False, close_fds=True,
            start_new_session=True, preexec_fn=preexec_fn, pass_fds=pass_fds, bufsize=0,
        )
    except BaseException:
        if report_read is not None:
            os.close(report_read)
        if report_write is not None:
            os.close(report_write)
        raise

    if report_write is not None:
        os.close(report_write)
        report_write = None
        try:
            with os.fdopen(report_read, "rb") as handle:
                raw = handle.read(8192)
            if not raw:
                _kill_process_group(process)
                process.wait()
                raise ContainmentUnavailableError("Child did not confirm applied resource limits")
            confirmed = json.loads(raw.decode("ascii"))
            report.applied_limits = {
                name: (int(values[0]), int(values[1]))
                for name, values in confirmed.items()
            }
            if set(report.applied_limits) != set(plan):
                _kill_process_group(process)
                process.wait()
                raise ContainmentUnavailableError("Child confirmed an incomplete resource limit set")
        except BaseException:
            if process.poll() is None:
                _kill_process_group(process)
                process.wait()
            raise
    return process, report


def _kill_process_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        process.kill()



def terminate_process_group(process: subprocess.Popen, timeout: float = 2.0) -> int:
    """Kill every remaining process in the child's session and reap its leader."""
    _kill_process_group(process)
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_process_group(process)
        return process.wait(timeout=timeout)



def finish_process_group(process: subprocess.Popen, grace_seconds: float = 0.25) -> int:
    """Close the request stream, allow a clean leader exit, then reap its group."""
    if process.stdin is not None and not process.stdin.closed:
        process.stdin.close()
    try:
        returncode = process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        _kill_process_group(process)
        returncode = process.wait()
    # The leader may have exited while descendants kept its session alive.
    _kill_process_group(process)
    return returncode


def _capture_process(process: subprocess.Popen, stdin_bytes: bytes,
                     policy: ContainmentPolicy, deadline: float) -> tuple[bytes, bytes, bool, bool]:
    assert process.stdout is not None and process.stderr is not None and process.stdin is not None
    selector = selectors.DefaultSelector()
    streams = {
        "stdout": [bytearray(), policy.max_stdout_bytes, process.stdout],
        "stderr": [bytearray(), policy.max_stderr_bytes, process.stderr],
    }
    for name, (_, _, stream) in streams.items():
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ, name)
    os.set_blocking(process.stdin.fileno(), False)
    selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
    input_view = memoryview(stdin_bytes)
    input_offset = 0
    input_open = True
    truncated = False
    timed_out = False
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            events = selector.select(min(remaining, 0.1))
            for key, _ in events:
                if key.data == "stdin":
                    if input_offset >= len(input_view):
                        selector.unregister(process.stdin)
                        process.stdin.close()
                        input_open = False
                        continue
                    try:
                        written = os.write(
                            process.stdin.fileno(), input_view[input_offset:input_offset + 65536]
                        )
                        input_offset += written
                    except BrokenPipeError:
                        selector.unregister(process.stdin)
                        process.stdin.close()
                        input_open = False
                else:
                    name = key.data
                    target, limit, stream = streams[name]
                    try:
                        chunk = os.read(stream.fileno(), 65536)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(stream)
                        stream.close()
                        continue
                    capacity = max(0, limit - len(target))
                    if capacity:
                        target.extend(chunk[:capacity])
                    if len(chunk) > capacity:
                        truncated = True
        return bytes(streams["stdout"][0]), bytes(streams["stderr"][0]), truncated, timed_out
    finally:
        selector.close()
        if input_open and not process.stdin.closed:
            process.stdin.close()


def run_contained(argv: list[str], stdin_bytes: bytes, policy: ContainmentPolicy,
                  seed: int, *, artifact_root: str | Path = "artifacts") -> ExecutionResult:
    """Run an explicitly trusted adapter with resource and process hygiene.

    Strict mode requires Linux user/network/PID namespaces. No mode provides a
    filesystem sandbox; do not use this as isolation for hostile code.
    """
    if not argv or any(not isinstance(arg, str) or not arg for arg in argv):
        raise ValueError("argv must be a non-empty list of non-empty strings")
    if not isinstance(stdin_bytes, bytes):
        raise TypeError("stdin_bytes must be bytes")
    if type(seed) is not int:
        raise TypeError("seed must be an integer")
    if policy.mode == "strict" and not policy.disable_network:
        raise ValueError("strict mode requires disable_network=True")

    run_id = uuid.uuid4().hex
    report_path = Path(artifact_root) / run_id / "containment.json"
    started = time.monotonic()
    report = ContainmentReport(requested_mode=policy.mode, effective_mode="none")

    with tempfile.TemporaryDirectory(prefix="gauntlet-") as temp_dir:
        process, report = spawn_contained_process(argv, policy, seed, temp_dir)
        timed_out = truncated = False
        stdout = stderr = b""
        returncode: int | None = None
        try:
            stdout, stderr, truncated, timed_out = _capture_process(
                process, stdin_bytes, policy, started + policy.wall_time_ms / 1000
            )
        finally:
            returncode = terminate_process_group(process)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report.to_dict(), sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )

    return ExecutionResult(
        argv=list(argv), returncode=returncode, stdout=stdout, stderr=stderr,
        timed_out=timed_out, output_truncated=truncated,
        duration_ms=int((time.monotonic() - started) * 1000), seed=seed,
        report=report, run_id=run_id, report_path=str(report_path),
    )
