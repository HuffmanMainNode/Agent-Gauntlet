import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from gauntlet.adversarial_runner import run_suite
from gauntlet.gri import DEFAULT_DOMAINS, build_gri
from gauntlet.leaderboard import build_scorecard
from gauntlet.pack_runner import discover_pack_ids

ROOT = Path(__file__).parents[1]
SCHEMAS = ROOT / "schemas"


def load_schema(name):
    schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def test_all_checked_in_schemas_are_valid():
    for path in sorted(SCHEMAS.glob("*.schema.json")):
        Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))


def test_every_declarative_pack_matches_challenge_schema():
    validator = Draft202012Validator(load_schema("challenge.schema.json"))
    for pack_id in discover_pack_ids(ROOT / "challenges"):
        manifest = json.loads(
            (ROOT / "challenges" / pack_id / "challenge.json").read_text(encoding="utf-8")
        )
        validator.validate(manifest)


def test_gri_output_matches_schema():
    rows = [
        {"pack_id": domain, "score": 90.0,
         "permission_violation": False, "injection_breach": False}
        for domain in DEFAULT_DOMAINS
    ]
    Draft202012Validator(load_schema("gri.schema.json")).validate(build_gri(rows))


def test_generated_scorecard_matches_schema(tmp_path):
    code = (
        "import json,sys; json.load(sys.stdin); "
        "print(json.dumps({'claims': [], 'abstain': True, 'conflict_detected': True}))"
    )
    bundle = run_suite(
        "hallucination", [sys.executable, "-c", code], [11, 12], tmp_path / "runs",
        agent_name="Schema Fixture Agent", model_id="schema-fixture/v1",
        adapter_version="schema-test-1", operator="ci",
    )
    scorecard = build_scorecard(
        [str(bundle)], "Schema Fixture Agent", "schema-fixture/v1", "schema-test-1", operator="ci"
    )
    validator = Draft202012Validator(
        load_schema("scorecard.schema.json"), format_checker=FormatChecker()
    )
    validator.validate(scorecard)
