"""Command-line interface."""
import argparse
import json
from pathlib import Path

from .runner import run, verify


def main():
    parser = argparse.ArgumentParser(prog="agent-gauntlet")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run", help="run a bundled fixture agent")
    run_parser.add_argument("--challenge", required=True)
    run_parser.add_argument("--agent", required=True, choices=["demo-good", "demo-bad"])
    verify_parser = sub.add_parser("verify", help="verify an evidence bundle")
    verify_parser.add_argument("--bundle", required=True)
    args = parser.parse_args()
    try:
        if args.command == "run":
            path = run(args.challenge, args.agent)
            print(json.dumps({"bundle": str(path), "latest": str(path.parent / "LATEST")}, indent=2))
        else:
            target = Path(args.bundle)
            if str(target) == "artifacts/LATEST":
                target = Path("artifacts") / Path("artifacts/LATEST").read_text(encoding="utf-8").strip()
            print(json.dumps(verify(target), indent=2))
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(2, f"agent-gauntlet: error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
