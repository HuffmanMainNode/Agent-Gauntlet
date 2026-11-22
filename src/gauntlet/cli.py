"""Command-line interface."""
import argparse
import json
from pathlib import Path

from .adversarial_runner import run_suite
from .leaderboard import build_scorecard, verify_scorecard, write_scorecard
from .runner import run, verify
from .pack_runner import discover_pack_ids, evaluate_response_file, evaluate_response, load_pack
from .tool_loop import run_tool_loop
from .containment import ContainmentPolicy


def main():
    parser = argparse.ArgumentParser(prog="agent-gauntlet")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run", help="run a bundled fixture agent")
    run_parser.add_argument("--challenge", required=True)
    run_parser.add_argument("--agent", required=True, choices=["demo-good", "demo-bad"])
    verify_parser = sub.add_parser("verify", help="verify an evidence bundle")
    verify_parser.add_argument("--bundle", required=True)
    adv = sub.add_parser("adversarial", help="run a seeded adversarial suite using an explicitly trusted adapter command")
    adv.add_argument("--suite", required=True, choices=["hallucination", "contradiction", "injection", "variable", "ambiguity", "stateful"])
    adv.add_argument("--adapter-json", required=True, help='JSON argument array, e.g. ["python","my_adapter.py"]')
    adv.add_argument("--seeds", default="1,2,3", help="comma-separated integer seeds; maximum 100")
    adv.add_argument("--output", default="artifacts/adversarial")
    adv.add_argument("--timeout", type=int, default=45)
    adv.add_argument("--protocol", choices=["single-turn", "jsonl-session"], default="single-turn")
    adv.add_argument("--agent-name", required=True)
    adv.add_argument("--model-id", required=True)
    adv.add_argument("--adapter-version", required=True)
    adv.add_argument("--operator", default="unspecified")
    pack = sub.add_parser("pack", help="evaluate a data-only challenge pack response")
    pack.add_argument("--name", help="challenge pack identifier")
    pack.add_argument("--all", action="store_true", help="evaluate every discovered challenge pack")
    pack.add_argument("--response", help="JSON response file for one pack")
    pack.add_argument("--responses-dir", default="responses", help="directory containing <pack-id>.json responses for --all")
    pack.add_argument("--output", default="artifacts/packs", help="directory for evaluation reports")
    tool_loop = sub.add_parser("tool-loop", help="run an interactive tool-loop-v1 pack session")
    tool_loop.add_argument("--name", required=True, help="challenge pack identifier")
    tool_loop.add_argument("--adapter-json", required=True, help="JSON argument array for a trusted local agent")
    tool_loop.add_argument("--timeout", type=int, default=30)
    tool_loop.add_argument("--output", default="artifacts/tool-loop")
    card = sub.add_parser("scorecard", help="build a public scorecard from verified adversarial evidence bundles")
    card.add_argument("--bundle", action="append", required=True, help="evidence bundle directory; repeat for each suite")
    card.add_argument("--agent-name", required=True)
    card.add_argument("--model-id", required=True)
    card.add_argument("--adapter-version", required=True)
    card.add_argument("--operator", default="unspecified")
    card.add_argument("--output", default="scorecard.json")
    card_verify = sub.add_parser("verify-scorecard", help="verify a scorecard's self-integrity digest")
    card_verify.add_argument("--scorecard", required=True)
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
        elif args.command == "adversarial":
            command = json.loads(args.adapter_json)
            if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
                raise ValueError("--adapter-json must be a JSON array of strings")
            seeds = [int(value.strip()) for value in args.seeds.split(",") if value.strip()]
            path = run_suite(args.suite, command, seeds, Path(args.output), args.timeout,
                             args.agent_name, args.model_id, args.adapter_version, args.operator, args.protocol)
            print(json.dumps({"bundle": str(path)}, indent=2))
        elif args.command == "pack":
            if args.all == bool(args.name):
                raise ValueError("choose exactly one of --name or --all")
            if args.all and args.response:
                raise ValueError("--response cannot be combined with --all")
            if args.name and not args.response:
                raise ValueError("--response is required with --name")
            ids = discover_pack_ids() if args.all else [args.name]
            output = Path(args.output)
            results = []
            missing = []
            for pack_id in ids:
                response_path = Path(args.responses_dir) / f"{pack_id}.json" if args.all else Path(args.response)
                if not response_path.is_file():
                    missing.append(pack_id)
                    continue
                result = evaluate_response_file(load_pack(pack_id), response_path)
                output.mkdir(parents=True, exist_ok=True)
                (output / f"{pack_id}.result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
                results.append(result)
            summary = {"evaluated": len(results), "missing_responses": missing, "passed": sum(1 for item in results if item["passed"]), "failed": sum(1 for item in results if not item["passed"]), "results": results}
            print(json.dumps(summary, indent=2))
            if missing or any(not item["passed"] for item in results):
                return 1
        elif args.command == "tool-loop":
            command = json.loads(args.adapter_json)
            if not isinstance(command, list) or not command or not all(isinstance(part, str) and part for part in command):
                raise ValueError("--adapter-json must be a non-empty JSON array of strings")
            if not 1 <= args.timeout <= 300:
                raise ValueError("--timeout must be between 1 and 300 seconds")
            challenge = load_pack(args.name)
            permissions = challenge.manifest["permissions"]
            result = run_tool_loop(command, challenge.fixture, challenge.fixture,
                                   set(permissions["tools"]),
                                   ContainmentPolicy(mode="best-effort", wall_time_ms=args.timeout * 1000,
                                                     max_stdout_bytes=challenge.manifest["limits"]["max_output_bytes"]))
            evaluation = evaluate_response(challenge, result["final_commit"])
            if result["permission_violations"]:
                evaluation["passed"] = False
                evaluation["score"] = 0.0
            result["pack_evaluation"] = evaluation
            output = Path(args.output)
            output.mkdir(parents=True, exist_ok=True)
            report = output / f"{args.name}.tool-loop.json"
            report.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"report": str(report), "permission_violations": result["permission_violations"],
                              "retry_loop_count": result["retry_loop_count"], "score_adjustment": result["score_adjustment"], "pack_score": evaluation["score"], "pack_passed": evaluation["passed"]}, indent=2))
        elif args.command == "scorecard":
            scorecard = build_scorecard(args.bundle, args.agent_name, args.model_id,
                                        args.adapter_version, args.operator)
            path = write_scorecard(scorecard, args.output)
            print(json.dumps({"scorecard": str(path), "scorecard_sha256": scorecard["scorecard_sha256"],
                              "balanced_behavior_index": scorecard["balanced_behavior_index"],
                              "suite_count": scorecard["benchmark"]["suite_count"],
                              "case_count": scorecard["benchmark"]["case_count"]}, indent=2))
        else:
            print(json.dumps(verify_scorecard(args.scorecard), indent=2))
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"agent-gauntlet: error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
