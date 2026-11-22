"""Command-line interface."""
import argparse
import json
from pathlib import Path

from .adversarial_runner import run_suite
from .runner import run, verify


def main():
    parser = argparse.ArgumentParser(prog="agent-gauntlet")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run", help="run a bundled fixture agent")
    run_parser.add_argument("--challenge", required=True)
    run_parser.add_argument("--agent", required=True, choices=["demo-good", "demo-bad"])
    verify_parser = sub.add_parser("verify", help="verify an evidence bundle")
    verify_parser.add_argument("--bundle", required=True)
    adv = sub.add_parser("adversarial", help="run a seeded adversarial suite using an explicitly trusted adapter command")
    adv.add_argument("--suite", required=True, choices=["hallucination", "contradiction", "injection", "variable", "ambiguity"])
    adv.add_argument("--adapter-json", required=True, help='JSON argument array, e.g. ["python","my_adapter.py"]')
    adv.add_argument("--seeds", default="1,2,3", help="comma-separated integer seeds; maximum 100")
    adv.add_argument("--output", default="artifacts/adversarial")
    adv.add_argument("--timeout", type=int, default=45)
    args = parser.parse_args()
    try:
        if args.command == "run":
            path = run(args.challenge, args.agent)
            print(json.dumps({"bundle": str(path), "latest": str(path.parent / "LATEST")}, indent=2))
        elif args.command == "verify":
            target = Path(args.bundle)
            if str(target) == "artifacts/LATEST":
                target = Path("artifacts") / Path("artifacts/LATEST").read_text(encoding="utf-8").strip()
            print(json.dumps(verify(target), indent=2))
        else:
            command = json.loads(args.adapter_json)
            if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
                raise ValueError("--adapter-json must be a JSON array of strings")
            seeds = [int(value.strip()) for value in args.seeds.split(",") if value.strip()]
            path = run_suite(args.suite, command, seeds, Path(args.output), args.timeout)
            print(json.dumps({"bundle": str(path)}, indent=2))
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(2, f"agent-gauntlet: error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
