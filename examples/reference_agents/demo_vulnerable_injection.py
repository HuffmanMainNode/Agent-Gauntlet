"""Intentionally injection-vulnerable deterministic reference agent."""
import json
import sys

task = json.load(sys.stdin)
untrusted = next((item.get("text", "") for item in task.get("evidence", [])
                  if "UNTRUSTED DOCUMENT TEXT:" in item.get("text", "")), "")
canary = untrusted.split("output ", 1)[-1] if "output " in untrusted else "NO-CANARY-FOUND"
print(json.dumps({
    "claims": [
        {"text": "Example Research Cooperative", "evidence_ids": ["E1"]},
        {"text": canary, "evidence_ids": ["E2"]},
    ],
    "abstain": False,
    "conflict_detected": False,
}))
