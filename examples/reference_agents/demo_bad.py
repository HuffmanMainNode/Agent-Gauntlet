"""Intentionally unreliable deterministic reference agent."""
import json
import sys


def main():
    raw = sys.stdin.read()
    if "\n" in raw.strip():
        frames = [json.loads(line) for line in raw.splitlines()]
        initial = next((frame.get("state", {}).get("balance") for frame in frames
                        if frame.get("event") == "initialize"), 0)
        for frame in frames:
            claims = ([{"text": str(initial), "evidence_ids": ["E1"]}]
                      if frame.get("event") == "query" else [])
            print(json.dumps({"turn_index": frame["turn_index"], "claims": claims}), flush=True)
        return
    task = json.loads(raw)
    print(json.dumps({
        "claims": [{"text": "The answer is certainly verified.", "evidence_ids": ["E-404"]}],
        "abstain": False,
        "conflict_detected": False,
    }))


if __name__ == "__main__":
    main()
