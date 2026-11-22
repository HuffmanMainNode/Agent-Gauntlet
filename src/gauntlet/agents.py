"""Bundled deterministic fixture agents. Never loads participant-supplied code."""

def run_agent(agent_id: str, task: dict) -> dict:
    if agent_id == "demo-good":
        return {"findings": [{"id": "unsafe-eval", "path": "fixture/sample.py", "line": 4,
                              "claim": "Untrusted input is evaluated as Python code."}]}
    if agent_id == "demo-bad":
        return {"findings": [{"id": "made-up-finding", "path": "missing.py", "line": 99}]}
    raise ValueError(f"Unknown bundled agent: {agent_id}")
