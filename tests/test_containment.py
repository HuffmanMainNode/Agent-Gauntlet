import json
import os
import sys
import time

import pytest

from gauntlet import containment


@pytest.mark.skipif(os.name != "posix", reason="POSIX resource limits required")
def test_env_scrubbing(tmp_path, monkeypatch):
    monkeypatch.setenv("GAUNTLET_PARENT_SECRET", "must-not-leak")
    code = (
        "import json,os; print(json.dumps({'secret': os.getenv('GAUNTLET_PARENT_SECRET'), "
        "'seed': os.getenv('GAUNTLET_SEED')}))"
    )
    result = containment.run_contained(
        [sys.executable, "-c", code], b"", containment.ContainmentPolicy(mode="best-effort"),
        123, artifact_root=tmp_path,
    )
    payload = json.loads(result.stdout)
    assert payload["secret"] is None
    assert payload["seed"] == "123"


@pytest.mark.skipif(os.name != "posix", reason="POSIX process groups required")
def test_process_group_cleanup_on_timeout(tmp_path):
    marker = tmp_path / "grandchild.pid"
    code = (
        "import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c',"
        "'import time; time.sleep(30)']); "
        f"open({str(marker)!r},'w').write(str(p.pid)); time.sleep(30)"
    )
    result = containment.run_contained(
        [sys.executable, "-c", code], b"",
        containment.ContainmentPolicy(mode="best-effort", wall_time_ms=500),
        9, artifact_root=tmp_path,
    )
    assert result.timed_out
    pid = int(marker.read_text())
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        stat_path = f"/proc/{pid}/stat"
        stat = open(stat_path).read().split()[2] if os.path.exists(stat_path) else "Z"
        assert stat == "Z"


def test_bounded_output_truncation(tmp_path):
    code = "import sys; sys.stdout.buffer.write(b'x' * (5 * 1024 * 1024))"
    result = containment.run_contained(
        [sys.executable, "-c", code], b"",
        containment.ContainmentPolicy(mode="best-effort", max_stdout_bytes=4096),
        2, artifact_root=tmp_path,
    )
    assert len(result.stdout) == 4096
    assert result.output_truncated


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux RLIMIT_AS behavior")
def test_rlimit_enforcement(tmp_path):
    code = "x=bytearray(256 * 1024 * 1024)"
    policy = containment.ContainmentPolicy(
        mode="best-effort", max_memory_mb=64, wall_time_ms=5000,
        max_stdout_bytes=1024, max_stderr_bytes=4096,
    )
    result = containment.run_contained([sys.executable, "-c", code], b"", policy, 3,
                                       artifact_root=tmp_path)
    assert result.returncode != 0
    assert "RLIMIT_AS" in result.report.applied_limits


def test_strict_mode_fails_closed_when_unshare_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(containment, "_probe_namespaces", lambda env: False)
    with pytest.raises(containment.ContainmentUnavailableError):
        containment.run_contained(
            [sys.executable, "-c", "pass"], b"",
            containment.ContainmentPolicy(mode="strict"), 4, artifact_root=tmp_path,
        )
    assert not list(tmp_path.glob("*/containment.json"))


def test_report_never_claims_filesystem_sandbox(tmp_path):
    result = containment.run_contained(
        [sys.executable, "-c", "pass"], b"",
        containment.ContainmentPolicy(mode="best-effort"), 5, artifact_root=tmp_path,
    )
    serialized = json.loads(open(result.report_path, encoding="utf-8").read())
    assert serialized["filesystem_sandboxed"] is False
    assert result.report.to_dict()["filesystem_sandboxed"] is False


def test_off_mode_does_not_claim_resource_limits(tmp_path):
    result = containment.run_contained(
        [sys.executable, "-c", "pass"], b"",
        containment.ContainmentPolicy(mode="off"), 6, artifact_root=tmp_path,
    )
    assert result.report.effective_mode == "none"
    assert result.report.applied_limits == {}
