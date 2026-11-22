"""Intentionally stale-state deterministic reference agent."""
import json
import sys

frames = [json.loads(line) for line in sys.stdin]
initial = next((frame.get("state", {}).get("balance") for frame in frames
                if frame.get("event") == "initialize"), 0)
for frame in frames:
    claims = ([{"text": str(initial), "evidence_ids": ["E1"]}]
              if frame.get("event") == "query" else [])
    print(json.dumps({"turn_index": frame["turn_index"], "claims": claims}), flush=True)
