"""Deterministic seed-derived presentation variants for synthetic challenge fixtures."""
from __future__ import annotations

import copy
import hashlib
from typing import Any

GENERATOR_ID = "evidence-order-sha256-v1"


def generate_seeded_fixture(base_fixture: dict[str, Any], seed: int) -> dict[str, Any]:
    """Return a deterministic evidence-order variant without inventing evidence.

    Existing evidence records are sorted by a seed-scoped SHA-256 key. Their
    contents and identifiers are preserved. Finite evidence sets can produce
    the same permutation for different seeds; callers must not claim otherwise.
    """
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    if not isinstance(base_fixture, dict):
        raise ValueError("base fixture must be an object")
    fixture = copy.deepcopy(base_fixture)
    evidence = fixture.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("fixture must contain a non-empty evidence list")
    identifiers = []
    for item in evidence:
        if not isinstance(item, dict):
            raise ValueError("evidence records must be objects")
        identifier = item.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("every evidence record must have a non-empty id")
        identifiers.append(identifier)
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("evidence record IDs must be unique")
    evidence.sort(
        key=lambda item: (
            hashlib.sha256(f"{seed}\\0{item['id']}".encode("utf-8")).digest(),
            item["id"],
        )
    )
    fixture["seed"] = seed
    fixture["variant"] = {
        "generator": GENERATOR_ID,
        "seed": seed,
        "evidence_order": [item["id"] for item in evidence],
    }
    return fixture
