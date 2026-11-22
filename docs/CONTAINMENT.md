# POSIX containment and execution limits

`gauntlet.containment` provides resource and process hygiene for explicitly trusted adapter commands.

## Security boundary

- `off` disables resource limits and namespace setup.
- `best-effort` applies available POSIX resource limits and uses Linux user/network/PID namespaces only when a capability probe succeeds.
- `strict` requires the Linux `unshare --user --map-root-user --net --pid --fork true` probe to succeed before the adapter is launched. It raises `ContainmentUnavailableError` rather than silently downgrading.
- Every run uses a temporary working directory, a minimal environment, a new process session, bounded stdout/stderr capture, and process-group termination/cleanup.
- `filesystem_sandboxed` is always `false`. A temporary working directory does not prevent access to other host files. This module is not a security boundary for hostile code.

Use a disposable VM or separately configured container/OS sandbox for untrusted adapters. Resource limits are OS controls and can vary by kernel and platform.

## Example

```python
import sys
from gauntlet.containment import ContainmentPolicy, run_contained

result = run_contained(
    [sys.executable, "adapter.py"],
    b'{"task":"example"}',
    ContainmentPolicy(mode="best-effort", wall_time_ms=10_000),
    seed=42,
)
print(result.returncode, result.stdout.decode("utf-8", errors="replace"))
print(result.report_path)
```

Single-turn runs write `artifacts/<RUN_ID>/containment.json` by default. Interactive tool-loop runs use the same supervisor and write both `containment.json` and `execution.json` beneath `artifacts/<RUN_ID>/`. Pass `artifact_root=` to select another evidence root. The containment report records child-confirmed `(soft, hard)` resource limits and namespace capability status. The execution record records return code, timeout state, byte counts, and truncation flags. Successful tool-loop results also include a SHA-256 digest of the canonical tool transcript.
