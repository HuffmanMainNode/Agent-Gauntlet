"""Validate the generated reference baseline against its published JSON Schema."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python scripts/validate_reference_baseline.py PATH")
    schema_path = ROOT / "schemas" / "reference-baseline.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    baseline_path = Path(sys.argv[1])
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(baseline)
    print(f"valid reference baseline: {baseline_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
